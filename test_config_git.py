import unittest
from nose.tools import assert_raises_regexp
from lib.exceptions import ConfigError
from lib.config import Config
from copy import deepcopy
import os
import tempfile
import copy
import json
import getpass


class TestConfig(unittest.TestCase):
    SAMPLE_CONFIG = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'test_files/sample_config.json')

    def test_local_configuration_validation(self):
        good_config = {
            'vcsrepo': {
                'path': '/tmp/conf',
                'source': '/tmp/repo',
                'revision': 'master',
                'provider': 'git'
            },
            'user': {
                'git': {'name': 'kim'},
                'bzr': {'name': 'kim.ebert'},
                'git-annex': {'name': 'kebert'}
            }
        }
        Config.validate_config(good_config, 'local')
        assert_raises_regexp(ConfigError, 'valid json', Config.validate_config, 'config', 'local')
        bad_config = copy.deepcopy(good_config)
        del bad_config['vcsrepo']['path']
        assert_raises_regexp(ConfigError, 'path.*required', Config.validate_config, bad_config, 'local')
        bad_config = copy.deepcopy(good_config)
        del bad_config['vcsrepo']['source']
        assert_raises_regexp(ConfigError, 'source.*required', Config.validate_config, bad_config, 'local')
        bad_config = copy.deepcopy(good_config)
        del bad_config['vcsrepo']['revision']
        assert_raises_regexp(ConfigError, 'revision.*required', Config.validate_config, bad_config, 'local')
        bad_config = copy.deepcopy(good_config)
        del bad_config['vcsrepo']['provider']
        assert_raises_regexp(ConfigError, 'provider.*required', Config.validate_config, bad_config, 'local')
        bad_config = copy.deepcopy(good_config)
        del bad_config['user']
        assert_raises_regexp(ConfigError, 'user.*required', Config.validate_config, bad_config, 'local')
        bad_config = copy.deepcopy(good_config)
        bad_config['user']['git'] = {'jim': 'bob'}
        assert_raises_regexp(ConfigError, 'name.*required', Config.validate_config, bad_config, 'local')
        good_config['user']['new_thing'] = {'name': 'bob'}
        Config.validate_config(good_config, 'local')
        good_config['user']['system_user'] = {'name': '$user'}
        Config.validate_config(good_config, 'local')

    def test_inject_variables_into_local_config(self):
        good_config = {
            'vcsrepo': {
                'path': '/tmp/conf',
                'source': '${system_user}@/tmp/repo',
                'revision': 'master',
                'provider': 'git'
            },
            'user': {
                'git': {'name': '${system_user}'},
                'bzr': {'name': 'kim.ebert'},
                'git-annex': {'name': 'kebert'}
            }
        }
        Config.validate_config(good_config, 'local')
        conf = Config.inject_variables_into_local_config(good_config)
        user = getpass.getuser()
        assert conf['vcsrepo']['source'] == '%s@/tmp/repo' % user
        assert conf['user']['git']['name'] == user

    def test_remote_configuration_validation(self):
        with open(self.SAMPLE_CONFIG, 'r') as config:
            configuration = json.loads(config.read())
        # Test the original object is valid
        Config.validate_config(configuration, 'remote')
        bad_config = copy.deepcopy(configuration)
        del bad_config['components'][0]['name']
        # Test the bad config throws a ConfigError with a good message
        assert_raises_regexp(ConfigError, "'name' is a required property",
                             Config.validate_config, bad_config, 'remote')

    def test_parse_config_error(self):
        temp_dir = tempfile.TemporaryDirectory()
        # Test if there is not remote config file
        assert_raises_regexp(ConfigError, 'config.json.*does not exist', Config.parse_config,
                             'config.json')
        # Test error is thrown if bad json
        config_file = os.path.join(temp_dir.name, 'config.json')

        with open(config_file, 'w') as file:
            file.write("this is not json")
        assert_raises_regexp(ConfigError, 'invalid json', Config.parse_config, file.name)

    def test_inject_variables(self):
        with open(self.SAMPLE_CONFIG, 'r') as config:
            configuration = json.loads(config.read())
        vcs_config = Config.validate_config(configuration, 'remote')
        users = {
            'git': {'name': 'kim'},
            'bzr': {'name': 'kim.ebert'},
            'git-annex': {'name': 'kebert'},
            'svn': {'name': 'kbert'}
        }
        aspects = Config.inject_variables_into_aspects(vcs_config['aspects'], 'ss', 'v12_release', 'x86-64', users, '/tmp')
        assert len(aspects) == 4
        assert [aspect for aspect in aspects if 'kim@' in aspect['vcsrepo']['source']][0]
        assert [aspect for aspect in aspects if 'kim.ebert@' in aspect['vcsrepo']['source']][0]
        assert [aspect for aspect in aspects if '/tmp/code/ss' in aspect['vcsrepo']['path']][0]
        assert [aspect for aspect in aspects if 'kebert@' in aspect['vcsrepo']['source']][0]
        assert [aspect for aspect in aspects if 'kbert@' in aspect['vcsrepo']['source']][0]
        assert [aspect for aspect in aspects if 'ss' in aspect['vcsrepo']['source']][0]
        assert [aspect for aspect in aspects if 'v12_release' in aspect['vcsrepo']['source']][0]
        assert [aspect for aspect in aspects if 'x86-64' in aspect['vcsrepo']['revision']][0]
        assert [aspect for aspect in aspects if 'v12_release' in aspect['vcsrepo']['revision']][0]
        aspects = Config.inject_variables_into_aspects(vcs_config['aspects'], 'ss', 'v12_release', 'all', users, '/tmp')
        assert len(aspects) == 10

    def test_get_aspects(self):
        with open(self.SAMPLE_CONFIG, 'r') as config:
            configuration = json.loads(config.read())
        vcs_config = Config.validate_config(configuration, 'remote')
        users = {
            'git': {'name': 'kim'},
            'bzr': {'name': 'kim.ebert'},
            'git-annex': {'name': 'kebert'},
            'svn': {'name': 'kbert'}
        }
        dependency_types = {
            "code": [
                "code",
                "test"
            ],
            "built": [
                "built",
                "test"
            ]
        }
        aspects = Config.get_aspects('SampleApp', vcs_config['components'], vcs_config['aspects'], dependency_types,
                                     'v12_release', 'x86-64', users, '/tmp')
        assert all(x in aspects.keys() for x in [
            'SampleApp',
            'SampleFramework',
            'SampleCppUnit',
            'cpp3p',
            'boost',
            'buildscripts'
        ])
        print(aspects)
        assert [aspect for aspect in aspects['SampleCppUnit'] if aspect['type'] == "code"
                and aspect['vcsrepo']['provider'] == "bzr"
                and aspect['vcsrepo']['source'] == "kim.ebert@192.0.2.100:/bzrroot/SampleCppUnit/code"
                and aspect['vcsrepo']['revision'] == "v12_release"
                ]
        assert [aspect for aspect in aspects['SampleCppUnit'] if aspect['type'] == "test"
                and aspect['vcsrepo']['provider'] == "svn"
                and aspect['vcsrepo']['source'] == "kbert@192.0.2.100:/svnroot/v12_release/SampleCppUnit/test"
                and aspect['vcsrepo']['revision'] == "HEAD"
                ]
        assert [aspect for aspect in aspects['boost'] if aspect['type'] == "built"
                and aspect['vcsrepo']['provider'] == "git-annex"
                and aspect['vcsrepo']['source'] == "kebert@192.0.2.100:/gitroot/boost/built"
                and aspect['vcsrepo']['revision'] == "v12_release-x86-64"
                ]
        assert [aspect for aspect in aspects['boost'] if aspect['type'] == "test"
                and aspect['vcsrepo']['provider'] == "svn"
                and aspect['vcsrepo']['source'] == "kbert@192.0.2.100:/svnroot/v12_release/boost/test"
                and aspect['vcsrepo']['revision'] == "HEAD"
                ]

    def test_clean_aspects(self):
        aspects = [
            {
                'vcsrepo': {'path': '/tmp/tmp3cun4nyh/ss.v74_release.dev/code/SampleFederator', 'revision': 'HEAD',
                            'source': 'bzr+ssh://joseph.pratt@192.0.2.100:20202/reporoot/v74_release/SampleFederator/code',
                            'provider': 'bzr'}, 'type': 'code', 'name': 'code'}, {
                'vcsrepo': {'path': '/tmp/tmp3cun4nyh/ss.v74_release.dev/test/SampleFederator', 'revision': 'HEAD',
                            'source': 'bzr+ssh://joseph.pratt@192.0.2.100:20202/reporoot/v74_release/SampleFederator/test',
                            'provider': 'bzr'}, 'type': 'test', 'name': 'test'}, {
                'vcsrepo': {'path': '/tmp/tmp3cun4nyh/ss.v74_release.dev/built.linux_x86-64/SampleFederator',
                            'revision': 'HEAD',
                            'source': 'bzr+ssh://joseph.pratt@192.0.2.100:20202/reporoot/v74_release/SampleFederator/built.linux_x86-64',
                            'provider': 'bzr'}, 'type': 'built', 'name': 'built'}, {
                'vcsrepo': {'path': '/tmp/tmp3cun4nyh/ss.v74_release.dev/test/SampleFederator', 'revision': 'HEAD',
                            'source': 'bzr+ssh://joseph.pratt@192.0.2.100:20202/reporoot/v74_release/SampleFederator/test',
                            'provider': 'bzr'}, 'type': 'test', 'name': 'test'}
        ]
        cleaned = Config.clean_aspects("SampleFederator", aspects)
        # Remove duplicate type and source combos
        assert len([a for a in cleaned if a['type'] == 'test']) == 1
        different_revision = deepcopy(aspects)
        different_revision.append({
            'vcsrepo': {'path': '/tmp/tmp3cun4nyh/ss.v74_release.dev/code/SampleFederator', 'revision': 'master',
                        'source': 'bzr+ssh://joseph.pratt@192.0.2.100:20202/reporoot/v74_release/SampleFederator/code',
                        'provider': 'bzr'}, 'type': 'code', 'name': 'code'})
        assert_raises_regexp(ConfigError, 'revisions.*master', Config.clean_aspects, 'SampleFederator', different_revision)
        different_source = deepcopy(aspects)
        different_source.append({
            'vcsrepo': {'path': '/tmp/tmp3cun4nyh/ss.v74_release.dev/code/SampleFederator', 'revision': 'HEAD',
                        'source': 'git+ssh://joseph.pratt@192.0.2.100:20202/reporoot/v74_release/SampleFederator/code',
                        'provider': 'bzr'}, 'type': 'code', 'name': 'code'})
        assert_raises_regexp(ConfigError, 'sources.*git', Config.clean_aspects, 'SampleFederator', different_source)
        different_provider = deepcopy(aspects)
        different_provider.append({
            'vcsrepo': {'path': '/tmp/tmp3cun4nyh/ss.v74_release.dev/code/SampleFederator', 'revision': 'HEAD',
                        'source': 'bzr+ssh://joseph.pratt@192.0.2.100:20202/reporoot/v74_release/SampleFederator/code',
                        'provider': 'git'}, 'type': 'code', 'name': 'code'})
        assert_raises_regexp(ConfigError, 'providers.*git', Config.clean_aspects, 'SampleFederator', different_provider)

    def test_combine_build_upto_deps(self):
       list1 = [
          [
             "dashboard-extension",
             "ui"
          ],
          [
             "perfectsearch-appliance",
             "data-warehouse-appliance"
          ],
          [
             "mpi",
             "clinical-reports-extension",
             "documentation",
             "CPC-extension",
             "implementation-tools-extension",
             "scorecard-extension"
          ],
          [
             "IMAT-reports"
          ],
          [
             "IMAT-product"
          ]
       ]

       list2 = [
           [
               "ui",
               "nlplib",
               "osconfig"
           ],
           [
               "compoundquery"
           ],
           [
               "webapp"
           ],
           [
               "generic-appliance"
           ],
           [
               "perfectsearch-appliance"
           ],
           [
               "appliance-product"
           ]
       ]

       combined = Config.combine_build_up_to_deps(list1, list2)
       assert len(combined) == 6
       assert len(combined[0]) == 4
       assert len(combined[1]) == 3
       assert len(combined[2]) == 7
       assert len(combined[3]) == 2
       assert len(combined[4]) == 2
       assert len(combined[5]) == 1
       assert Config.combine_build_up_to_deps([], []) == []
       combined = Config.combine_build_up_to_deps(list2, list1)
       assert len(combined) == 6
       assert len(combined[0]) == 4
       assert len(combined[1]) == 3
       assert len(combined[2]) == 7
       assert len(combined[3]) == 2
       assert len(combined[4]) == 2
       assert len(combined[5]) == 1

