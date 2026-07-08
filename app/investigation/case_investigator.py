from app.db.investigator import DBInvestigator
from app.investigation.input_parser import IncidentInputParser
from app.log_fetch.ftp_logs import FTPLogFetcher


class CaseInvestigator:
    def __init__(self, db_investigator=None, log_fetcher=None):
        self.parser = IncidentInputParser()
        self.db = db_investigator or DBInvestigator()
        self.logs = log_fetcher or FTPLogFetcher()

    def investigate(self, payload):
        text = payload.get("description") or ""
        parsed = self.parser.parse(
            text,
            lot_id=payload.get("lot_id"),
            fab=payload.get("fab"),
            env=payload.get("env"),
        )

        missing = [name for name in ("lot_id", "fab", "env") if not parsed.get(name)]
        if missing:
            return {
                "ok": False,
                "missing": missing,
                "parsed_input": parsed,
                "message": "Missing required fields: " + ", ".join(missing),
            }

        db_result = self.db.investigate(parsed["lot_id"], parsed["fab"], parsed["env"])
        log_result = self._fetch_logs(parsed, db_result)
        log_text = self._build_log_text(log_result)
        report = self._build_report(parsed, db_result, log_result)

        return {
            "ok": True,
            "parsed_input": parsed,
            "db_result": db_result,
            "log_result": log_result,
            "log_text": log_text,
            "report": report,
        }

    def _fetch_logs(self, parsed, db_result):
        required = ["server_ip", "module", "handled_at"]
        missing = [name for name in required if not db_result.get(name)]
        if missing:
            return {
                "skipped": True,
                "reason": "Missing DB fields required for log lookup: " + ", ".join(missing),
            }

        keywords = [
            parsed["lot_id"],
            db_result.get("rule_name"),
            db_result.get("module"),
        ]
        try:
            return self.logs.fetch_logs(
                fab=parsed["fab"],
                env=db_result.get("env") or parsed["env"],
                server_ip=db_result["server_ip"],
                module=db_result["module"],
                target_time=db_result["handled_at"],
                keywords=keywords,
            )
        except Exception as exc:
            return {"error": str(exc)}

    def _build_log_text(self, log_result):
        parts = []
        for snippet in log_result.get("snippets", []):
            file_name = snippet.get("file", "")
            if file_name:
                parts.append(f"===== {file_name} =====")
            for row in snippet.get("lines", []):
                parts.append(row.get("text", ""))
        return "\n".join(parts)

    def _build_report(self, parsed, db_result, log_result):
        lines = [
            "# DB and Log Investigation Report",
            "",
            "## 1. Input",
            f"- lotId: {parsed.get('lot_id')}",
            f"- fab: {parsed.get('fab')}",
            f"- env: {parsed.get('env')}",
            "",
            "## 2. DB Result",
            f"- ruleName: {db_result.get('rule_name') or 'N/A'}",
            f"- serverIp: {db_result.get('server_ip') or 'N/A'}",
            f"- module: {db_result.get('module') or 'N/A'}",
            f"- handledAt: {db_result.get('handled_at') or 'N/A'}",
        ]

        warnings = db_result.get("warnings") or []
        if warnings:
            lines.append("")
            lines.append("## 3. Warnings")
            for item in warnings:
                lines.append(f"- {item}")

        lines.append("")
        lines.append("## 4. Log Result")
        if log_result.get("skipped"):
            lines.append(f"- Skipped: {log_result.get('reason')}")
        elif log_result.get("error"):
            lines.append(f"- Error: {log_result.get('error')}")
        else:
            files = log_result.get("downloaded_files", [])
            snippets = log_result.get("snippets", [])
            lines.append(f"- downloaded files: {len(files)}")
            lines.append(f"- matched snippets: {len(snippets)}")
            for snippet in snippets[:3]:
                lines.append(f"- file: {snippet.get('file')}")
                for row in snippet.get("lines", [])[:10]:
                    lines.append(f"  - {row['line']}: {row['text']}")

        return "\n".join(lines)
