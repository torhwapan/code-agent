class CodeAnalysisChildAgent:
    def __init__(self, code_agent):
        self.code_agent = code_agent

    def run(self, context):
        payload = {
            "repo_id": context.get("repo_id") or "workspace",
            "description": self._build_description(context),
            "raw_log": self._build_analysis_text(context),
            "max_steps": context.get("max_steps") or 8,
        }

        result = self.code_agent.analyze(
            repo_id=payload["repo_id"],
            raw_log=payload["raw_log"],
            description=payload["description"],
            max_steps=payload["max_steps"],
        )

        return {
            "ok": True,
            "agent": "CodeAnalysisAgent",
            "summary": "代码分析完成。",
            "data": result,
            "warnings": [],
        }

    def _build_description(self, context):
        parts = [context.get("user_message", "")]
        parsed = context.get("parsed", {})
        db_data = context.get("db_result", {}).get("data", {})
        if parsed:
            parts.append(f"解析字段：{parsed}")
        if db_data:
            parts.append(f"DB 定位：{db_data}")
        return "\n".join(part for part in parts if part)

    def _build_analysis_text(self, context):
        log_text = context.get("log_text") or ""
        if log_text.strip():
            return log_text

        message = context.get("user_message") or ""
        parsed = context.get("parsed", {})
        keywords = parsed.get("keywords") or []
        if keywords:
            return message + "\n" + "\n".join(str(item) for item in keywords)
        return message or "CodeAnalysisAgent"

