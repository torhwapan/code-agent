import json
from pathlib import Path


class Repository:
    def __init__(self, repo_id, name, root, include=None, exclude=None):
        self.id = repo_id
        self.name = name
        self.root = Path(root)
        self.include = include or []
        self.exclude = exclude or []

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "root": str(self.root),
            "include": self.include,
            "exclude": self.exclude,
        }


class RepositoryRegistry:
    def __init__(self, config_path="configs/repositories.json"):
        self.config_path = Path(config_path)
        self.repositories = self._load()

    def list(self):
        return list(self.repositories.values())

    def get(self, repo_id):
        try:
            return self.repositories[repo_id]
        except KeyError:
            raise ValueError(f"Unknown repository id: {repo_id}")

    def resolve_inside_repo(self, repo_id, relative_or_abs_path):
        repo = self.get(repo_id)
        requested = Path(relative_or_abs_path)
        if not requested.is_absolute():
            requested = repo.root / requested

        resolved = requested.resolve()
        root = repo.root.resolve()
        if resolved != root and root not in resolved.parents:
            raise ValueError(f"Path is outside repository root: {relative_or_abs_path}")
        return resolved

    def _load(self):
        if not self.config_path.exists():
            raise FileNotFoundError(f"Repository config not found: {self.config_path}")

        data = json.loads(self.config_path.read_text(encoding="utf-8"))
        repos = {}
        base = self.config_path.parent.parent.resolve()

        for item in data.get("repositories", []):
            root = Path(item["root"])
            if not root.is_absolute():
                root = (base / root).resolve()

            repo = Repository(
                repo_id=item["id"],
                name=item.get("name", item["id"]),
                root=root,
                include=item.get("include", []),
                exclude=item.get("exclude", []),
            )
            repos[repo.id] = repo

        if not repos:
            raise ValueError("No repositories configured")
        return repos
