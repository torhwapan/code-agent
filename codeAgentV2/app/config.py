import json
from pathlib import Path


class RepositoryConfig:
    def __init__(self, config_path):
        self.config_path = Path(config_path)
        self.data = self._load()

    def list_repositories(self):
        return self.data.get("repositories", [])

    def get_repository(self, repo_id):
        repo_id = repo_id or self.data.get("default_repo_id") or "workspace"
        for repo in self.list_repositories():
            if repo.get("id") == repo_id:
                return repo
        raise ValueError(f"Unknown repo_id: {repo_id}")

    def _load(self):
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        with self.config_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
