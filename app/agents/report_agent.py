class ReportAgent:
    def run(self, context):
        lines = [
            "# OnCallAgent 调查报告",
            "",
            "## 1. 当前判断",
            f"- 意图：{context.get('intent')}",
            f"- 日志来源：{context.get('log_source')}",
            f"- 状态：{context.get('status')}",
        ]

        parsed = context.get("parsed") or {}
        lines.extend(
            [
                "",
                "## 2. 输入解析",
                f"- lotId：{parsed.get('lot_id') or 'N/A'}",
                f"- 厂别：{parsed.get('fab') or 'N/A'}",
                f"- 环境：{parsed.get('env') or 'N/A'}",
                f"- 模块：{parsed.get('module') or 'N/A'}",
                f"- ruleName：{parsed.get('rule_name') or 'N/A'}",
            ]
        )

        self._append_agent_result(lines, "DB 证据", context.get("db_result"))
        self._append_agent_result(lines, "日志证据", context.get("log_result"))
        self._append_knowledge(lines, context.get("knowledge"))
        self._append_code(lines, context.get("code_result"))
        self._append_warnings(lines, context)
        return "\n".join(lines)

    def _append_agent_result(self, lines, title, result):
        if not result:
            return
        lines.extend(["", f"## {title}", f"- 摘要：{result.get('summary') or 'N/A'}"])
        data = result.get("data") or {}
        for key in ("rule_name", "server_ip", "module", "handled_at", "remote_dir"):
            if data.get(key):
                lines.append(f"- {key}：{data.get(key)}")
        evidence = result.get("evidence") or []
        for item in evidence[:5]:
            lines.append(f"- 证据：{item.get('source')} - {item.get('content')}")

    def _append_knowledge(self, lines, knowledge):
        if not knowledge:
            return
        lines.extend(["", "## 知识库参考"])
        for phase, result in knowledge.items():
            if not result:
                continue
            lines.append(f"- 阶段：{phase}，query：{result.get('query') or 'N/A'}")
            collections = result.get("collections") or {}
            for name, docs in collections.items():
                for doc in docs[:2]:
                    lines.append(f"  - {name}：{doc.get('title')} - {doc.get('summary')}")

    def _append_code(self, lines, code_result):
        if not code_result:
            return
        data = code_result.get("data") or {}
        lines.extend(["", "## 代码分析结果"])
        lines.append(data.get("report") or "代码分析没有返回报告。")

    def _append_warnings(self, lines, context):
        warnings = []
        for key in ("db_result", "log_result"):
            result = context.get(key) or {}
            warnings.extend(result.get("warnings") or [])
        for phase_result in (context.get("knowledge") or {}).values():
            warnings.extend((phase_result or {}).get("warnings") or [])

        if warnings:
            lines.extend(["", "## 注意事项"])
            for item in warnings:
                lines.append(f"- {item}")

