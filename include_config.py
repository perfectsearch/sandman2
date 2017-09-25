import tempfile
import os
import unittest
from lib.config import Config
import subprocess
import shutil
import json
import ssl
import urllib.request


class IncludeConfig(unittest.TestCase):
    SAMPLE_CONFIG = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'test_files/sample_config.json')

    def __init__(self, *args, **kwargs):
        super(IncludeConfig, self).__init__(*args, **kwargs)
        self.config_dir = tempfile.TemporaryDirectory()
        self.source_dir = tempfile.TemporaryDirectory()
        self.base_dir = tempfile.TemporaryDirectory()
        self.config = None
        self.cwd = os.getcwd()
        self.branch = 'v74_release'

    def setUp(self):
        self.config_dir = tempfile.TemporaryDirectory()
        self.source_dir = tempfile.TemporaryDirectory()
        self.base_dir = tempfile.TemporaryDirectory()
        self.config = self.get_config()

    @staticmethod
    def commit_json_as_config(config_file, configuration):
        with open(config_file, 'w') as c_file:
            c_file.write(json.dumps(configuration, indent=3))
        subprocess.call(['git', 'add', '*'])
        subprocess.call(['git', 'commit', '--message', "add %s" % 'config.json'])

    def commit_all_branches(self, dependency_conf, official_conf):
        with open(dependency_conf, 'r') as config_file:
            configuration = json.loads(config_file.read())
        for b in configuration.keys():
            if b == self.branch or b == "cm_tools":
                subprocess.call(['git', 'checkout', b])
            else:
                subprocess.call(['git', 'checkout', '-b', b])
            branch_conf = Config.convert_dependency_config(dependency_conf, b)
            # Remove test branches
            branch_conf['commands'] = [c for c in branch_conf['commands'] if
                                       c['name'] != 'test_command' and c['name'] != 'test_script']
            branch_conf['sandbox_types'] = [t for t in branch_conf['sandbox_types'] if 'only_test' not in t['name']]
            if b == "cm_tools":
                branch_conf = Config.add_sandman_component(branch_conf)
            if b == "v73_release":
                branch_conf = Config.add_ps_selinux_component(branch_conf)
            Config.validate_config(branch_conf, 'remote')
            IncludeConfig.commit_json_as_config(official_conf, branch_conf)
        subprocess.call(['git', 'checkout', '-b', 'master'])

    def update_local_source(self):
        source = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../sandman-config')
        shutil.rmtree(source, ignore_errors=True)
        shutil.copytree(self.source_dir.name, source)

    def get_config(self):
        Config.reset_config()
        try:
            os.chdir(self.source_dir.name)
            subprocess.call(["git", "init", "--bare"])
            subprocess.call(["git", "config", "receive.denyCurrentBranch", "ignore"])
            temp_dir = tempfile.TemporaryDirectory()
            os.chdir(temp_dir.name)
            subprocess.call(["git", "init"])
            subprocess.call(["git", "remote", "add", "origin", self.source_dir.name])
            # Allow pushing to this repo, normally we would expect this repo to be a bare repository
            subprocess.call(["git", "config", "user.email", "'test@example.com'"])
            subprocess.call(["git", "config", "user.name", "Test User"])
            # In case you want to update the dependencies
            # IncludeConfig.update_dependencies()
            build_type_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_files/build_type.py')
            shutil.copy(build_type_script, temp_dir.name)
            official_conf = os.path.join(temp_dir.name, 'config.json')

            with open(self.SAMPLE_CONFIG, 'r') as config:
                configuration = json.loads(config.read())

            subprocess.call(['git', 'checkout', '-b', self.branch])
            IncludeConfig.commit_json_as_config(official_conf,configuration)# TODO fixme. This code is broken.
            subprocess.call(["git", "push", "origin", "--all"])
        finally:
            os.chdir(self.cwd)
        local_config = {
            'vcsrepo': {
                'path': self.config_dir.name,
                'source': self.source_dir.name,
                'revision': self.branch,
                'provider': 'git'
            },
            'user': {
                'bzr': {'name': 'user'},
                'kimbzr': {'name': 'user'},
                'git': {'name': 'git-user'}
            }
        }
        return Config.get_config(configuration=local_config)

    @staticmethod
    def functions_called_on_repo(mock_clone):
        calls = []
        for call in mock_clone.return_value.method_calls:
            function, args, kwargs = call
            calls.append(function)
        return calls

    @staticmethod
    def parse_mock_clone(mock_clone):
        sources = []
        paths = []
        for call in mock_clone.call_args_list:
            args, kwargs = call
            sources.append(args[0]['vcsrepo']['source'])
            paths.append(args[0]['vcsrepo']['path'])
        return sources, paths

    @staticmethod
    def parse_mock_popen(mock_script):
        called_commands = []
        for call in mock_script.call_args_list:
            args, kwargs = call
            command = args[0]
            if 'env' in kwargs:
                for k, v in kwargs['env'].items():
                    command = command.replace("$%s" % k, v)
            called_commands.append(command)
        return called_commands
