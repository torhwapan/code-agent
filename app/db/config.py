import json
import os
from pathlib import Path


class DBConfig:
    def __init__(self, config_path="configs/db.json"):
        self.path = Path(config_path)
        self.data = self._load()
        self.profile_name = os.getenv("DB_PROFILE") or self.data.get("active_profile")
        self.profile = self.data.get("profiles", {}).get(self.profile_name, {})
        self.queries = self.data.get("queries", {})

    def get_query(self, query_id):
        if query_id not in self.queries:
            raise ValueError(f"Unknown query template: {query_id}")
        return self.queries[query_id]

    def _load(self):
        if not self.path.exists():
            return {"profiles": {}, "queries": {}}
        return json.loads(self.path.read_text(encoding="utf-8"))
