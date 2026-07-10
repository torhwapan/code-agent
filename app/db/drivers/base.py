class BaseDBDriver:
    def __init__(self, profile):
        self.profile = profile or {}

    def query(self, sql, params):
        raise NotImplementedError

