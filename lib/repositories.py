from lib.config import Config


class Repositories:
    def __init__(self, config=None):
        if not config:
            self.config = Config.get_config()
        else:
            self.config = config
        self.build_type = "all"
        self.dep_types = {
            "code": [
                "code",
                "test",
                "report"
            ],
            "built": [
                "built"
            ]
        }

    def get_build_info(self):
        return self.config.get_build_info(self.build_type, self.dep_types)

    def get_repository_changesets(self, branch):
        return self.config.get_repository_changesets(self.build_type, self.dep_types, branch)
