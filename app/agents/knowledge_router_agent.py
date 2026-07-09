class KnowledgeRouterAgent:
    def run(self, context, phase):
        parsed = context.get("parsed", {})
        db_data = context.get("db_result", {}).get("data", {})
        keywords = []
        keywords.extend(parsed.get("keywords") or [])
        for key in ("module", "rule_name", "lot_id"):
            value = parsed.get(key) or db_data.get(key)
            if value:
                keywords.append(value)

        query = " ".join(self._unique(keywords)[:8]) or context.get("user_message", "")
        return {
            "ok": True,
            "agent": "KnowledgeRouterAgent",
            "phase": phase,
            "query": query,
            "collections": {
                "sop": self._sop_docs(parsed, db_data),
                "historical_case": self._case_docs(parsed, db_data),
                "requirement": self._requirement_docs(parsed, db_data),
            },
            "warnings": ["当前知识库为 mock 召回结果，后续可接入向量库或 Hybrid RAG。"],
        }

    def _sop_docs(self, parsed, db_data):
        module = db_data.get("module") or parsed.get("module") or "R2R"
        return [
            {
                "title": f"{module} Rule Timeout 处理 SOP",
                "summary": "先确认 lot 当前状态、ruleName、处理服务器和目标时间窗口日志，再判断是否需要重跑或升级研发。",
                "score": 0.82,
            }
        ]

    def _case_docs(self, parsed, db_data):
        rule_name = db_data.get("rule_name") or parsed.get("rule_name") or "MockRecipeCheckRule"
        return [
            {
                "title": f"历史 CASE：{rule_name} timeout",
                "summary": "历史类似问题多与 recipe 状态等待、R2R 回包超时或 rule 执行线程阻塞有关。",
                "score": 0.78,
            }
        ]

    def _requirement_docs(self, parsed, db_data):
        module = db_data.get("module") or parsed.get("module") or "R2R"
        return [
            {
                "title": f"{module} Rule 执行需求说明",
                "summary": "rule 执行需要在指定超时时间内返回明确结果；超时后不得直接放行 lot。",
                "score": 0.75,
            }
        ]

    def _unique(self, items):
        seen = set()
        result = []
        for item in items:
            text = str(item).strip()
            key = text.lower()
            if text and key not in seen:
                seen.add(key)
                result.append(text)
        return result

