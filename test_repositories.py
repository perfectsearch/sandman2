from include_config import IncludeConfig
from lib.repositories import Repositories
from unittest.mock import patch
from unittest.mock import Mock
from nose.tools import nottest


class TestRepositories(IncludeConfig):

    @patch('vcs.bzr.Popen')
    @patch('vcs.git.Popen')
    @patch('subprocess.check_call')
    @nottest
    def test_sandbox_initialization(self, mock_sub_call, mock_git, mock_bzr):
        repo_mock = Mock()
        repo_mock.configure_mock(**{'exists.return_value': False,
                                    'communicate.return_value': (bytearray("origin/cm_tools\n".encode()), ""),
                                    })
        mock_bzr.return_value = repo_mock
        mock_git.return_value = repo_mock
        repositories = Repositories(config=self.config)
        repositories.get_repository_changesets("cm_tools")
        TestRepositories.parse_mock_popen(mock_bzr)
        build_info = repositories.get_build_info()
        pass
