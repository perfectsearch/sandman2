import os


class Vcs:
    def __init__(self, path, source, revision='master', type_='code'):
        self.path = os.path.abspath(path)
        self.source = source
        self.revision = revision
        self.type = type_

    def checkout(self, branch):
        raise NotImplementedError()

    def exists(self):
        raise NotImplementedError()

    def get_head_commit(self):
        raise NotImplementedError()

    def get_head_revision(self):
        raise NotImplementedError()

    def get_remote_head_revision(self):
        raise NotImplementedError()

    def get_sources(self):
        raise NotImplementedError()

    def get_hidden_folder(self):
        raise NotImplementedError()

    def init(self):
        raise NotImplementedError()

    def publish_prep(self):
        raise NotImplementedError()

    def print_missing(self):
        raise NotImplementedError()

    def print_status(self):
        raise NotImplementedError()

    def publish(self, commit_message):
        raise NotImplementedError()

    def branches(self):
        raise NotImplementedError()

    def remove(self):
        os.removedirs(self.path)

    def update(self):
        raise NotImplementedError()

    def force_update(self):
        raise NotImplementedError()
