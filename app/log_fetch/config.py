import json
from pathlib import Path


class LogConfig:
    def __init__(self, config_path="configs/logs.json"):
        self.path = Path(config_path)
        self.data = self._load()

    def get_fab(self, fab):
        fabs = self.data.get("fabs", {})
        if fab not in fabs:
            raise ValueError(f"Unknown fab in logs config: {fab}")
        return fabs[fab]

    def cache_dir(self):
        return Path(self.data.get("cache_dir", "data/log_cache"))

    def time_window_seconds(self):
        return int(self.data.get("default_time_window_seconds", 90))

    def file_interval_seconds(self):
        return int(self.data.get("default_file_interval_seconds", 120))

    def path_template(self):
        return self.data.get("path_template", "{env}/{server_ip}/{module}")

    def filename_time_patterns(self):
        return self.data.get("filename_time_patterns", [])

    def _load(self):
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))
