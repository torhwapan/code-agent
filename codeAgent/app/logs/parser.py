from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ParsedLog:
    error_codes: list[str] = field(default_factory=list)
    exceptions: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    stack_frames: list[dict] = field(default_factory=list)
    tables: list[str] = field(default_factory=list)
    sql_fragments: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    timestamps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "error_codes": self.error_codes,
            "exceptions": self.exceptions,
            "classes": self.classes,
            "methods": self.methods,
            "stack_frames": self.stack_frames,
            "tables": self.tables,
            "sql_fragments": self.sql_fragments,
            "keywords": self.keywords,
            "timestamps": self.timestamps,
        }


class LogParser:
    ERROR_CODE_RE = re.compile(r"\b(?:[A-Z]{2,}[A-Z0-9]*(?:-[A-Z0-9]+){1,}|ORA-\d{5}|SQLSTATE\[[A-Z0-9]+\]|SQLSTATE\s*[=:]\s*[A-Z0-9]+)\b")
    EXCEPTION_RE = re.compile(r"\b([A-Za-z_$][\w.$]*(?:Exception|Error|Timeout|Deadlock|SQLException))\b")
    JAVA_FRAME_RE = re.compile(r"\bat\s+([\w.$]+)\.([A-Za-z_$][\w$]*)\(([^():]+)(?::(\d+))?\)")
    TIMESTAMP_RE = re.compile(r"\b\d{4}[-/]\d{2}[-/]\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d{1,6})?\b")
    TABLE_RE = re.compile(r"\b[A-Z][A-Z0-9]{1,}_[A-Z0-9_]{2,}\b")
    SQL_RE = re.compile(
        r"\b(?:select|insert|update|delete|merge|from|join|where)\b.{0,220}",
        re.IGNORECASE,
    )

    NOISE_WORDS = {
        "ERROR",
        "WARN",
        "INFO",
        "DEBUG",
        "TRACE",
        "NULL",
        "TRUE",
        "FALSE",
    }

    def parse(self, raw_text: str) -> ParsedLog:
        text = raw_text or ""
        frames = []
        classes = []
        methods = []
        for match in self.JAVA_FRAME_RE.finditer(text):
            full_class = match.group(1)
            method = match.group(2)
            frames.append(
                {
                    "class": full_class,
                    "simple_class": full_class.split(".")[-1],
                    "method": method,
                    "file": match.group(3),
                    "line": int(match.group(4)) if match.group(4) else None,
                }
            )
            classes.extend([full_class, full_class.split(".")[-1]])
            methods.append(method)

        exceptions = []
        for item in self.EXCEPTION_RE.findall(text):
            exceptions.append(item.split(".")[-1])
            if "." in item:
                classes.append(item)

        tables = [t for t in self.TABLE_RE.findall(text) if t not in self.NOISE_WORDS]
        sql_fragments = [self._clean_line(m.group(0)) for m in self.SQL_RE.finditer(text)]
        keywords = self._extract_keywords(text)

        return ParsedLog(
            error_codes=self._unique(self.ERROR_CODE_RE.findall(text), 20),
            exceptions=self._unique(exceptions, 20),
            classes=self._unique(classes, 30),
            methods=self._unique(methods, 30),
            stack_frames=frames[:20],
            tables=self._unique(tables, 30),
            sql_fragments=self._unique(sql_fragments, 8),
            keywords=self._unique(keywords, 30),
            timestamps=self._unique(self.TIMESTAMP_RE.findall(text), 10),
        )

    def build_search_terms(self, parsed: ParsedLog) -> list[str]:
        terms: list[str] = []
        terms.extend(frame["simple_class"] for frame in parsed.stack_frames)
        terms.extend(parsed.classes)
        terms.extend(parsed.methods)
        terms.extend(parsed.error_codes)
        terms.extend(parsed.exceptions)
        terms.extend(parsed.tables)
        terms.extend(self._sql_identifiers(parsed.sql_fragments))
        terms.extend(parsed.keywords)
        return self._unique([term for term in terms if len(term) >= 3], 50)

    def _extract_keywords(self, text: str) -> list[str]:
        keywords = []
        signal_words = re.compile(r"(error|exception|fail|failed|timeout|deadlock|invalid|mismatch|cannot|unable|abort|rollback)", re.I)
        for line in text.splitlines():
            if signal_words.search(line):
                cleaned = self._clean_line(line)
                if cleaned:
                    keywords.append(cleaned[:180])

        quoted = re.findall(r"'([^']{3,80})'|\"([^\"]{3,80})\"", text)
        for left, right in quoted:
            value = left or right
            if value and not value.isspace():
                keywords.append(value.strip())

        return keywords[:30]

    def _sql_identifiers(self, fragments: list[str]) -> list[str]:
        identifiers = []
        for fragment in fragments:
            identifiers.extend(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]{3,}\b", fragment))
        return identifiers

    def _clean_line(self, line: str) -> str:
        return re.sub(r"\s+", " ", line).strip()

    def _unique(self, items: list[str], limit: int) -> list[str]:
        seen = set()
        result = []
        for item in items:
            clean = item.strip()
            key = clean.lower()
            if not clean or key in seen:
                continue
            seen.add(key)
            result.append(clean)
            if len(result) >= limit:
                break
        return result
