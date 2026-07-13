class ReportAgent:
    def run(self, context):
        code_result = context.get("code_result") or {}
        lines = [
            "# CodeAgent 分析报告",
            "",
            "## 当前判断",
            f"- 意图：{context.get('intent') or 'code_question'}",
            f"- 任务类型：{context.get('task_type') or 'code_question'}",
            f"- 状态：{context.get('status')}",
        ]

        parsed = context.get("parsed") or {}
        if parsed:
            lines.extend(
                [
                    "",
                    "## 输入解析",
                    f"- Fab：{parsed.get('fab') or 'N/A'}",
                    f"- 模块：{parsed.get('module') or 'N/A'}",
                    f"- ruleName：{parsed.get('rule_name') or 'N/A'}",
                    f"- 关键词：{', '.join(parsed.get('keywords') or []) or 'N/A'}",
                ]
            )

        self._append_code(lines, code_result)
        return "\n".join(lines)

    def _append_code(self, lines, code_result):
        if not code_result:
            lines.extend(["", "## 代码分析结果", "代码分析没有返回结果。"])
            return

        lines.extend(["", "## 代码分析结果"])
        lines.append(f"- 摘要：{code_result.get('summary') or 'N/A'}")

        diagnosis = code_result.get("diagnosis") or {}
        if diagnosis:
            lines.append(f"- 置信度：{diagnosis.get('confidence') or 'N/A'}")
            lines.append(f"- CodeGraph：used={diagnosis.get('codegraph_used')}, ok={diagnosis.get('codegraph_ok')}")
            related_files = diagnosis.get("related_files") or []
            if related_files:
                lines.append("- 相关文件：" + ", ".join(f"`{path}`" for path in related_files[:8]))

        answer = code_result.get("answer_markdown")
        if not answer:
            data = code_result.get("data") or {}
            answer = data.get("report")

        lines.append("")
        lines.append(answer or "代码分析没有返回报告。")
