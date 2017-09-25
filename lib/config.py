import json
from jsonschema import validate
import os
import re
from vcs.vcsrepo import VcsRepo
from lib.exceptions import ConfigError
from lib.exceptions import VcsError
from lib.exceptions import CommandError
from jsonschema.exceptions import ValidationError
from copy import deepcopy
from subprocess import CalledProcessError
from datetime import datetime, timezone
import subprocess
import getpass
import shutil
import copy

config = None
REMOTE_CONF_NAME = 'config.json'
REMOTE_SCRIPT_NAME = 'build_type.py'
LOCAL_CONF = os.path.join(os.path.expanduser('~'), '.sand.conf')
DEFAULT_CONF = '/opt/sandman/etc/config.json'
ALL_BUILD_TYPES = ['built.osx_universal', 'built.linux_armv6', 'built.linux_x86-64', 'built.linux_i686',
                   'built.linux_x86-64.org', 'built.win_32', 'built.win_x64']


class Config:
    def __init__(self, local_config, config_path):
        if not local_config:
            if not config_path:
                config_path = Config.local_config_to_parse()
            local_config = self.parse_config(config_path)
        self.validate_config(local_config, 'local')
        local_config = self.inject_variables_into_local_config(local_config)
        try:
            self.vcs = Config.clone_or_update_repo(local_config['vcsrepo'], force=True)
        except VcsError:
            shutil.rmtree(local_config['vcsrepo']['path'])
            os.chdir(os.path.dirname(os.path.abspath(__file__)))
            self.vcs = Config.clone_or_update_repo(local_config['vcsrepo'], force=True)
        self.config_path = os.path.join(local_config['vcsrepo']['path'], REMOTE_CONF_NAME)
        self.script_path = os.path.join(local_config['vcsrepo']['path'], REMOTE_SCRIPT_NAME)
        self.users = local_config['user']

    @staticmethod
    def local_config_to_parse():
        config_path = LOCAL_CONF
        if not os.path.exists(config_path):
            config_path = DEFAULT_CONF
        return config_path

    @staticmethod
    def clone_or_update_repo(vcsrepo, force=False, type_='code'):
        vcs = VcsRepo.get_repo(path=vcsrepo['path'],
                               provider=vcsrepo['provider'],
                               source=vcsrepo['source'],
                               revision=vcsrepo['revision'],
                               type_=type_)
        # Init the git repo
        try:
            if not vcs.exists():
                if os.path.isdir(vcsrepo['path']):
                    shutil.rmtree(vcsrepo['path'])
                vcs.init()
            else:
                if force:
                    vcs.force_update()
                else:
                    vcs.update()
        except CalledProcessError as e:
            raise VcsError(e, vcsrepo['path'], vcsrepo['source'], vcsrepo['revision'])

        return vcs

    @staticmethod
    def clone_or_update_aspect(aspect, force=False):
        return Config.clone_or_update_repo(aspect['vcsrepo'], force=force, type_=aspect['type'])

    def get_build_type(self):
        if not os.path.isfile(self.script_path) or not os.access(self.script_path, os.X_OK):
            raise CommandError("Script %s either doesn't exist or is not executable.")
        p = subprocess.Popen(["python", self.script_path], stdout=subprocess.PIPE)
        return p.communicate()[0].decode().replace("\n", "")

    def get_build_info(self, build_type, dep_types):
        urls = {}
        components = {}
        for branch in self.vcs.branches():
            try:
                self.vcs.checkout(branch)
                self.vcs.update()
                components[branch] = {}
                vcs_config = Config.validate_config(Config.parse_config(self.config_path), 'remote')
                for component in vcs_config['components']:
                    if 'integrate' in component['attributes'] and not component['attributes']['integrate']:
                        continue
                    if 'platforms' not in component['attributes'] or len(component['attributes']['platforms']) == 0:
                        continue
                    component_aspects = Config.get_aspects(component['name'], vcs_config['components'], vcs_config['aspects'],
                                                           dep_types, branch, build_type, self.users,
                                                           "")
                    components[branch][component['name']] = component['attributes']
                    for _, aspects in component_aspects.items():
                        for a in aspects:
                            if a['type'] != 'code':
                                continue
                            source = re.sub(r'.*/reporoot', '/reporoot', a['vcsrepo']['source'])
                            source = re.sub(r'.*/gitroot', '/gitroot', source)
                            if source == "git@gitlab.imat.io:ui/imat.git":
                                source = "/var/opt/gitlab/git-data/repositories/ui/imat.git"
                            if a['vcsrepo']['provider'] == 'git':
                                source = "%s.%s" % (source, a['vcsrepo']['revision'])
                            if source not in urls.keys():
                                urls[source] = set()
                            urls[source].add("%s.%s" % (a['name'], branch))
            except CalledProcessError as e:
                raise VcsError(e, self.vcs.path, self.vcs.source, self.vcs.revision)
        return {'components': components, 'urls': urls}

    def get_repository_changesets(self, build_type, dep_types, b='all'):
        repository_check = {}
        repositories = []
        for branch in self.vcs.branches():
            if branch != 'all' and branch != b:
                continue
            try:
                self.vcs.checkout(branch)
                self.vcs.update()
                vcs_config = Config.validate_config(Config.parse_config(self.config_path), 'remote')
                for top in vcs_config['components']:
                    component_aspects = Config.get_aspects(top['name'], vcs_config['components'], vcs_config['aspects'],
                                                           dep_types, branch, build_type, self.users,
                                                           "")
                    for _, c_aspects in component_aspects.items():
                        for a in c_aspects:
                            vcs = VcsRepo.get_repo(path=a['vcsrepo']['path'],
                                                   provider=a['vcsrepo']['provider'],
                                                   source=a['vcsrepo']['source'],
                                                   revision=a['vcsrepo']['revision'],
                                                   type_=a['type']
                                                   )

                            if branch not in repository_check.keys():
                                repository_check[branch] = {}
                            if a['name'] not in repository_check[branch].keys():
                                repository_check[branch][a['name']] = {}
                            if a['type'] not in repository_check[branch][a['name']].keys():
                                repository_check[branch][a['name']][a['type']] = {}
                                a['vcsrepo']['changeset'] = vcs.get_remote_head_revision()
                                if a['vcsrepo']['changeset']:
                                    a['branch'] = branch
                                    del a['vcsrepo']['built_path']
                                    del a['vcsrepo']['path']
                                    repositories.append(a)
            except CalledProcessError as e:
                raise VcsError(e, self.vcs.path, self.vcs.source, self.vcs.revision)
        return sorted(repositories, key=lambda x: (x['branch'], x['name'], x['type']))

    def gather_facts(self, component, branch, sand_type, sand_path):
        # TODO: fix this try catch around everything crazyness
        supported_branches = self.vcs.branches()
        if branch not in supported_branches:
            if len(supported_branches) == 0:
                raise VcsError(
                    "Repo not connected to any remote branches. Please 'rm -rf /opt/sandman/cache/config' and try again.",
                    self.vcs.path, self.vcs.source, self.vcs.revision)
            raise ConfigError("Branch %s is not supported. Available branches: %s" % (branch, supported_branches))

        try:
            self.vcs.checkout(branch)
        except CalledProcessError as e:
            raise VcsError(e, self.vcs.path, self.vcs.source, self.vcs.revision)
        try:
            build_type = self.get_build_type()
            vcs_config = Config.validate_config(Config.parse_config(self.config_path), 'remote')
            top = Config.get_config_component(vcs_config['components'], component)
            sandbox = Config.get_config_sandbox(vcs_config, sand_type)
            facts = {
                'aspects': [],
                'attributes': [],
                'branch': branch,
                'build_type': build_type,
                'config_aspects':  vcs_config['aspects'],
                'commands': [],
                'components': vcs_config['components'],
                'env': {},
                'top': top,
                'sandbox': sandbox,
                'sand_path': sand_path,
            }

            if 'attributes' in top:
                facts['attributes'] = top['attributes']

            for command_name in sandbox['commands']:
                facts['commands'].append(Config.get_config_command(vcs_config, command_name))
            # Override sandbox commands
            if 'commands' in top and len(top['commands']) > 0:
                for command in top['commands']:
                    facts['commands'] = [c for c in facts['commands'] if command['name'] != c['name']]
                    facts['commands'].append(Config.get_config_command(top, command['name'], top_name=top['name']))

            component_aspects = Config.get_aspects(top['name'], vcs_config['components'], vcs_config['aspects'],
                                                   sandbox['dependency_types'], branch, build_type, self.users,
                                                   sand_path)
            for _, c_aspects in component_aspects.items():
                for aspect in c_aspects:
                    facts['aspects'].append(aspect)
            # Always include buildscripts code aspect
            if 'buildscripts' not in component_aspects.keys() or not [a for a in component_aspects['buildscripts'] if
                                                                      a['type'] == 'code']:
                component_aspects = Config.get_aspects('buildscripts', vcs_config['components'], vcs_config['aspects'],
                                                       sandbox['dependency_types'], branch, build_type, self.users,
                                                       sand_path, recurse=False)
                facts['aspects'].append(Config.get_specific_aspect_by_type(component_aspects, 'code'))

            component_aspects = Config.get_aspects(top['name'], vcs_config['components'], vcs_config['aspects'],
                                                   sandbox['dependency_types'], branch, build_type, self.users,
                                                   sand_path, recurse=False, dep_type='built')
            facts["top_built_aspect"] = Config.get_specific_aspect_by_type(component_aspects, 'built')

            if 'env' in sandbox:
                facts['env'] = sandbox['env']

        except ConfigError as e:
            e.message = "Error with config on branch '%s': %s " % (branch, e)
            raise e

        return facts

    @staticmethod
    def get_specific_aspect_by_type(component_aspects, type):
        for _, c_aspects in component_aspects.items():
            for aspect in c_aspects:
                if aspect['type'] == type:
                    return aspect

    @staticmethod
    def get_config(configuration=None, config_path=None):
        global config
        if config is None:
            config = Config(configuration, config_path)
        return config

    @staticmethod
    def get_config_aspect(aspects, aspect_name, component, dep_type=None):
        matched_aspects = [a for a in aspects if aspect_name == a['name']]
        if len(matched_aspects) < 1:
            if dep_type:
                raise ConfigError(
                    "The dependency component=%s, type=%s failed because there is no aspect with name %s." % (
                        component, dep_type, aspect_name))
            else:
                raise ConfigError(
                    "The top level component %s failed because there is no aspect with name %s." % (
                        component, aspect_name))
        if len(matched_aspects) > 1:
            if dep_type:
                raise ConfigError(
                    "The dependency component=%s, type=%s failed because there are more than 1 aspect named %s." %
                    (component, aspect_name))
            else:
                raise ConfigError(
                    "The top level component %s failed because there are more than 1 aspect named %s." % (
                        component, aspect_name))
        aspect = deepcopy(matched_aspects[0])
        # This is to know when we layout the sandbox if it was an actual built dependency or another type
        # that just needed a folder created.
        if aspect['type'] == 'built':
            if dep_type and dep_type == "built":
                aspect['clone'] = True
            else:
                aspect['clone'] = False
        return aspect

    @staticmethod
    def get_config_command(vcs_config, command_name, top_name=None):
        matched_commands = [c for c in vcs_config['commands'] if command_name == c['name']]
        if len(matched_commands) < 1:
            if top_name:
                raise ConfigError(
                    "The top level component %s commands failed because there is no command with name %s." % (
                        top_name, command_name))
            else:
                raise ConfigError(
                    "The sandbox commands failed because there is no command with name %s." % command_name)
        if len(matched_commands) > 1:
            if top_name:
                raise ConfigError(
                    "The top level component %s commands failed because there is more than one command with name %s." % (
                        top_name, command_name))
            else:
                raise ConfigError(
                    "The sandbox commands failed because there is more than one command with name %s." % command_name)
        return matched_commands[0]

    @staticmethod
    def get_config_component(components, component_name):
        c_list = [c for c in components if c['name'] == component_name]
        if len(c_list) < 1:
            comp_names = list(set([c['name'] for c in components]))
            comp_names.sort()
            raise ConfigError(
                "Component '%s' was not found." % component_name)
        if len(c_list) > 1:
            raise ConfigError(
                "Component '%s' was found multiple times in the component section of the config." % component_name)
        return c_list[0]

    @staticmethod
    def get_config_sandbox(vcs_config, sandbox_name):
        sandboxes = []
        for s in vcs_config['sandbox_types']:
            regex = r'%s' % s['name']
            if re.search(regex, sandbox_name, re.IGNORECASE):
                sandboxes.append(s)
        if len(sandboxes) > 1:
            raise ConfigError("Multiple sandbox types match %s. %s" % (sandbox_name, sandboxes))
        if len(sandboxes) == 0:
            sandboxes = [s for s in vcs_config['sandbox_types'] if 'default' in s and s['default'] is True]
            if len(sandboxes) == 0:
                raise ConfigError("Unable to find a default sandbox type or one that matches %s." % sandbox_name)
            else:
                print("Unable to find sandbox type that matches %s.  Using default sandbox type %s" % (sandbox_name,
                                                                                                       sandboxes[0][
                                                                                                           'name']))
        return sandboxes[0]

    @staticmethod
    def clean_aspects(component, aspects):
        unique_types = list(set(aspect['type'] for aspect in aspects))
        # Check for built and code aspects because if you have the code aspect you do not need the built aspect
        if 'built' in unique_types and 'code' in unique_types:
            aspects = [a for a in aspects if a['type'] != 'built']
        # Check for duplicate types to avoid cloning twice
        for type_ in unique_types:
            common = [a for a in aspects if a['type'] == type_]
            if len(common) > 1:
                unique_sources = list(set(aspect['vcsrepo']['source'] for aspect in common))
                if len(unique_sources) > 1:
                    raise ConfigError("Component %s has 2 aspects with the same type %s and different sources: %s" % (
                        component, type_, unique_sources))
                unique_providers = list(set(aspect['vcsrepo']['provider'] for aspect in common))
                if len(unique_providers) > 1:
                    raise ConfigError("Component %s has 2 aspects with the same type %s and different providers: %s" % (
                        component, type_, unique_providers))
                unique_revisions = list(set(aspect['vcsrepo']['revision'] for aspect in common))
                if len(unique_revisions) > 1:
                    raise ConfigError("Component %s has 2 aspects with the same type %s and different revisions: %s" % (
                        component, type_, unique_revisions))
                # If they are all duplicates remove all of them except one.
                aspects = [a for a in aspects if a['type'] != type_]
                aspects.append(common[0])
        return aspects

    @staticmethod
    def get_component_tree(component_name, components, comp_types, tree=None):
        if not tree:
            tree = ComponentTree(component_name, comp_types[component_name])
            del comp_types[component_name]

        component_children = [c for c in Config.get_config_component(components, component_name)['dependencies'] if
                              c['component'] in comp_types.keys() and (
                                  comp_types[c['component']] != "code" or
                                  (comp_types[c['component']] == "code" and c['type'] == 'code')
                              )
                              ]
        tree.children = [ComponentTree(c['component'], comp_types[c['component']]) for c in component_children]

        children_not_terminal = []
        for c in component_children:
            if Config.is_terminal_dependency(c['component'], c['type'], components):
                tree.get_child(c['component']).set_terminal()
            else:
                children_not_terminal.append(c)
            if c['component'] in comp_types:
                del comp_types[c['component']]

        for dep in children_not_terminal:
            Config.get_component_tree(dep['component'], components, comp_types, tree.get_child(dep['component']))
        return tree

    @staticmethod
    def get_built_component_tree(component_name, components, tree=None):
        if not tree:
            tree = ComponentTree(component_name, 'built')

        component_children = [c for c in Config.get_config_component(components, component_name)['dependencies']
                              if c['type'] == 'built' and not
                              Config.get_config_component(components, c['component'])['attributes']['exclude_bu2']]

        tree.children = [ComponentTree(c['component'], 'built') for c in component_children]

        children_not_terminal = []
        for c in component_children:
            if Config.is_terminal_dependency(c['component'], c['type'], components):
                tree.get_child(c['component']).set_terminal()
            else:
                children_not_terminal.append(c)

        for dep in children_not_terminal:
            Config.get_built_component_tree(dep['component'], components, tree.get_child(dep['component']))
        return tree

    @staticmethod
    def get_component_types(component_name, components, build_type, dep_type='code', comp_types=None,
                            built_descendant=False):
        if not comp_types:
            comp_types = {component_name: dep_type}

        if dep_type == 'built' or built_descendant:
            dep_type = build_type

        if component_name not in comp_types or dep_type == 'code':
            comp_types[component_name] = dep_type

        if Config.is_terminal_dependency(component_name, dep_type, components):
            return comp_types

        for dep in Config.get_config_component(components, component_name)['dependencies']:
            if built_descendant or dep_type == build_type:
                Config.get_component_types(dep['component'], components, build_type, dep_type=dep['type'],
                                           comp_types=comp_types, built_descendant=True)
            else:
                Config.get_component_types(dep['component'], components, build_type, dep_type=dep['type'],
                                           comp_types=comp_types, built_descendant=False)
        return comp_types

    @staticmethod
    def create_dependency_files(sand_path, component_name, components, build_type):
        legacy_file = os.path.join(sand_path, 'dependencies.txt')
        graph_file = os.path.join(sand_path, 'dependency_tree.txt')
        comp_type = None
        if not os.path.isfile(legacy_file):
            comp_type = Config.get_component_types(component_name, components, build_type)
            comp_tree = Config.get_component_tree(component_name, components, deepcopy(comp_type))
            deps = comp_tree.order_deps()
            with open(legacy_file, 'w') as f:
                for comp in deps:
                    f.write("%s: %s\n" % (comp, comp_type[comp]))
        if not os.path.isfile(graph_file):
            if not comp_type:
                comp_type = Config.get_component_types(component_name, components, build_type)
            comp_tree = Config.get_component_tree(component_name, components, comp_type)
            with open(graph_file, 'w') as f:
                f.write("%s" % comp_tree)

    def get_build_up_to_deps(self, component_name, facts, debug=False):
        comp_tree = Config.get_built_component_tree(component_name, facts['components'])
        if debug:
            print("----------------------------")
            print("Full Dependency tree for %s:" % component_name)
            print(comp_tree)
        deps = comp_tree.get_build_up_to_deps(facts['components'])
        if debug:
            print("----------------------------")
            print("Build upto dependencies tree for %s:" % component_name)
            print(json.dumps({'bu2_deps': deps}, indent=3))
        return self.remove_already_published_dependencies(deps, facts, debug)

    @staticmethod
    def combine_build_up_to_deps(list1, list2):
        if len(list1) >= len(list2):
            big_list = list1
            small_list = list2
        else:
            big_list = list2
            small_list = list1
        for i, deps in enumerate(small_list):
            big_list[i] = list(set(big_list[i] + deps))
        return big_list

    def remove_already_published_dependencies(self, deps, facts, debug):
        needs_to_be_built = list()
        for i, _ in enumerate(deps):
            already_built_curr = set()
            for component in deps[i]:
                if component in needs_to_be_built:
                    if debug:
                        print("Scheduling component %s because it depends on something being built for this bu2." % component)
                    already_built_curr.add(component)
                    continue
                component_aspects = Config.get_aspects(component, facts['components'], facts['config_aspects'],
                                                       {}, facts['branch'], facts['build_type'],
                                                       self.users, facts['sand_path'], recurse=False, dep_type='built')
                built_aspect = Config.get_specific_aspect_by_type(component_aspects, 'built')
                built_vcs = VcsRepo.get_repo(path=built_aspect['vcsrepo']['path'],
                                             provider=built_aspect['vcsrepo']['provider'],
                                             source=built_aspect['vcsrepo']['source'],
                                             revision=built_aspect['vcsrepo']['revision'],
                                             type_=built_aspect['type'])
                sources = built_vcs.get_sources()
                if debug:
                    print("----------------------------")
                    print("Looking at sources.txt for %s:" % component)
                for source in sources:
                    if debug:
                        print(source)
                    component_aspects = Config.get_aspects(source['name'], facts['components'], facts['config_aspects'],
                                                           {}, facts['branch'], facts['build_type'],
                                                           self.users, facts['sand_path'], recurse=False, dep_type=source['type'])
                    aspect = Config.get_specific_aspect_by_type(component_aspects, source['type'])
                    vcs = VcsRepo.get_repo(path=aspect['vcsrepo']['path'],
                                                provider=aspect['vcsrepo']['provider'],
                                                source=aspect['vcsrepo']['source'],
                                                revision=aspect['vcsrepo']['revision'],
                                                type_=aspect['type'])
                    rev = vcs.get_remote_head_revision()
                    if debug:
                        print("Actual revision is %s" % rev)
                    if not rev or len(rev) < 8 or rev[-8:] not in source['revision']:
                        if rev is None and source['revision'].lower() == 'none':
                            continue
                        if debug:
                            print("Scheduling component %s because %s aspect of the %s component is out of date." % (component, source['type'], source['name']))
                        already_built_curr.add(component)
                        level = i
                        parent_components = []
                        prev_deps = [component]
                        while len(deps) > level + 2:
                            curr_deps = []
                            for c in prev_deps:
                                curr_deps.extend(ComponentTree.filter_dependencies_that_depend_on_component(c, facts['components'], deps[level + 1]))
                            parent_components.extend(curr_deps)
                            prev_deps = curr_deps
                            level += 1
                        # Always add the top level
                        parent_components.extend(deps[len(deps) - 1])
                        needs_to_be_built.extend(parent_components)
                        # If even one of the sources is not the same this needs rebuild so breaking out of sources loop
                        break
            deps[i] = list(already_built_curr)
            needs_to_be_built.extend(list(already_built_curr))
        return [d for d in deps if len(d) > 0]

    @staticmethod
    def get_manifest_lines(relative_path, folder_to_publish, vcs_hidden_folder):
        files = []
        for f in os.listdir(os.path.join(folder_to_publish, relative_path)):
            if "%s" % vcs_hidden_folder in f:
                continue
            path = (os.path.join(folder_to_publish, relative_path, f))
            if os.path.isdir(path):
                files += Config.get_manifest_lines(os.path.join(relative_path, f), folder_to_publish, vcs_hidden_folder)
            else:
                files.append('%s,%s' % (os.path.join(relative_path, f), os.stat(path).st_size))
        return files

    def create_publish_files(self, top_name, built_path, aspects, build_type, vcs_hidden_folder):
        source_file = os.path.join(built_path, 'source.txt')
        manifest_file = os.path.join(built_path, 'manifest.txt')
        manifest_lines = Config.get_manifest_lines('', built_path, vcs_hidden_folder)
        with open(manifest_file, 'w') as f:
            f.write('Last published on %s\n' % datetime.now(timezone.utc).astimezone().isoformat().replace('T', ' '))
            f.write('\n'.join(manifest_lines))
        top_revision = None
        with open(source_file, 'w') as f:
            for a in sorted(aspects, key=lambda x: (x['name'], x['type'])):
                vcs = VcsRepo.get_repo(path=a['vcsrepo']['path'],
                                       provider=a['vcsrepo']['provider'],
                                       source=a['vcsrepo']['source'],
                                       revision=a['vcsrepo']['revision'],
                                       type_=a['type'])
                # TODO: move get_head_revision() to vcs.get_head_commit() after we stop using depends.py in buildupto
                rev = vcs.get_head_revision()
                if a['name'] == top_name and a['type'] == 'code':
                    top_revision = rev
                if a['type'] == 'built':
                    type_ = build_type
                else:
                    type_ = a['type']
                f.write("%s.%s: %s\n" % (a['name'], type_, rev))
        shutil.copy(self.config_path, built_path)
        return top_revision

    @staticmethod
    def is_terminal_dependency(component_name, component_type, components):
        if component_type == 'code':
            return False
        component = Config.get_config_component(components, component_name)
        if 'attributes' in component and 'terminal_dependency' in component['attributes']:
            return component['attributes']['terminal_dependency']
        else:
            return False

    @staticmethod
    def get_aspects(component_name, components, conf_aspects, dependency_types, branch, arch, users, sand_path,
                    dep_type='code', comp_aspects=None, recurse=True, built_descendant=False):
        if not comp_aspects:
            comp_aspects = {}
        if not dependency_types:
            dependency_types = {
                "code": [
                    "code",
                ],
                "built": [
                    "built",
                ],
                "test": [
                    "test",
                ]
            }
        if dep_type not in dependency_types:
            raise ConfigError("Dependency type %s is not defined for component %s" % (dep_type, component_name))

        component = Config.get_config_component(components, component_name)
        # Get aspects for the component
        aspects = []
        for aspect_name in dependency_types[dep_type]:
            used_aspects = conf_aspects

            if 'aspects' in component and len(component['aspects']) > 0:
                for aspect in component['aspects']:
                    used_aspects = [a for a in used_aspects if a['name'] != aspect['name']]
                    used_aspects.append(aspect)
            aspects.append(Config.get_config_aspect(used_aspects, aspect_name, component_name, dep_type=dep_type))
        aspects = Config.inject_variables_into_aspects(aspects, component_name, branch, arch, users, sand_path)
        if component_name in comp_aspects:
            comp_aspects[component_name].extend(aspects)
        else:
            comp_aspects[component_name] = aspects
        comp_aspects[component_name] = Config.clean_aspects(component_name, comp_aspects[component_name])

        if recurse and not Config.is_terminal_dependency(component_name, dep_type, components):
            for dep in component['dependencies']:
                if built_descendant or dep_type == 'built':
                    comp_aspects.update(
                        Config.get_aspects(dep['component'], components, conf_aspects, dependency_types, branch, arch,
                                           users, sand_path, 'built', comp_aspects, built_descendant=True))
                else:
                    comp_aspects.update(
                        Config.get_aspects(dep['component'], components, conf_aspects, dependency_types, branch, arch,
                                           users, sand_path, dep['type'], comp_aspects, built_descendant=False))
        return comp_aspects

    @staticmethod
    def inject_variables_into_local_config(conf):
        user_regex = re.compile(r'\$\s*?\{\s*system_user\s*\}', re.IGNORECASE)
        system_user = getpass.getuser()

        for k, v in conf['vcsrepo'].items():
            conf['vcsrepo'][k] = user_regex.sub(system_user, conf['vcsrepo'][k])

        for k, v in conf['user'].items():
            conf['user'][k]['name'] = user_regex.sub(system_user, conf['user'][k]['name'])
        return conf

    @staticmethod
    def inject_variables_into_aspects2(aspects, component, branch, build_type, users, sand_path):
        component_regex = re.compile(r'\$\s*?\{\s*component\s*\}', re.IGNORECASE)
        branch_regex = re.compile(r'\$\s*?\{\s*branch\s*\}', re.IGNORECASE)
        built_regex = re.compile(r'\$\s*?\{\s*built\s*\}', re.IGNORECASE)
        user_regex = re.compile(r'\$\s*?\{\s*user[^.]*\.\s*([^.]+)\s*\.*name\s*\}', re.IGNORECASE)

        modified_aspects = []
        for a in aspects:
            aspect = deepcopy(a)
            aspect['name'] = component
            m = user_regex.search(aspect['vcsrepo']['source'])
            if m:
                provider = m.group(1)
                if provider not in users.keys():
                    raise ConfigError("Variable '%s' in the remote config is not defined in the local config."
                                      % m.group(0))
                aspect['vcsrepo']['source'] = user_regex.sub(users[provider]['name'], aspect['vcsrepo']['source'])
            aspect['vcsrepo']['source'] = component_regex.sub(component, aspect['vcsrepo']['source'])
            aspect['vcsrepo']['source'] = branch_regex.sub(branch, aspect['vcsrepo']['source'])
            aspect['vcsrepo']['source'] = built_regex.sub(build_type, aspect['vcsrepo']['source'])
            aspect['vcsrepo']['revision'] = component_regex.sub(component, aspect['vcsrepo']['revision'])
            aspect['vcsrepo']['revision'] = branch_regex.sub(branch, aspect['vcsrepo']['revision'])
            aspect['vcsrepo']['revision'] = built_regex.sub(build_type, aspect['vcsrepo']['revision'])
            aspect['vcsrepo']['built_path'] = os.path.join(sand_path, build_type, component)
            if aspect['type'] == 'built':
                aspect['vcsrepo']['path'] = os.path.join(sand_path, build_type, component)
            else:
                aspect['vcsrepo']['path'] = os.path.join(sand_path, aspect['type'], component)
            modified_aspects.append(aspect)
        return modified_aspects

    @staticmethod
    def inject_variables_into_aspects(aspects, component, branch, build_type, users, sand_path):
        if build_type == 'all':
            modified_aspects = Config.inject_variables_into_aspects2([a for a in aspects if a['type'] != 'built'],
                                                                     component, branch, build_type, users, sand_path)
            for b_type in ALL_BUILD_TYPES:
                modified_built_aspects = Config.inject_variables_into_aspects2(
                    [a for a in aspects if a['type'] == 'built'], component, branch, b_type, users, sand_path)
                for m in modified_built_aspects:
                    m['type'] = b_type
                modified_aspects.extend(modified_built_aspects)
            return modified_aspects
        else:
            return Config.inject_variables_into_aspects2(aspects, component, branch, build_type, users, sand_path)

    @staticmethod
    def parse_config(config_path):
        if not os.path.isfile(config_path):
            raise ConfigError("Config file '%s' does not exist" % config_path)
        try:
            lines = ""
            for line in open(config_path):
                li = line.strip()
                if not li.startswith("#"):
                    lines += line.rstrip()
            configuration = json.loads(lines)
        except ValueError as e:
            raise ConfigError("Config File '%s' contains invalid json. %s" % (config_path,
                                                                              e))
        return configuration

    @staticmethod
    def print_aspect_missing(aspect):
        vcs = VcsRepo.get_repo(path=aspect['vcsrepo']['path'],
                               provider=aspect['vcsrepo']['provider'],
                               source=aspect['vcsrepo']['source'],
                               revision=aspect['vcsrepo']['revision'],
                               type_=aspect['type'])
        try:
            vcs.print_missing()
        except CalledProcessError as e:
            raise VcsError(e, aspect['path'], aspect['source'], aspect['revision'])

    @staticmethod
    def print_aspect_status(aspect):
        vcs = VcsRepo.get_repo(path=aspect['vcsrepo']['path'],
                               provider=aspect['vcsrepo']['provider'],
                               source=aspect['vcsrepo']['source'],
                               revision=aspect['vcsrepo']['revision'],
                               type_=aspect['type'])
        try:
            if vcs.exists():
                return vcs.print_status()
            return False
        except CalledProcessError as e:
            raise VcsError(e, aspect['path'], aspect['source'], aspect['revision'])

    @staticmethod
    def reset_config():
        global config
        config = None

    @staticmethod
    def validate_config(conf, type_):
        if not isinstance(conf, dict):
            raise ConfigError("The %s configuration must be a valid json object." % type_)
        if type_ == 'remote':
            schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config_schemas/remote.schema.json')
        elif type_ == 'local':
            schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config_schemas/local.schema.json')
        else:
            raise ConfigError("Only remote and local config types are supported")
        with open(schema_path, 'r') as schema_file:
            schema = json.loads(schema_file.read())
        try:
            validate(conf, schema)
        except ValidationError as e:
            raise ConfigError("The %s configuration file is not valid because: %s" % (type_, e))
        return conf


