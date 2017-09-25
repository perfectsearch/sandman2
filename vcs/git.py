from vcs import Vcs
import os
import subprocess
import shutil
from lib.exceptions import VcsError
from subprocess import Popen


class Git(Vcs):
    def checkout(self, branch):
        cwd = os.getcwd()
        try:
            os.chdir(self.path)
            subprocess.check_call(["git", "reset", "--hard", "--quiet"], stdout=subprocess.DEVNULL)
            subprocess.check_call(["git", "fetch", "--quiet"], stdout=subprocess.DEVNULL)
            subprocess.check_call(["git", "checkout", "--quiet", branch], stdout=subprocess.DEVNULL)
            self.revision = branch
        finally:
            os.chdir(cwd)

    def exists(self):
        cwd = os.getcwd()
        try:
            exists = os.path.exists(os.path.join(self.path, '.git'))
            if exists:
                os.chdir(self.path)
                p = Popen(["git", "config", "--get", "remote.origin.url"], stdout=subprocess.PIPE)
                out = p.communicate()[0].decode()
                if self.source not in out:
                    subprocess.check_call(["git", "config", "remote.origin.url", self.source], stdout=subprocess.DEVNULL)
        finally:
            os.chdir(cwd)
        return exists

    def get_head_commit(self):
        cwd = os.getcwd()
        rev = None
        if not os.path.isdir(self.path):
            return None
        try:
            os.chdir(self.path)
            p = Popen(["git", "log", '-1', "--format=%h: %an %ad %s", "--date=short"], stdout=subprocess.PIPE)
            stdout = p.communicate()[0].decode().replace('\n', ' ')
            if stdout:
                return stdout
        finally:
            os.chdir(cwd)
        return rev

    def get_sources(self):
        p = Popen(["git", "archive", "--remote=%s" % self.source, self.revision, 'source.txt'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        output = subprocess.check_output(('tar', '-xOf', '-'), stdin=p.stdout)
        p.wait()
        stdout = output.decode()
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

    def get_head_revision(self):
        cwd = os.getcwd()
        rev = None
        try:
            os.chdir(self.path)
            p = Popen(["git", "rev-parse", "HEAD"], stdout=subprocess.PIPE)
            rev = p.communicate()[0].decode().replace('\n', '')
        finally:
            os.chdir(cwd)
        return rev

    def get_remote_head_revision(self):
        rev = None
        p = Popen(["git", "ls-remote", self.source], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        out = p.communicate()[0].decode()
        for line in out.split('\n'):
            if self.revision in line:
                return line.split('\t')[0]
        return rev

    def get_hidden_folder(self):
        return '.git'

    def init(self):
        try:
            os.makedirs(self.path, exist_ok=True)
        except PermissionError as e:
            raise VcsError(e, self.path, self.source, self.revision)
        if self.type == 'built':
            subprocess.check_call(["git", "clone", "--depth", "1", "--quiet", "-b", self.revision, self.source, self.path], stdout=subprocess.DEVNULL)
        else:
            subprocess.check_call(["git", "clone", "--quiet", "-b", self.revision, self.source, self.path], stdout=subprocess.DEVNULL)

    def update(self):
        cwd = os.getcwd()
        try:
            os.chdir(self.path)
            subprocess.check_call(["git", "pull", "--quiet"], stdout=subprocess.DEVNULL)
        finally:
            os.chdir(cwd)

    def force_update(self):
        cwd = os.getcwd()
        try:
            os.chdir(self.path)
            subprocess.check_call(["git", "reset", "--hard", "--quiet"], stdout=subprocess.DEVNULL)
            subprocess.check_call(["git", "pull", "--quiet"], stdout=subprocess.DEVNULL)
        finally:
            os.chdir(cwd)

    def publish_prep(self):
        cwd = os.getcwd()
        try:
            os.chdir(self.path)
            for path in os.listdir(self.path):
                if path == '.git':
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
            subprocess.check_call(["git", "fetch", "--quiet"], stdout=subprocess.DEVNULL)
            p = Popen(["git", "log", "HEAD..origin/%s" % self.revision], stdout=subprocess.PIPE)
            out = p.communicate()[0].decode()
            if out:
                print("Missing for %s:\n" % self.path)
                print(out)
        finally:
            os.chdir(cwd)

    def print_status(self):
        cwd = os.getcwd()
        try:
            os.chdir(self.path)
            p = Popen(["git", "status"], stdout=subprocess.PIPE)
            out = p.communicate()[0].decode()
            if 'working directory clean' not in out:
                print("Status for %s:\n" % self.path)
                print(out)
                return True
        finally:
            os.chdir(cwd)
        return False

    def publish(self, commit_message):
        cwd = os.getcwd()
        try:
            os.chdir(self.path)
            ignore_file = open('.gitignore', 'w')
            ignore_type = ['*.obj\n', '*.o\n', '*.pdb\n', '*.a\n', 'CMakeFiles\n']
            ignore_file.writelines(ignore_type)
            ignore_file.close()

            subprocess.check_call(["git", "add", "--all"], stdout=subprocess.DEVNULL)
            subprocess.check_call(["git", "commit", "-a", "--message", commit_message], stdout=subprocess.DEVNULL)
            subprocess.check_call(["git", "push", "origin", self.revision], stdout=subprocess.DEVNULL)
        finally:
            os.chdir(cwd)

    def branches(self):
        branches = []
        cwd = os.getcwd()
        try:
            os.chdir(self.path)
            subprocess.check_call(["git", "reset", "--hard", "--quiet"], stdout=subprocess.DEVNULL)
            subprocess.check_call(["git", "fetch", "--quiet"], stdout=subprocess.DEVNULL)
            p = Popen(["git", "branch", "-r"], stdout=subprocess.PIPE)
            out, err = p.communicate()
            out = out.decode("utf-8").replace('\r', '')

            for branch in out.split('\n'):
                branch = branch.strip()
                if '->' in branch:
                    continue
                if branch.startswith('origin/'):
                    branches.append(branch.replace('origin/', ''))

        finally:
            os.chdir(cwd)
        return branches

