import os
import re
from lib.exceptions import SandboxNameError
from lib.exceptions import CommandError
from lib.exceptions import SandboxExistsError
from lib.exceptions import SandboxNotExistsError
from lib.exceptions import SandmanException
from lib.config import Config
from lib.utils import prompt_question
import shutil
from subprocess import Popen
import stat
import sys
from vcs.vcsrepo import VcsRepo
import json

STANDARD_NAME_PAT = re.compile(r'^([^.]+)\.([^.]+)\.(.+)$', re.IGNORECASE)


class Sandbox:
    def __init__(self, base_dir, sandbox_name, config=None, debug=False, bu2_components=""):
        self.path = os.path.join(base_dir, sandbox_name)
        self.base_dir = base_dir
        self.name = sandbox_name
        self.debug = debug
        self.bu2_components = bu2_components.split(",")
        self.top, self.branch, self.type = self.parse_sandbox_name(sandbox_name)
        if not config:
            self.config = Config.get_config()
        else:
            self.config = config
        self.facts = self.config.gather_facts(self.top, self.branch, self.type, self.path)

    def remove(self):
        """
        Removes the sandbox
        """
        local_changes = False
        if not os.path.isdir(self.path):
            print("The sandbox was not there to remove.")
            return

        for aspect in self.facts['aspects']:
            if self.config.print_aspect_status(aspect):
                local_changes = True
        if local_changes and not prompt_question("Are you sure you want to lose local changes on sandbox %s?" % self.name):
                return
        shutil.rmtree(self.path)

    def init(self):
        """
        Pulls down the correct component aspects.
        """
        if os.path.isdir(self.path):
            raise SandboxExistsError(self.name, self.base_dir)
        else:
            os.makedirs(os.path.join(self.path, 'run'))
        self._clone_or_update_aspects(force=True)

    def update(self):
        """
        Pulls down or updates the correct component aspects.
        """
        if not os.path.isdir(self.path):
            raise SandboxNotExistsError(self.name, self.base_dir)
        self._clone_or_update_aspects(force=False)

    def publish_prep(self):
        """
        Prepare the build directory for a publish
        """
        vcs = self.config.clone_or_update_aspect(self.facts['top_built_aspect'], force=True)
        vcs.publish_prep()

    def bu2_dependencies(self):
        """
        Return a json list of lists of components that need to be built in order for the component to be built.
        :return:
        """
        deps = self.config.get_build_up_to_deps(self.top, self.facts, self.debug)
        for component in self.bu2_components:
            if not component:
                continue
            if self.debug:
                print("Before combining with %s dependency list is %s" % (component, json.dumps(deps, indent=3)))
            facts = self.config.gather_facts(component, self.branch, self.type, self.path)
            component_deps = self.config.get_build_up_to_deps(component, facts, self.debug)
            deps = self.config.combine_build_up_to_deps(deps, component_deps)
            if self.debug:
                print("After combining with %s dependency list is %s" % (component, json.dumps(deps, indent=3)))
        print(json.dumps(deps, indent=3))

    def commit_info(self):
        """
        Print the revision and comment of the top level code component
        """
        top_aspects = [a for a in self.facts['aspects'] if a['name'] == self.facts['top']['name'] and a['type'] == 'code']
        if len(top_aspects) > 0:
            vcsrepo = top_aspects[0]['vcsrepo']
            vcs = VcsRepo.get_repo(path=vcsrepo['path'],
                                   provider=vcsrepo['provider'],
                                   source=vcsrepo['source'],
                                   revision=vcsrepo['revision'],
                                   type_=top_aspects[0]['type'])
            commit = vcs.get_head_commit()
            if commit:
                print(commit)

    def publish(self):
        """
        Publish the sandbox
        """
        vcsrepo = self.facts['top_built_aspect']['vcsrepo']
        vcs = VcsRepo.get_repo(path=vcsrepo['path'],
                               provider=vcsrepo['provider'],
                               source=vcsrepo['source'],
                               revision=vcsrepo['revision'],
                               type_=self.facts['top_built_aspect']['type'])
        if not vcs.exists():
            raise CommandError("There is no VCS repo at %s.  Run command 'publish_prep' first." % (vcsrepo['path']))
        rev = self.config.create_publish_files(self.facts['top']['name'], vcsrepo['path'], self.facts['aspects'],
                                               self.facts['build_type'], vcs.get_hidden_folder())

        vcs.publish("Published %s.%s.%s for %s" % (self.top, self.branch, rev, self.facts['build_type']))

    def force_update(self):
        """
        Reset --hard the repo before updates the correct component aspects.
        """
        self._clone_or_update_aspects(force=True)

    def status(self):
        """
        Prints the status of all modified repositories.
        """
        for aspect in self.facts['aspects']:
            self.config.print_aspect_status(aspect)

    def missing(self):
        """
        Prints the commits that are missing in the local repositories.
        """
        for aspect in self.facts['aspects']:
            self.config.print_aspect_missing(aspect)

    def _clone_or_update_aspects(self, force=False):
        """
        Clones aspect repositories if they doesn't exist or updates them if the do
        """
        try:
            for aspect in self.facts['aspects']:
                if aspect['type'] == 'built':
                    if aspect['clone']:
                        self.config.clone_or_update_aspect(aspect, force)
                    continue
                if aspect['type'] == 'code':
                    os.makedirs(aspect['vcsrepo']['built_path'], exist_ok=True)
                self.config.clone_or_update_aspect(aspect, force)
            self.config.create_dependency_files(self.path, self.facts['top']['name'], self.facts['components'],
                                                self.facts['build_type'])
            self.exe_command("tools")
            self.exe_command("init_config")
        except SandmanException as e:
            print("The following error occurred: %s\n" % e)
            if prompt_question("Would you like to remove incomplete sandbox %s?" % self.name):
                self.remove()

    def get_commands(self):
        """
        Return the available commands that can be executed in this sandbox
        """
        return list(set([c['name'] for c in self.facts['commands']]))

    def exe_command(self, name):
        """
        Execute one of the available commands in this sandbox
        """
        # I don't check if command exists because argparse checks before this is called
        command = [a for a in self.facts['commands'] if a['name'] == name][0]
        if command['type'] == 'command' and len(command['command']) > 0:
            if 'cwd' not in command:
                if not os.path.isdir(self.path):
                    os.makedirs(self.path)
                command['cwd'] = self.path
            script = os.path.join(self.path, command['command'][0])
            if os.path.isfile(script):
                command['command'][0] = script
                if not os.access(script, os.X_OK):
                    st = os.stat(script)
                    os.chmod(script, st.st_mode | stat.S_IEXEC)
            env = os.environ.copy()
            env.update(self.facts['env'])
            if 'env' in command:
                env.update(command['env'])
            process = Popen(" ".join(command['command']), shell=True, env=env, cwd=command['cwd'])
            process.communicate()
            if process.returncode:
                sys.exit(process.returncode)
        elif command['type'] == 'builtin':
            getattr(self, command['name'].replace("-", "_"))()

    @staticmethod
    def get_sandbox_from_path(path):
        path = os.path.abspath(path)
        segments = path.split('/')
        i = len(segments) - 1
        while i >= 0:
            m = STANDARD_NAME_PAT.match(segments[i])
            if m:
                return '/'.join(segments[0:i]), segments[i]
            i -= 1
        return None, None

    @staticmethod
    def parse_sandbox_name(name):
        """
        Split a sandbox name into its 3 constituent pieces (component, branch, task).
        Return a 3-tuple. Raises SandboxNameError if name is invalid.
        """
        m = STANDARD_NAME_PAT.match(name)
        if not m:
            raise SandboxNameError(name)
        return m.group(1), m.group(2), m.group(3)