class ComponentTree(object):
    def __init__(self, name, type_="", children=[]):
        self.name = name
        self.type = type_
        self.children = children

    def __str__(self, level=0):
        ret = "\t" * level + "%s(%s)" % (self.name, self.type) + "\n"
        for child in self.children:
            ret += child.__str__(level + 1)
        return ret

    def get_child(self, name):
        return [a for a in self.children if a.name == name][0]

    def set_terminal(self):
        self.type = "%s:terminal-dependency" % self.type

    @staticmethod
    def clean_deps(deps):
        already_built_prev = list()
        for i, _ in enumerate(deps):
            already_built_curr = set()
            for d in deps[i]:
                if d not in already_built_prev:
                    already_built_curr.add(d)
            deps[i] = list(already_built_curr)
            already_built_prev.extend(list(already_built_curr))
        return [d for d in deps if len(d) > 0]

    @staticmethod
    def filter_dependencies_that_depend_on_component(me, components, dependencies):
        components_that_depend_on_me = []
        for component in dependencies:
            if [d for d in Config.get_config_component(components, component)['dependencies'] if
                    d['type'] == 'built' and d['component'] == me]:
                components_that_depend_on_me.append(component)
        return components_that_depend_on_me

    @staticmethod
    def pull_deps_down_one_level(dependencies, components):
        previously_pulled_down = list()
        for i, _ in enumerate(dependencies):
            if len(dependencies) < i + 2:
                break
            cant_be_pulled_down = list()
            for component in dependencies[i]:
                cant_be_pulled_down.extend(
                    ComponentTree.filter_dependencies_that_depend_on_component(component, components,
                                                                               dependencies[i + 1]))
            dependencies[i] = [x for x in dependencies[i] if x not in previously_pulled_down] + [x for x in dependencies[i+1] if x not in cant_be_pulled_down]
            previously_pulled_down = dependencies[i]
        return dependencies

    @staticmethod
    def dependencies_are_equal(list1, list2):
        first_set = set(map(tuple, list1))
        second_set = set(map(tuple, list2))
        return first_set.symmetric_difference(second_set)

    @staticmethod
    def optimize_deps(deps, components):
        while True:
            new_deps = ComponentTree.pull_deps_down_one_level(copy.deepcopy(deps), components)
            if not ComponentTree.dependencies_are_equal(deps, new_deps):
                break
            deps = new_deps
        return deps

    def get_deps(self):
        tree = self.__str__().replace('\n', '')
        build_info = {}
        while tree.find('\t') != -1:
            level = 0
            while tree.startswith('\t'):
                tree = tree[1:]
                level += 1
            next_ = tree.find('\t')
            if level not in build_info:
                build_info[level] = []
            build_info[level].append(tree[0:tree.find('(')])
            tree = tree[next_:]
        if 0 not in build_info:
            build_info[0] = [tree[0:tree.find('(')]]
        sorted_tuples = sorted(build_info.items(), reverse=True)
        _, dependencies = zip(*sorted_tuples)
        return self.clean_deps(list(dependencies))

    def get_build_up_to_deps(self, components):
        return self.optimize_deps(self.get_deps(), components)

    def order_deps(self):
        deps = self.get_deps()
        return [item for sublist in deps for item in sublist]
