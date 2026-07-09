import re

from app.investigation.input_parser import IncidentInputParser
from app.logs.parser import LogParser


class InputParseAgent:
    MODULE_RE = re.compile(r"\b(MES|R2R|CIM|EAP|FDC|APC)\b", re.IGNORECASE)
    RULE_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*(?:Rule|RULE))\b")

    def __init__(self):
        self.incident_parser = IncidentInputParser()
        self.log_parser = LogParser()

    def run(self, payload):
        message = payload.get("message") or payload.get("description") or ""
        log_text = payload.get("log_text") or ""
        parsed = self.incident_parser.parse(
            message,
            lot_id=payload.get("lot_id"),
            fab=payload.get("fab"),
            env=payload.get("env"),
        )

        parsed["module"] = payload.get("module") or self._find_module(message + "\n" + log_text)
        parsed["rule_name"] = payload.get("rule_name") or self._find_rule(message + "\n" + log_text)

        log_signals = self.log_parser.parse(log_text or message)
        parsed["keywords"] = self.log_parser.build_search_terms(log_signals)[:20]
        parsed["log_signals"] = log_signals.to_dict()
        return parsed

    def _find_module(self, text):
        match = self.MODULE_RE.search(text or "")
        if not match:
            return None
        return match.group(1).upper()

    def _find_rule(self, text):
        match = self.RULE_RE.search(text or "")
        if not match:
            return None
        return match.group(1)

