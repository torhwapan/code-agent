class IntentAgent:
    def decide(self, payload):
        message = (payload.get("message") or payload.get("description") or payload.get("user_message") or "").strip()
        lowered = message.lower()
        task_type = self._classify_code_task(lowered, message)
        return {
            "intent": "code_question",
            "task_type": task_type,
            "reason": "当前版本只保留代码分析能力，所有用户输入都按代码分析任务处理。",
        }

    def _classify_code_task(self, lowered, message):
        if any(word in message for word in ["流程", "调用链", "链路", "怎么执行", "怎么走", "如何执行"]):
            return "flow_analysis"
        if any(word in message for word in ["影响", "改动", "风险", "会不会影响"]):
            return "impact_analysis"
        if any(word in lowered for word in ["bug", "error", "exception"]) or any(word in message for word in ["报错", "异常", "失败"]):
            return "bug_hunt"
        return "code_question"
