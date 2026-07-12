import ftplib
import re
from datetime import datetime, timedelta
from pathlib import Path

from app.log_fetch.config import LogConfig


class FTPLogFetcher:
    def __init__(self, config=None):
        self.config = config or LogConfig()

    def fetch_logs(self, fab, env, server_ip, module, target_time, keywords=None, window_seconds=None):
        if not target_time:
            return {"warning": "target_time is empty, skip FTP log fetch.", "snippets": []}

        target_dt = self._parse_time(target_time)
        if not target_dt:
            return {"warning": f"Cannot parse target_time: {target_time}", "snippets": []}

        window = window_seconds or self.config.time_window_seconds()
        remote_dir = self._build_remote_dir(env, server_ip, module)
        local_files = self._download_candidate_files(fab, remote_dir, target_dt)

        extractor = LogExtractor()
        snippets = []
        for local_file in local_files:
            extracted = extractor.extract(local_file, target_dt, window, keywords or [])
            if extracted["lines"]:
                snippets.append(extracted)

        return {
            "fab": fab,
            "remote_dir": remote_dir,
            "target_time": target_time,
            "downloaded_files": [str(path) for path in local_files],
            "snippets": snippets,
        }

    def _build_remote_dir(self, env, server_ip, module):
        return self.config.path_template().format(
            env=env,
            server_ip=server_ip,
            module=module,
        ).replace("\\", "/")

    def _download_candidate_files(self, fab, remote_dir, target_dt):
        ftp_info = self.config.get_fab(fab)
        cache_dir = self.config.cache_dir() / fab / remote_dir.replace("/", "_")
        cache_dir.mkdir(parents=True, exist_ok=True)

        with ftplib.FTP() as ftp:
            ftp.connect(ftp_info["host"], int(ftp_info.get("port", 21)), timeout=30)
            ftp.login(ftp_info.get("username", ""), ftp_info.get("password", ""))
            root = ftp_info.get("root", "/")
            full_dir = self._join_remote(root, remote_dir)
            ftp.cwd(full_dir)

            names = ftp.nlst()
            selected = self._select_files(names, target_dt)
            local_files = []
            for name in selected:
                local_path = cache_dir / Path(name).name
                if not local_path.exists():
                    with local_path.open("wb") as handle:
                        ftp.retrbinary(f"RETR {name}", handle.write)
                local_files.append(local_path)
            return local_files

    def _select_files(self, names, target_dt):
        candidates = []
        interval = self.config.file_interval_seconds()
        for name in names:
            file_dt = self._parse_time_from_filename(name)
            if not file_dt:
                continue
            delta = abs((file_dt - target_dt).total_seconds())
            if delta <= interval * 3:
                candidates.append((delta, name))

        candidates.sort(key=lambda item: item[0])
        return [name for _, name in candidates[:3]]

    def _parse_time_from_filename(self, name):
        for pattern in self.config.filename_time_patterns():
            match = re.search(pattern, name)
            if not match:
                continue
            parsed = self._parse_time(match.group(1))
            if parsed:
                return parsed
        return None

    def _parse_time(self, value):
        if isinstance(value, datetime):
            return value
        if not value:
            return None

        text = str(value).strip()
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H_%M_%S",
            "%y-%m-%dT%H_%M_%S",
            "%Y/%m/%d %H:%M:%S",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(text[:19], fmt)
            except ValueError:
                pass
        return None

    def _join_remote(self, root, path):
        left = (root or "/").rstrip("/")
        right = path.lstrip("/")
        if not right:
            return left or "/"
        return f"{left}/{right}"


class LogExtractor:
    TIME_PATTERNS = [
        re.compile(r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})"),
        re.compile(r"(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})"),
    ]

    def extract(self, path, target_dt, window_seconds, keywords):
        lines = self._read_lines(path)
        selected = []
        start = target_dt - timedelta(seconds=window_seconds)
        end = target_dt + timedelta(seconds=window_seconds)

        lowered_keywords = [str(item).lower() for item in keywords if item]
        for index, line in enumerate(lines, start=1):
            line_time = self._parse_line_time(line)
            if line_time and not (start <= line_time <= end):
                continue
            if lowered_keywords and not self._has_keyword(line, lowered_keywords):
                continue
            selected.append({"line": index, "text": line.rstrip()})
            if len(selected) >= 300:
                break

        return {"file": str(path), "lines": selected}

    def _read_lines(self, path):
        for encoding in ("utf-8", "utf-8-sig", "gbk", "latin-1"):
            try:
                return Path(path).read_text(encoding=encoding).splitlines()
            except UnicodeDecodeError:
                pass
        return Path(path).read_text(encoding="utf-8", errors="replace").splitlines()

    def _parse_line_time(self, line):
        for pattern in self.TIME_PATTERNS:
            match = pattern.search(line)
            if not match:
                continue
            text = match.group(1)
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y/%m/%d %H:%M:%S"):
                try:
                    return datetime.strptime(text, fmt)
                except ValueError:
                    pass
        return None

    def _has_keyword(self, line, keywords):
        lowered = line.lower()
        return any(keyword in lowered for keyword in keywords)
