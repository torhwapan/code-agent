import json
import urllib.request


class CodeAnalysisChildAgent:
    def __init__(self, code_agent=None, service_url=None):
        self.code_agent = code_agent
        self.service_url = (service_url or "").rstrip("/")

    def run(self, context):
        request = self._build_child_request(context)

        if self.service_url:
            result = self._call_remote_agent(request)
        else:
            result = self.code_agent.handle_input(request)

        task = result.get("normalized_task") or {}
        task_type = task.get("task_type") or context.get("task_type") or "code_question"
        debug = result.get("debug") or {}

        return {
            "ok": True,
            "agent": "CodeAnalysisAgent",
            "summary": result.get("summary") or f"代码分析完成，任务类型：{task_type}。",
            "answer_markdown": result.get("answer_markdown") or result.get("report") or "",
            "evidence": result.get("evidence") or [],
            "diagnosis": result.get("diagnosis") or {},
            "debug": {
                "case_id": debug.get("case_id") or result.get("case_id") or "",
                "step_count": debug.get("step_count", len(result.get("steps") or [])),
                "error_count": debug.get("error_count", len(result.get("errors") or [])),
            },
            # Keep the full child-agent payload for troubleshooting, but parent/user
            # facing code should prefer summary/answer_markdown/evidence/diagnosis.
            "data": result,
            "child_request": request,
            "task": task,
            "warnings": [],
        }

    def _call_remote_agent(self, request_payload):
        body = json.dumps(request_payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"{self.service_url}/api/code-analysis/handle",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=180) as response:
            data = json.loads(response.read().decode("utf-8"))
        if not data.get("ok"):
            raise RuntimeError(data.get("error") or data.get("message") or "CodeAnalysisAgent remote call failed")
        return data.get("data") or {}

    def _build_child_request(self, context):
        parsed = context.get("parsed") or {}
        return {
            "case_id": context.get("case_id") or "",
            "repo_id": context.get("repo_id") or "workspace",
            "user_message": context.get("user_message") or "",
            "conversation_summary": self._build_context_summary(context),
            "attachments": {
                "extra_text": context.get("extra_text") or "",
            },
            "known_context": {
                "fab": parsed.get("fab"),
                "module": parsed.get("module"),
                "rule_name": parsed.get("rule_name"),
            },
            "options": {
                "max_steps": context.get("max_steps") or 8,
            },
        }

    def _build_context_summary(self, context):
        parts = []
        parsed = context.get("parsed", {})
        if parsed:
            parsed_summary = self._compact_dict(
                parsed,
                ["fab", "module", "rule_name"],
            )
            if parsed_summary:
                parts.append("解析字段：" + ", ".join(f"{key}={value}" for key, value in parsed_summary.items()))
        return "\n".join(parts)

    def _compact_dict(self, data, keys):
        result = {}
        for key in keys:
            value = data.get(key)
            if value not in (None, "", [], {}):
                result[key] = value
        return result
