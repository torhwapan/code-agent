def extract_answer_text(response):
    texts = []
    for part in response.get("parts") or []:
        if part.get("type") == "text" and part.get("text"):
            texts.append(part["text"])
    return "\n\n".join(texts).strip()


def summarize_answer(answer):
    if not answer:
        return "opencode 未返回文本结果。"
    first_line = ""
    for line in answer.splitlines():
        text = line.strip(" #*-")
        if text:
            first_line = text
            break
    return first_line[:160] if first_line else "opencode 分析完成。"
