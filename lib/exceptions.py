class SandmanException(Exception):
    def __init__(self):
        raise NotImplemented()


class SandboxNameError(SandmanException):
    """SandmanException raised when a sandbox name doesn't match correct Regex
    """
    def __init__(self, name):
        self.message = "The name '%s' must contain 3 strings separated by periods." % name

    def __str__(self):
        return self.message


class SandboxExistsError(SandmanException):
    """SandmanException raised when a sandbox already exists
    """
    def __init__(self, sandbox, base_dir):
        self.message = "The sandbox with name '%s' already exists in %s." % (sandbox, base_dir)

    def __str__(self):
        return self.message


class SandboxNotExistsError(SandmanException):
    """SandmanException raised when a sandbox does not exists
    """
    def __init__(self, sandbox, base_dir):
        self.message = "The sandbox with name '%s' doesn't exists in %s. Please use the init method." % (sandbox, base_dir)

    def __str__(self):
        return self.message


class ConfigError(SandmanException):
    """SandmanException raised when there is a problem with the configuration
    """
    def __init__(self, m):
        self.message = m

    def __str__(self):
        return self.message


class CommandError(SandmanException):
    """SandmanException raised when there is a problem with running a command
    """
    def __init__(self, m):
        self.message = m

    def __str__(self):
        return self.message


class VcsError(SandmanException):
    """SandmanException raised when there is a problem executing Vcs commands

    Attributes:
         m -- the message of the problem
    """
    def __init__(self, message, path, source, revision):
        self.message = "%s in %s with source %s and revision %s" % (message, path, source, revision)

    def __str__(self):
        return self.message
