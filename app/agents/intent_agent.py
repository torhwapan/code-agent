class IntentAgent:
    def decide(self, payload):
        message = (payload.get("message") or payload.get("description") or "").strip()
        log_text = (payload.get("log_text") or "").strip()
        lowered = message.lower()

        if log_text:
            return {
                "intent": "code_with_log",
                "log_source": "user_provided",
                "task_type": "log_diagnosis",
                "reason": "用户已经提供了日志或分析材料，进入证据驱动的代码分析。",
            }

        if self._looks_like_log_lookup(message, payload):
            return {
                "intent": "code_with_log",
                "log_source": "need_retrieve",
                "task_type": "log_diagnosis",
                "reason": "用户提供了 lot/fab/env 或表达了查询日志诉求，需要先定位日志。",
            }

        if any(word in lowered for word in ["sop", "case", "需求", "文档", "怎么处理", "处理步骤"]):
            return {
                "intent": "knowledge_question",
                "log_source": "none",
                "task_type": "knowledge_question",
                "reason": "用户主要在询问知识库信息。",
            }

        task_type = self._classify_code_task(lowered, message)
        return {
            "intent": "code_question",
            "log_source": "none",
            "task_type": task_type,
            "reason": "没有发现日志输入或日志查询条件，按通用代码分析处理。",
        }

    def _classify_code_task(self, lowered, message):
        if any(word in message for word in ["流程", "调用链", "链路", "怎么执行", "怎么跑"]):
            return "flow_analysis"
        if any(word in message for word in ["影响", "改动", "风险", "会不会影响"]):
            return "impact_analysis"
        if any(word in lowered for word in ["bug", "error", "exception"]) or any(word in message for word in ["报错", "异常", "失败"]):
            return "bug_hunt"
        return "code_question"

    def _looks_like_log_lookup(self, message, payload):
        if payload.get("lot_id") or payload.get("fab") or payload.get("env"):
            return True

        lowered = message.lower()
        has_lot = "lot" in lowered or "lotid" in lowered or "lot_id" in lowered
        has_fab = "fab1" in lowered or "fab2" in lowered
        has_env = "pirun" in lowered or "prod" in lowered
        wants_log = "日志" in message and any(word in message for word in ["查", "检索", "获取", "拉"])
        return wants_log or (has_lot and (has_fab or has_env))
