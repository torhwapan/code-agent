import re


class InputParseAgent:
    MODULE_RE = re.compile(r"\b(MES|R2R|CIM|EAP|FDC|APC)\b", re.IGNORECASE)
    RULE_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*(?:Rule|RULE))\b")
    FAB_RE = re.compile(r"\b(Fab[123]|FAB[123])\b")

    def run(self, payload):
        message = payload.get("message") or payload.get("description") or payload.get("user_message") or ""
        extra_text = payload.get("extra_text") or ""
        source = "\n".join(part for part in [message, extra_text] if part)

        return {
            "fab": payload.get("fab") or self._find_fab(source),
            "module": payload.get("module") or self._find_module(source),
            "rule_name": payload.get("rule_name") or self._find_rule(source),
            "keywords": self._extract_keywords(source)[:30],
        }

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

    def _find_fab(self, text):
        match = self.FAB_RE.search(text or "")
        if not match:
            return None
        value = match.group(1)
        return value[:1].upper() + value[1:].lower()

    def _extract_keywords(self, text):
        terms = []
        terms.extend(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]{2,}\b", text or ""))
        terms.extend(re.findall(r"[\u4e00-\u9fff]{2,12}", text or ""))

        seen = set()
        result = []
        for term in terms:
            key = term.lower()
            if key in seen or key in {"the", "and", "for", "with"}:
                continue
            seen.add(key)
            result.append(term)
        return result
