import importlib
import re

from app.db.drivers.base import BaseDBDriver


class PostgresDriver(BaseDBDriver):
    def query(self, sql, params):
        module = self._load_driver_module()
        converted_sql = self._convert_named_params(sql)
        conn = self._connect(module)
        try:
            cursor = conn.cursor()
            cursor.execute(converted_sql, params)
            if not cursor.description:
                self._commit_if_needed(conn)
                return {"rows": [], "rowcount": cursor.rowcount}

            columns = [item[0] for item in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
            return {"rows": rows}
        finally:
            conn.close()

    def _load_driver_module(self):
        driver_module = self.profile.get("driver_module")
        if driver_module:
            return importlib.import_module(driver_module)

        try:
            import psycopg

            return psycopg
        except ImportError:
            try:
                import psycopg2

                return psycopg2
            except ImportError as exc:
                raise RuntimeError("Postgres driver is not installed. Run: pip install psycopg[binary]") from exc

    def _connect(self, module):
        kwargs = {
            "host": self.profile.get("host"),
            "port": int(self.profile.get("port", 5432)),
            "dbname": self.profile.get("database") or self.profile.get("dbname"),
            "user": self.profile.get("username") or self.profile.get("user"),
            "password": self.profile.get("password", ""),
            "connect_timeout": int(self.profile.get("connect_timeout", 10)),
        }
        optional_keys = ["sslmode", "application_name", "options"]
        for key in optional_keys:
            if self.profile.get(key):
                kwargs[key] = self.profile[key]

        kwargs = {key: value for key, value in kwargs.items() if value not in (None, "")}
        conn = module.connect(**kwargs)
        if self.profile.get("autocommit", True):
            conn.autocommit = True
        return conn

    def _convert_named_params(self, sql):
        # Project SQL templates use :name, while psycopg/psycopg2 use %(name)s.
        # The negative lookbehind avoids converting PostgreSQL casts such as ::text.
        return re.sub(r"(?<!:):([A-Za-z_][A-Za-z0-9_]*)", r"%(\1)s", sql)

    def _commit_if_needed(self, conn):
        if not getattr(conn, "autocommit", False):
            conn.commit()
