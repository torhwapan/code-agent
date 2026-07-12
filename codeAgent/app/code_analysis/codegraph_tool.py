import json
import shutil
import subprocess
from pathlib import Path


class CodeGraphResult:
    def __init__(self, ok, query, project_path="", output="", error="", command=None):
        self.ok = ok
        self.query = query
        self.project_path = project_path
        self.output = output
        self.error = error
        self.command = command or []

    def to_dict(self):
        return {
            "ok": self.ok,
            "query": self.query,
            "project_path": self.project_path,
            "output": self.output,
            "error": self.error,
            "command": self.command,
        }


class CodeGraphTool:
    def __init__(self, registry, config_path="configs/codegraph.json"):
        self.registry = registry
        self.config_path = Path(config_path)
        self.config = self._load_config()

    def enabled(self):
        return bool(self.config.get("enabled", False))

    def explore(self, repo_id, query, max_files=None):
        if not self.enabled():
            return CodeGraphResult(False, query, error="CodeGraph is disabled.")

        clean_query = str(query or "").strip()
        if not clean_query:
            return CodeGraphResult(False, query, error="CodeGraph query is empty.")

        cli_path = self.config.get("cliPath") or "codegraph"
        resolved_cli = self._resolve_cli(cli_path)
        if not resolved_cli:
            return CodeGraphResult(False, clean_query, error=f"CodeGraph CLI not found: {cli_path}")

        project_path = self._project_path(repo_id)
        if not project_path.exists():
            return CodeGraphResult(False, clean_query, project_path=str(project_path), error="Project path does not exist.")

        if not (project_path / ".codegraph").exists():
            return CodeGraphResult(
                False,
                clean_query,
                project_path=str(project_path),
                error=f"CodeGraph index not found. Run: codegraph init {project_path}",
            )

        args = [
            resolved_cli,
            "explore",
            clean_query[: self._int_config("maxQueryChars", 4000)],
            "--path",
            str(project_path),
        ]

        effective_max_files = max_files or self._int_config("maxFiles", 8)
        if effective_max_files:
            args.extend(["--max-files", str(effective_max_files)])

        try:
            proc = subprocess.run(
                args,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self._int_config("timeoutSeconds", 60),
            )
        except subprocess.TimeoutExpired:
            return CodeGraphResult(
                False,
                clean_query,
                project_path=str(project_path),
                error=f"CodeGraph explore timed out after {self._int_config('timeoutSeconds', 60)} seconds.",
                command=args,
            )

        output = (proc.stdout or "").strip()
        error = (proc.stderr or "").strip()
        if proc.returncode != 0:
            return CodeGraphResult(False, clean_query, str(project_path), output, error or f"Exit code: {proc.returncode}", args)

        return CodeGraphResult(
            True,
            clean_query,
            str(project_path),
            self._truncate(output, self._int_config("maxOutputChars", 24000)),
            error,
            args,
        )

    def _load_config(self):
        if not self.config_path.exists():
            return {"enabled": False}
        return json.loads(self.config_path.read_text(encoding="utf-8"))

    def _resolve_cli(self, cli_path):
        candidate = Path(cli_path)
        if candidate.is_absolute() or "\\" in cli_path or "/" in cli_path:
            return str(candidate) if candidate.exists() else None
        return shutil.which(cli_path)

    def _project_path(self, repo_id):
        repo_config = (self.config.get("repositories") or {}).get(repo_id) or {}
        configured = repo_config.get("projectPath") or self.config.get("projectPath")
        if configured:
            path = Path(configured)
            if not path.is_absolute():
                path = (self.config_path.parent.parent / path).resolve()
            return path
        return self.registry.get(repo_id).root.resolve()

    def _int_config(self, key, default):
        try:
            return int(self.config.get(key, default))
        except (TypeError, ValueError):
            return default

    def _truncate(self, text, limit):
        if len(text) <= limit:
            return text
        return text[:limit] + "\n...<codegraph output truncated>"

