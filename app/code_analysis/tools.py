import json
import os
import re
import shutil
import subprocess
from pathlib import Path


class CodeMatch:
    def __init__(self, repo_id, path, line, column, text, matched):
        self.repo_id = repo_id
        self.path = path
        self.line = line
        self.column = column
        self.text = text
        self.matched = matched

    def to_dict(self):
        return {
            "repo_id": self.repo_id,
            "path": self.path,
            "line": self.line,
            "column": self.column,
            "text": self.text,
            "matched": self.matched,
        }


class CodeSnippet:
    def __init__(self, repo_id, path, start_line, end_line, content, reason=""):
        self.repo_id = repo_id
        self.path = path
        self.start_line = start_line
        self.end_line = end_line
        self.content = content
        self.reason = reason

    def to_dict(self):
        return {
            "repo_id": self.repo_id,
            "path": self.path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "content": self.content,
            "reason": self.reason,
        }


class LocalCodeTools:
    def __init__(self, registry):
        self.registry = registry
        self.rg_path = shutil.which("rg")

    def search_code(self, repo_id, query, max_results=30):
        repo = self.registry.get(repo_id)
        clean_query = query.strip()
        if not clean_query:
            return []
        if self.rg_path:
            return self._search_with_rg(repo, clean_query, max_results)
        return self._search_with_python(repo, clean_query, max_results)

    def read_file(self, repo_id, path, start_line=None, end_line=None, max_lines=220, reason=""):
        resolved = self.registry.resolve_inside_repo(repo_id, path)
        if not resolved.exists() or not resolved.is_file():
            raise ValueError(f"File not found: {path}")

        text = self._read_text(resolved)
        lines = text.splitlines()
        total = len(lines)
        start = max(1, start_line or 1)
        end = min(total, end_line or min(total, start + max_lines - 1))
        if end - start + 1 > max_lines:
            end = start + max_lines - 1

        content = "\n".join(
            f"{idx + 1}: {line}"
            for idx, line in enumerate(lines[start - 1:end], start - 1)
        )

        return CodeSnippet(
            repo_id=repo_id,
            path=self._relative_path(self.registry.get(repo_id), resolved),
            start_line=start,
            end_line=end,
            content=content,
            reason=reason,
        )

    def read_around(self, repo_id, path, center_line, context_lines=80, reason=""):
        start = max(1, center_line - context_lines)
        end = center_line + context_lines
        return self.read_file(repo_id, path, start, end, context_lines * 2 + 1, reason)

    def _search_with_rg(self, repo, query, max_results):
        args = [
            self.rg_path or "rg",
            "--json",
            "--line-number",
            "--column",
            "--fixed-strings",
            "--ignore-case",
        ]
        for pattern in repo.include:
            args.extend(["-g", pattern])
        for pattern in repo.exclude:
            args.extend(["-g", f"!{pattern}"])
        args.extend([query, str(repo.root)])

        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )

        matches = []
        for line in proc.stdout.splitlines():
            if len(matches) >= max_results:
                break
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") != "match":
                continue

            data = event.get("data", {})
            path = Path(data.get("path", {}).get("text", ""))
            submatches = data.get("submatches", [])
            column = 1
            matched = query
            if submatches:
                column = int(submatches[0].get("start", 0)) + 1
                matched = submatches[0].get("match", {}).get("text", query)

            matches.append(
                CodeMatch(
                    repo_id=repo.id,
                    path=self._relative_path(repo, path),
                    line=int(data.get("line_number", 0)),
                    column=column,
                    text=data.get("lines", {}).get("text", "").rstrip(),
                    matched=matched,
                )
            )
        return matches

    def _search_with_python(self, repo, query, max_results):
        matches = []
        lower = query.lower()
        for root, dirs, files in os.walk(repo.root):
            dirs[:] = [d for d in dirs if d not in set(repo.exclude)]
            for file_name in files:
                path = Path(root) / file_name
                if not self._included(repo, path):
                    continue
                try:
                    lines = self._read_text(path).splitlines()
                except Exception:
                    continue
                for index, line in enumerate(lines, start=1):
                    column = line.lower().find(lower)
                    if column >= 0:
                        matches.append(
                            CodeMatch(
                                repo_id=repo.id,
                                path=self._relative_path(repo, path),
                                line=index,
                                column=column + 1,
                                text=line.rstrip(),
                                matched=query,
                            )
                        )
                        if len(matches) >= max_results:
                            return matches
        return matches

    def _included(self, repo, path):
        rel = self._relative_path(repo, path).replace("\\", "/")
        if any(part in set(repo.exclude) for part in Path(rel).parts):
            return False
        if not repo.include:
            return True
        return any(self._glob_to_regex(pattern).match(rel) for pattern in repo.include)

    def _glob_to_regex(self, pattern):
        regex = re.escape(pattern).replace(r"\*\*/", r"(?:.*/)?").replace(r"\*", r"[^/]*")
        return re.compile(f"^{regex}$")

    def _relative_path(self, repo, path):
        try:
            return str(path.resolve().relative_to(repo.root.resolve())).replace("\\", "/")
        except ValueError:
            return str(path).replace("\\", "/")

    def _read_text(self, path):
        for encoding in ("utf-8", "utf-8-sig", "gbk", "latin-1"):
            try:
                return path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
        return path.read_text(encoding="utf-8", errors="replace")
