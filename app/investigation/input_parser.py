import re


class IncidentInputParser:
    LOT_RE = re.compile(r"\b(?:lotId|lot_id|lot)\s*[:=]?\s*([A-Za-z0-9_.-]{4,})\b", re.IGNORECASE)
    FAB_RE = re.compile(r"\b(Fab1|Fab2)\b", re.IGNORECASE)
    ENV_RE = re.compile(r"\b(pirun|prod)\b", re.IGNORECASE)

    def parse(self, text, lot_id=None, fab=None, env=None):
        source = text or ""
        return {
            "lot_id": lot_id or self._find(self.LOT_RE, source),
            "fab": self._normalize_fab(fab or self._find(self.FAB_RE, source)),
            "env": self._normalize_env(env or self._find(self.ENV_RE, source)),
        }

    def _find(self, pattern, text):
        match = pattern.search(text)
        if not match:
            return None
        return match.group(1)

    def _normalize_fab(self, value):
        if not value:
            return None
        value = value.lower()
        if value == "fab1":
            return "Fab1"
        if value == "fab2":
            return "Fab2"
        return value

    def _normalize_env(self, value):
        if not value:
            return None
        return value.lower()
