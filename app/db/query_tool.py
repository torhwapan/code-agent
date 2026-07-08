import sqlite3
from pathlib import Path

from app.db.config import DBConfig


class DBQueryTool:
    def __init__(self, config=None):
        self.config = config or DBConfig()

    def run_query(self, query_id, params):
        query = self.config.get_query(query_id)
        self._validate_params(query, params)

        driver = self.config.profile.get("driver", "sqlite")
        if driver == "sqlite":
            return self._run_sqlite(query["sql"], params)

        raise ValueError(f"Unsupported DB driver for first version: {driver}")

    def _validate_params(self, query, params):
        missing = []
        for name in query.get("params", []):
            if name not in params or params[name] in (None, ""):
                missing.append(name)
        if missing:
            raise ValueError(f"Missing query params: {', '.join(missing)}")

    def _run_sqlite(self, sql, params):
        database = self.config.profile.get("database")
        if not database:
            raise ValueError("SQLite database path is not configured")

        path = Path(database)
        if not path.exists():
            return {
                "rows": [],
                "warning": f"SQLite database not found: {database}. Replace configs/db.json with real DB config or create demo data."
            }

        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(sql, params)
            rows = [dict(row) for row in cursor.fetchall()]
            return {"rows": rows}
        finally:
            conn.close()
