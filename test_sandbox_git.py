import tempfile
from unittest.mock import Mock
import os
from lib.config import Config, REMOTE_CONF_NAME
from lib.sandbox import Sandbox
import subprocess
from unittest.mock import patch
from nose.tools import assert_raises_regexp
from lib.exceptions import CommandError
from include_config import IncludeConfig


class TestSandman(IncludeConfig):

    def test_sandbox_initialization(self):
        sandbox_name = "SampleApp.%s.test.1" % self.branch
        sandbox = Sandbox(self.base_dir.name, sandbox_name, self.config)
        assert sandbox.path == "%s/%s" % (self.base_dir.name, sandbox_name)
        assert sandbox.base_dir == self.base_dir.name
        assert sandbox.name == sandbox_name
        assert sandbox.facts['sandbox']['name'] == '^test.*'

        sandbox = Sandbox(self.base_dir.name, "SampleApp.%s.memcheck.1234" % self.branch, self.config)
        assert sandbox.facts['sandbox']['name'] == '^memcheck.*'

        # If it doesn't match any use the default
        sandbox = Sandbox(self.base_dir.name, "SampleApp.%s.347memcheck.1234" % self.branch, self.config)
        assert sandbox.facts['sandbox']['name'] == '^dev.*'

    @patch('lib.sandbox.Popen')
    @patch('lib.config.Config.clone_or_update_aspect')
    def test_init_with_dev_sandbox(self, mock_clone, mock_popen):
        process_mock = Mock()
        process_mock.configure_mock(**{'returncode': 0})
        mock_popen.return_value = process_mock
        sandbox = Sandbox(self.base_dir.name, "Sampleapp.%s.dev" % self.branch, self.config)
        sandbox.init()
        # 11 components 1 test and 1 code aspect for 22
        assert mock_clone.call_count == 22
        assert mock_popen.call_count == 2
        called_commands = TestSandman.parse_mock_popen(mock_popen)
        assert [c for c in called_commands if 'build.py --build-type Debug config' in c][0]
        assert [c for c in called_commands if 'check_tools.py' in c][0]
        sources, paths = TestSandman.parse_mock_clone(mock_clone)
        # ss is in the code and test aspect because all top components have code dependency type
        assert [s for s in sources if
                'v74_release/SampleApp/code' in s]
        assert [s for s in sources if
                'v74_release/SampleApp/test' in s]
        assert not [s for s in sources if
                    'v74_release/SampleApp/built.linux_x86-64' in s]
        # boost is in built and test because of the dev sandbox dependency type of built
        assert [s for s in sources if
                'v74_release/boost/built.linux_x86-64' in s]
        assert [s for s in sources if
                'v74_release/boost/test' in s]
        assert not [s for s in sources if
                    'v74_release/boost/code' in s]
        # snowball is in code and test because of the dev sandbox dependency type of code
        assert not [s for s in sources if
                    'v74_release/snowball/built.linux_x86-64' in s]
        assert [s for s in sources if
                'v74_release/snowball/test' in s]
        assert [s for s in sources if
                'v74_release/snowball/code' in s]
        # Also the paths are dynamic meaning they depend on the ${built} variable
        assert [p for p in paths if 'linux_x86-64' in p]
        legacy_file = os.path.join(sandbox.path, 'dependencies.txt')
        dependency_file = os.path.join(sandbox.path, 'dependency_tree.txt')
        build_count = 0
        for count, l in enumerate(open(legacy_file)):
            if 'linux_x86-64' in l:
                build_count += 1
        assert (count + 1) == 11
        assert build_count == 1
        build_count = 0
        for count, l in enumerate(open(dependency_file)):
            if 'linux_x86-64' in l:
                build_count += 1
        assert (count + 1) == 11
        assert build_count == 1

    @patch('lib.config.Config.clone_or_update_aspect')
    def test_publish_prep_with_test_sandbox(self, mock_vcs_update):
        sandbox = Sandbox(self.base_dir.name, 'ss.v74_release.official', self.config)
        sandbox.exe_command('publish-prep')

        # We cloned and updated twice
        assert mock_vcs_update.call_count == 1

        # We cloned the only built dependency and top aspect built
        sources, paths = TestSandman.parse_mock_clone(mock_vcs_update)
        assert len(sources) == 1
        assert len(paths) == 1
        assert 'v74_release/ss/built.linux_x86-64' in sources[0]
        assert 'ss.v74_release.official/built.linux_x86-64/ss' in paths[0]

        # We only called one call on that repo and that was publish_prep
        functions = TestSandman.functions_called_on_repo(mock_vcs_update)
        assert len(functions) == 1
        assert functions[0] == 'publish_prep'

    @patch('vcs.vcsrepo.VcsRepo.get_repo')
    def test_publish_fails_if_repo_does_not_exist(self, mock_get_repo):
        repo_mock = Mock()
        repo_mock.configure_mock(**{'exists.return_value': False})
        mock_get_repo.return_value = repo_mock

        sandbox = Sandbox(self.base_dir.name, 'ss.v74_release.official', self.config)
        publish_dir = os.path.join(sandbox.path, 'built.linux_x86-64', 'ss')
        # Mock publish-prep by creating empty folder
        os.makedirs(publish_dir)
        assert_raises_regexp(CommandError, 'no VCS repo', sandbox.exe_command, 'publish')

    @patch('lib.config.Config.clone_or_update_aspect')
    @patch('vcs.vcsrepo.VcsRepo.get_repo')
    def test_publish_with_test_sandbox(self, mock_get_repo, mock_vcs_update):
        sandbox = Sandbox(self.base_dir.name, 'ss.v74_release.official', self.config)
        publish_dir = os.path.join(sandbox.path, 'built.linux_x86-64', 'ss')
        # Mock publish-prep by creating empty folder
        os.makedirs(publish_dir)
        sandbox.exe_command('publish')

        # We didn't clone or update anything
        assert mock_vcs_update.call_count == 0

        # We used the correct repo
        # 1 for the repo to publish and 22 for dependencies needed in source.txt
        assert mock_get_repo.call_count == 23
        vcs_repo = mock_get_repo.call_args_list[0][1]
        assert 'ss.v74_release.official/built.linux_x86-64/ss' in vcs_repo['path']
        assert 'bzr' in vcs_repo['provider']
        assert 'v74_release/ss/built.linux_x86-64' in vcs_repo['source']

        # We only called exists, get_hidden_folder, and publish (in that order) on the publish repo
        functions = TestSandman.functions_called_on_repo(mock_get_repo)
        # the rest where get_head_revision on the dependencies for source.txt
        assert len(functions) == 25
        assert functions[0] == 'exists'
        assert functions[1] == 'get_hidden_folder'
        assert functions[2] == 'get_head_revision'
        assert functions[24] == 'publish'
        source_file = os.path.join(publish_dir, 'source.txt')
        assert os.path.isfile(source_file)
        for count, l in enumerate(open(source_file)):
            assert 'get_head_revision' in l
        assert count == 21
        manifest_file = os.path.join(publish_dir, 'manifest.txt')
        assert os.path.isfile(manifest_file)
        for count, l in enumerate(open(manifest_file)):
            assert 'Last published on ' in l
        assert count == 0
        conf_file = os.path.join(publish_dir, 'config.json')
        assert os.path.isfile(conf_file)

    def test_command_env_with_test_sandbox(self):
        sandbox = Sandbox(self.base_dir.name, 'SampleApp.v74_release.only_test', self.config)
        sandbox.facts['env']['TEST_DIR'] = sandbox.path
        sandbox.exe_command('test_command')
        command_output = os.path.join(sandbox.path, "file")
        assert os.path.isfile(command_output)
        with open(command_output, 'r') as f:
            contents = f.readline().replace("\n", "")
        assert contents == 'xyz'

    def test_script_env_with_test_sandbox(self):
        sandbox = Sandbox(self.base_dir.name, 'ss.v74_release.only_test', self.config)
        sandbox.facts['env']['TEST_DIR'] = sandbox.path
        script = os.path.join(sandbox.path, 'test.sh')
        os.mkdir(sandbox.path)
        with open(script, 'w') as f:
            f.write('echo $TEST_VAR > $TEST_DIR/file')
        sandbox.exe_command('test_script')
        command_output = os.path.join(sandbox.path, "file")
        assert os.path.isfile(command_output)
        with open(command_output, 'r') as f:
            contents = f.readline().replace("\n", "")
        assert contents == 'xyz'

    def test_get_sandbox_name_from_path(self):
        base_dir_, name = Sandbox.get_sandbox_from_path(
            '/home/user/sandboxes/ss.v712_release.dev/code/buildscripts/cmake/patches')
        assert base_dir_ == '/home/user/sandboxes'
        assert name == 'ss.v712_release.dev'
        base_dir_, name = Sandbox.get_sandbox_from_path(
            '/home/user/sandboxes/not_a_sandbox/code/buildscripts/cmake/patches')
        assert base_dir_ is None
        assert name is None

    def test_command_override(self):
        sandbox = Sandbox(self.base_dir.name, "sandman2.cm_tools.dev", self.config)
        override_commands = [c for c in sandbox.facts['commands'] if c['name'] == 'init_config']
        # The command old command was removed.
        assert len(override_commands) == 1
        # The override worked
        assert override_commands[0]['command'][0] == 'echo'
        # The other sandbox commands are included.
        assert len(sandbox.facts['commands']) > 1
        # Make sure there is not an error when we reference a report aspect and not defined in component
        sandbox = Sandbox(self.base_dir.name, "sandman2.cm_tools.only_test", self.config)

    @patch('lib.sandbox.Popen')
    @patch('lib.config.Config.clone_or_update_aspect')
    def test_dependency_files(self, mock_clone, mock_popen):
        process_mock = Mock()
        process_mock.configure_mock(**{'returncode': 0})
        mock_popen.return_value = process_mock
        sandbox = Sandbox(self.base_dir.name, 'dashboard-extension.%s.dev' % self.branch, self.config)
        sandbox.init()
        legacy_file = os.path.join(sandbox.path, 'dependencies.txt')
        dependency_file = os.path.join(sandbox.path, 'dependency_tree.txt')
        build_count = 0
        for count, l in enumerate(open(legacy_file)):
            if 'linux_x86-64' in l:
                build_count += 1
        assert (count + 1) == 27
        assert build_count == 23
        build_count = 0
        terminal_count = 0
        for count, l in enumerate(open(dependency_file)):
            if 'built' in l:
                build_count += 1
            if 'terminal' in l:
                terminal_count += 1
        assert count == 27
        assert build_count == 23
        assert terminal_count == 6
        code_deps = [a['name'] for a in sandbox.facts['aspects'] if 'code' == a['type']]
        assert len(code_deps) == 4
        assert 'dashboard-extension' in code_deps
        assert 'dashboard-ui' in code_deps
        assert 'ps-angular' in code_deps
        assert 'buildscripts' in code_deps
        built_deps = [a['name'] for a in sandbox.facts['aspects'] if 'built' == a['type']]
        assert len(built_deps) == 23
        test_deps = [a['name'] for a in sandbox.facts['aspects'] if 'test' == a['type']]
        assert len(test_deps) == 27

    @patch('lib.sandbox.Popen')
    @patch('lib.config.Config.clone_or_update_aspect')
    def test_modified_we_overcome_cache_conflicts(self, mock_clone, mock_popen):
        process_mock = Mock()
        process_mock.configure_mock(**{'returncode': 0})
        mock_popen.return_value = process_mock
        # Admin modifies the config
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            subprocess.call(["git", "init"])
            subprocess.call(["git", "remote", "add", "origin", self.source_dir.name])
            subprocess.call(["git", "pull"])
            subprocess.call(["git", "checkout", self.branch])
            with open(REMOTE_CONF_NAME, mode='a') as f:
                f.write("I'm messing with the remote config.")
            subprocess.call(["git", "commit", "-a", "-m", "modified remote cache"])
            subprocess.call(["git", "push"])

            os.chdir(self.config_dir.name)
            subprocess.call(["git", "checkout", self.branch])
            with open(REMOTE_CONF_NAME, mode='a') as f:
                f.write("I'm messing with the cached config.")
            subprocess.call(["git", "commit", "-a", "-m", "modified cached config"])
            local_config = {
                'vcsrepo': {
                    'path': self.config_dir.name,
                    'source': self.source_dir.name,
                    'revision': self.branch,
                    'provider': 'git'
                },
                'user': {
                    'bzr': {'name': 'user'},
                    'git': {'name': 'git-user'}
                }
            }
            Config.reset_config()
            # If this doesn't through a conflict error that is good
            Config.get_config(configuration=local_config)
            os.chdir(temp_dir)
            subprocess.call(["git", "reset", "--hard", "HEAD^"])
            subprocess.call(["git", "push", "-f"])

    @patch('vcs.vcsrepo.VcsRepo.get_repo')
    def test_get_build_up_to_deps(self, mock_get_repo):
        repo_mock = Mock()
        repo_mock.configure_mock(**{'get_remote_head_revision.return_value': None,
                                    'get_sources.return_value': [{'name': 'ss', 'type': 'built', 'revision': 'jklf23j4ljk'}],
                                    })
        mock_get_repo.return_value = repo_mock
        sandbox = Sandbox(self.base_dir.name, 'appliance-product.%s.dev' % self.branch, self.config)
        deps = self.config.get_build_up_to_deps(sandbox.top, sandbox.facts)
        assert len(deps) == 6
        assert len(deps[0]) == 15
        assert len(deps[1]) == 1
        assert len(deps[2]) == 1
        assert len(deps[3]) == 1
        assert len(deps[4]) == 1
        assert len(deps[5]) == 1
        assert deps[1][0] == 'compoundquery'
        assert deps[2][0] == 'webapp'
        assert deps[3][0] == 'generic-appliance'
        assert deps[4][0] == 'perfectsearch-appliance'
        assert deps[5][0] == 'appliance-product'

    # Need this test because ant build iterate expects dependencies.txt to be in dependency order
    @patch('lib.sandbox.Popen')
    @patch('lib.config.Config.clone_or_update_aspect')
    def test_dependency_order(self, mock_clone, mock_popen):
        process_mock = Mock()
        process_mock.configure_mock(**{'returncode': 0})
        mock_popen.return_value = process_mock
        for i in range(10):
            sandbox = Sandbox(self.base_dir.name, "feeder.%s.dev" % self.branch, self.config)
            sandbox.init()
            legacy_file = os.path.join(sandbox.path, 'dependencies.txt')
            psjbase_line = 100000
            feeder_line = 0
            for count, l in enumerate(open(legacy_file)):
                if 'psjbase' in l:
                    psjbase_line = count
                if 'feeder' in l:
                    feeder_line = count
            assert feeder_line > psjbase_line
            sandbox.remove()

    # def test_only_if_updating_local_source(self):
    #     sandbox = Sandbox(self.base_dir.name, 'ss.v73_release.only_test', self.config)
    #     assert 'only_test' not in sandbox.facts['sandbox']['name']
    #     sandbox = Sandbox(self.base_dir.name, 'ss.%s.only_test' % self.branch, self.config)
    #     assert 'only_test' not in sandbox.facts['sandbox']['name']
    #     sandbox = Sandbox(self.base_dir.name, "sandman2.cm_tools.dev", self.config)
    #     override_commands = [c for c in sandbox.facts['commands'] if c['name'] == 'init_config']
    #     # The command old command was removed.
    #     assert len(override_commands) == 1
    #     # The override worked
    #     assert override_commands[0]['command'][0] == 'echo'
    #     # The other sandbox commands are included.
    #     assert len(sandbox.facts['commands']) > 1

    # @nottest
    # # TODO: find a way to capture STDOUT
    # def test_status_with_test_sandbox(self):
    #     sandbox = Sandbox(self.base_dir.name, 'ss.v74_release.test', self.config)
    #     sandbox.init()
    #     sandbox.status()
    #     sandbox.missing()
