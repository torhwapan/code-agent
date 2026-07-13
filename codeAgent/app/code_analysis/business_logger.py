import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


class BusinessLogger:
    def __init__(self, log_dir="data/business_logs/code_analysis"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def new_request_id(self):
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"REQ-{stamp}-{uuid.uuid4().hex[:8]}"

    def write(self, event, payload):
        record = {
            "event": event,
            "logged_at": datetime.now(timezone.utc).isoformat(),
        }
        record.update(payload or {})

        path = self.log_dir / (datetime.now().strftime("%Y%m%d") + ".jsonl")
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def preview(self, value, limit=500):
        text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
        if len(text) <= limit:
            return text
        return text[:limit] + "...<truncated>"

    def summarize_request(self, request):
        attachments = request.get("attachments") or {}
        known_context = request.get("known_context") or {}
        return {
            "case_id": request.get("case_id") or "",
            "repo_id": request.get("repo_id") or known_context.get("repo_id") or "workspace",
            "user_message_preview": self.preview(request.get("user_message") or request.get("message") or ""),
            "conversation_summary_preview": self.preview(request.get("conversation_summary") or request.get("context_summary") or ""),
            "extra_text_length": len(attachments.get("extra_text") or request.get("extra_text") or ""),
            "known_context": self._compact_dict(known_context),
        }

    def summarize_task(self, task):
        evidence = task.get("evidence") or {}
        code_signals = task.get("code_signals") or {}
        return {
            "task_type": task.get("task_type") or "",
            "repo_id": task.get("repo_id") or "",
            "user_goal_preview": self.preview(task.get("user_goal") or ""),
            "context_summary_preview": self.preview(task.get("context_summary") or ""),
            "keyword_count": len(code_signals.get("keywords") or []),
            "class_count": len(code_signals.get("classes") or []),
            "method_count": len(code_signals.get("methods") or []),
            "exception_count": len(code_signals.get("exceptions") or []),
            "extra_text_length": len(evidence.get("extra_text") or ""),
            "module": code_signals.get("module") or "",
            "rule_name": code_signals.get("rule_name") or "",
        }

    def summarize_result(self, result):
        codegraph_results = result.get("codegraph_results") or []
        first_codegraph = codegraph_results[0] if codegraph_results else {}
        return {
            "analysis_case_id": result.get("case_id") or "",
            "task_type": result.get("task_type") or "",
            "llm_enabled": bool(result.get("llm_enabled")),
            "codegraph_used": bool(codegraph_results),
            "codegraph_ok": bool(first_codegraph.get("ok")) if first_codegraph else False,
            "codegraph_query_preview": self.preview(first_codegraph.get("query") or "", limit=300),
            "codegraph_output_length": len(first_codegraph.get("output") or ""),
            "codegraph_error": self.preview(first_codegraph.get("error") or "", limit=300),
            "search_term_count": len(result.get("search_terms") or []),
            "step_count": len(result.get("steps") or []),
            "match_count": len(result.get("matches") or []),
            "snippet_count": len(result.get("snippets") or []),
            "error_count": len(result.get("errors") or []),
            "report_preview": self.preview(result.get("report") or "", limit=800),
        }

    def _compact_dict(self, data):
        result = {}
        for key, value in (data or {}).items():
            if value not in (None, "", [], {}):
                result[key] = value
        return result
