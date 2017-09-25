import os
import unittest
import subprocess
import tempfile
from vcs.vcsrepo import VcsRepo

config_dir = tempfile.TemporaryDirectory()
source_dir = tempfile.TemporaryDirectory()
repo = None
cwd = os.getcwd()


class TestGit(unittest.TestCase):

    def setUp(self):
        global config_dir
        global source_dir
        global repo
        config_dir = tempfile.TemporaryDirectory()
        source_dir = tempfile.TemporaryDirectory()
        repo = self.get_repo()

    @staticmethod
    def get_repo():
        global cwd
        tmp_file = os.path.join(source_dir.name, 'test.txt')
        with open(tmp_file, 'a'):
            os.utime(tmp_file, None)
        try:
            os.chdir(source_dir.name)
            subprocess.call(["git", "init"])
            subprocess.call(["git", "add", "test.txt"])
            # Allow pushing to this repo, normally we would expect this repo to be a bare repository
            subprocess.call(["git", "config", "receive.denyCurrentBranch", "ignore"])
            subprocess.call(["git", "config", "user.email", "'test@example.com'"])
            subprocess.call(["git", "config", "user.name", "Test User"])
            subprocess.call(["git", "commit", "--message", "test comment"])
            return VcsRepo.get_repo(path=config_dir.name, provider='git', source=source_dir.name)
        finally:
            os.chdir(cwd)

    def test_init(self):
        repo.init()
        assert os.path.exists(os.path.join(config_dir.name, 'test.txt'))
        assert repo.exists()

    def test_force_source_change(self):
        repo.init()
        good_source = repo.source
        os.chdir(config_dir.name)
        subprocess.call(["git", "config", "remote.origin.url", "bad_source"])
        assert repo.exists()
        p = subprocess.Popen(["git", "config", "--get", "remote.origin.url"], stdout=subprocess.PIPE)
        out = p.communicate()[0].decode()
        assert good_source in out

    def test_update(self):
        repo.init()
        os.chdir(source_dir.name)
        tmp_file = os.path.join(source_dir.name, 'test2.txt')
        with open(tmp_file, 'a'):
            os.utime(tmp_file, None)
        os.chdir(source_dir.name)
        subprocess.call(["git", "add", "test2.txt"])
        subprocess.call(["git", "commit", "--message", "'test'"])
        repo.update()
        assert os.path.exists(os.path.join(config_dir.name, 'test2.txt'))

    def test_publish_prep(self):
        repo.init()
        repo.publish_prep()
        assert not os.path.exists(os.path.join(config_dir.name, 'test.txt'))

    def test_head_commit(self):
        repo.init()
        commit = repo.get_head_commit()
        assert 'test comment' in commit

    def test_publish(self):
        repo.init()
        repo.publish_prep()
        tmp_file = os.path.join(config_dir.name, 'test2.txt')
        with open(tmp_file, 'a'):
            os.utime(tmp_file, None)
        repo.publish("commit message")
        os.chdir(source_dir.name)
        subprocess.call(["git", "reset", "--hard"])
        assert os.path.exists(os.path.join(source_dir.name, 'test2.txt'))

    def test_shallow_publish(self):
        repo = VcsRepo.get_repo(path=config_dir.name, provider='git', source=source_dir.name, type_='built')
        repo.init()
        repo.publish_prep()
        tmp_file = os.path.join(config_dir.name, 'test2.txt')
        with open(tmp_file, 'a'):
            os.utime(tmp_file, None)
        repo.publish("commit message")
        os.chdir(source_dir.name)
        subprocess.call(["git", "reset", "--hard"])
        assert os.path.exists(os.path.join(source_dir.name, 'test2.txt'))

    def test_branches(self):
        repo.init()
        os.chdir(source_dir.name)
        subprocess.call(["git", "checkout", "-b", "branch"])
        subprocess.call(["git", "checkout", "-b", "branch1"])
        subprocess.call(["git", "checkout", "-b", "branch2"])
        subprocess.call(["git", "checkout", "-b", "branch3"])
        branches = repo.branches()
        assert all(x in branches for x in ['master', 'branch', 'branch1', 'branch2', 'branch3'])

    def test_remote_head_revision(self):
        repo.init()
        rev_local = repo.get_head_revision()
        rev_remote = repo.get_remote_head_revision()
        assert rev_local
        assert rev_local == rev_remote

    def test_publish_branch(self):
        global cwd
        repo.init()
        os.chdir(source_dir.name)
        subprocess.call(["git", "checkout", "-b", "branch"])
        tmp_file = os.path.join(source_dir.name, 'branch.txt')
        with open(tmp_file, 'a'):
            os.utime(tmp_file, None)
        subprocess.call(["git", "add", "branch.txt"])
        subprocess.call(["git", "commit", "--message", "'branch'"])
        os.chdir(cwd)
        repo.checkout("branch")
        assert os.path.exists(os.path.join(config_dir.name, 'branch.txt'))
        repo.publish_prep()
        assert not os.path.exists(os.path.join(config_dir.name, 'branch.txt'))
        tmp_file = os.path.join(config_dir.name, 'test2.txt')
        with open(tmp_file, 'a'):
            os.utime(tmp_file, None)
        repo.publish("commit message")
        os.chdir(source_dir.name)
        subprocess.call(["git", "reset", "--hard"])
        assert os.path.exists(os.path.join(source_dir.name, 'test2.txt'))

