from vcs.git import Git
from vcs.bzr import Bzr


class VcsRepo:

    @staticmethod
    def get_repo(path, provider, source, revision='master', type_='code'):
        if provider == 'git':
            return Git(path, source, revision, type_)
        elif provider == 'bzr':
            return Bzr(path, source, revision, type_)
        else:
            raise ValueError("Provider '%s' is not supported" % provider)
