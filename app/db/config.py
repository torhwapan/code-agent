import json
import os
from pathlib import Path


class DBConfig:
    def __init__(self, config_path="configs/db.json"):
        self.path = Path(config_path)
        self.data = self._load()
        self.profile_name = os.getenv("DB_PROFILE") or self.data.get("active_profile")
        self.profile = self.data.get("profiles", {}).get(self.profile_name, {})
        self.profile = self._resolve_env_values(self.profile)
        self.queries = self.data.get("queries", {})

    def get_query(self, query_id):
        if query_id not in self.queries:
            raise ValueError(f"Unknown query template: {query_id}")
        return self.queries[query_id]

    def _load(self):
        if not self.path.exists():
            return {"profiles": {}, "queries": {}}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _resolve_env_values(self, value):
        if isinstance(value, dict):
            return {key: self._resolve_env_values(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._resolve_env_values(item) for item in value]
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            env_name = value[2:-1]
            return os.getenv(env_name, "")
        return value
