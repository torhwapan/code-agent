from app.db.config import DBConfig
from app.db.drivers import create_driver


class DBQueryTool:
    def __init__(self, config=None):
        self.config = config or DBConfig()
        self.driver = create_driver(self.config.profile)

    def run_query(self, query_id, params):
        query = self.config.get_query(query_id)
        self._validate_params(query, params)

        return self.driver.query(query["sql"], params)

    def _validate_params(self, query, params):
        missing = []
        for name in query.get("params", []):
            if name not in params or params[name] in (None, ""):
                missing.append(name)
        if missing:
            raise ValueError(f"Missing query params: {', '.join(missing)}")

