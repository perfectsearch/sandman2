from vcs import Vcs
import os
import subprocess
import shutil
from subprocess import Popen


class Bzr(Vcs):

    def checkout(self, branch):
        raise NotImplementedError

    def exists(self):
        return os.path.exists(os.path.join(self.path, '.bzr'))

    def get_head_commit(self):
        cwd = os.getcwd()
        rev = None
        if not os.path.isdir(self.path):
            return None
        try:
            os.chdir(self.path)
            p = Popen(["bzr", "log", "--log-format=line", '-l', '1'], stdout=subprocess.PIPE)
            stdout = p.communicate()[0].decode().replace('\n', ' ')
            if stdout:
                return stdout
        finally:
            os.chdir(cwd)
        return rev

    def get_head_revision(self):
        cwd = os.getcwd()
        rev = None
        if not os.path.isdir(self.path):
            return None
        try:
            os.chdir(self.path)
            p = Popen(["bzr", "version-info", "--custom", '--template=revno={revno},revision_id={revision_id}'], stdout=subprocess.PIPE)
            stdout = p.communicate()[0].decode()
            if stdout:
                return stdout
        finally:
            os.chdir(cwd)
        return rev

    def get_remote_head_revision(self):
        rev = None
        p = Popen(["bzr", "revision-info", "-d", self.source], stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL)
        stdout = p.communicate()[0].decode()
        for l in stdout.split('\n'):
            data = l.split(' ')
            # If data[1] == 'null:' the repo exists but there are no commits
            if len(data) > 1 and data[1] != 'null:':
                return data[1]
        return rev

    def get_sources(self):
        p = Popen(["bzr", "cat", "%s/%s" % (self.source, 'source.txt')], stdout=subprocess.PIPE,
                  stderr=subprocess.DEVNULL)
        stdout = p.communicate()[0].decode()
        sources = []
        for l in stdout.split('\n'):
            if l.find(': ') == -1:
                continue
            comp_type, revision = l.split(': ')
            if comp_type.find('.') == -1:
                continue
            data = comp_type.split('.')
            comp = data[0]
            type_ = data[1]
            sources.append({'name': comp, 'type': type_, 'revision': revision})
        return sources

    def get_hidden_folder(self):
        return '.bzr'

    def init(self):
        os.makedirs(self.path, exist_ok=True)
        if self.type == 'built':
            subprocess.check_call(["bzr", "checkout", "--lightweight", self.source, self.path],
                                  stdout=subprocess.DEVNULL)
        else:
            subprocess.check_call(["bzr", "branch", "--standalone", "--use-existing-dir", self.source, self.path],
                                  stdout=subprocess.DEVNULL)
        subprocess.check_call(["bzr", "config", "-d", self.path, "push_location=%s" % self.source],
                              stdout=subprocess.DEVNULL)
        subprocess.check_call(["bzr", "config", "-d", self.path, "submit_location=%s" % self.source],
                              stdout=subprocess.DEVNULL)

    def update(self):
        cwd = os.getcwd()
        try:
            os.chdir(self.path)
            if self.type == 'built':
                subprocess.check_call(["bzr", "update"], stdout=subprocess.DEVNULL)
            else:
                subprocess.check_call(["bzr", "pull", self.source], stdout=subprocess.DEVNULL)
        finally:
            os.chdir(cwd)

    def force_update(self):
        cwd = os.getcwd()
        try:
            os.chdir(self.path)
            subprocess.check_call(["bzr", "revert"], stdout=subprocess.DEVNULL)
            subprocess.check_call(["bzr", "pull", self.source], stdout=subprocess.DEVNULL)
        finally:
            os.chdir(cwd)

    def publish_prep(self):
        cwd = os.getcwd()
        try:
            os.chdir(self.path)
            for path in os.listdir(self.path):
                if path == '.bzr':
                    continue
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
        finally:
            os.chdir(cwd)

    def print_missing(self):
        cwd = os.getcwd()
        try:
            os.chdir(self.path)
            p = Popen(["bzr", "missing"], stdout=subprocess.PIPE)
            out = p.communicate()[0].decode()
            if 'up to date' not in out:
                print("Missing for %s:" % self.path)
                print(out)
        finally:
            os.chdir(cwd)

    def print_status(self):
        p = Popen(["bzr", "status", self.path], stdout=subprocess.PIPE)
        out = p.communicate()[0].decode()
        if out:
            print("Status for %s:" % self.path)
            print(out)
            return True
        return False

    def publish(self, commit_message):
        cwd = os.getcwd()
        try:
            os.chdir(self.path)
            ignore_file = open('.bzrignore', 'w')
            ignore_type = ['*.obj\n', '*.o\n', '*.pdb\n', '*.a\n', 'CMakeFiles\n']
            ignore_file.writelines(ignore_type)
            ignore_file.close()

            subprocess.check_call(["bzr", "add", "."], stdout=subprocess.DEVNULL)
            subprocess.check_call(["bzr", "commit", "-m", commit_message], stdout=subprocess.DEVNULL)
            subprocess.check_call(["bzr", "push", self.source], stdout=subprocess.DEVNULL)
        finally:
            os.chdir(cwd)

    def branches(self):
        raise NotImplementedError
