from app.db.drivers.postgres_driver import PostgresDriver
from app.db.drivers.sqlite_driver import SQLiteDriver


def create_driver(profile):
    driver = (profile or {}).get("driver", "sqlite").lower()
    if driver == "sqlite":
        return SQLiteDriver(profile)
    if driver in {"postgres", "postgresql"}:
        return PostgresDriver(profile)
    raise ValueError(f"Unsupported DB driver: {driver}")
