import sqlite3
from pathlib import Path

from app.db.drivers.base import BaseDBDriver


class SQLiteDriver(BaseDBDriver):
    def query(self, sql, params):
        database = self.profile.get("database")
        if not database:
            raise ValueError("SQLite database path is not configured")

        path = Path(database)
        if not path.exists():
            return {
                "rows": [],
                "warning": f"SQLite database not found: {database}. Replace configs/db.json with real DB config or create demo data.",
            }

        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(sql, params)
            rows = [dict(row) for row in cursor.fetchall()]
            return {"rows": rows}
        finally:
            conn.close()

