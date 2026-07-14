def build_opencode_prompt(payload, repo):
    message = (payload.get("message") or "").strip()
    context = (payload.get("context") or "").strip()
    repo_name = repo.get("name") or repo.get("id") or "unknown"

    parts = [
        "你是资深代码分析助手。请基于当前 opencode 工作目录中的代码回答用户问题。",
        "",
        f"代码仓库：{repo_name}",
        "",
        "用户需求：",
        message,
    ]

    if context:
        parts.extend(["", "补充上下文：", context])

    parts.extend(
        [
            "",
            "输出要求：",
            "1. 使用中文 Markdown。",
            "2. 先给结论，再给关键证据。",
            "3. 尽量列出相关文件、类、方法和调用链。",
            "4. 如果证据不足，明确说明不确定点。",
            "5. 不要编造没有在代码中确认的信息。",
        ]
    )

    return "\n".join(parts)
