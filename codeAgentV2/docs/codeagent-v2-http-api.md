# CodeAgentV2 HTTP API

## GET /health

响应：

```json
{
  "ok": true,
  "service": "code-agent-v2"
}
```

## GET /api/repositories

返回已配置仓库。

## POST /api/code-analysis

等价接口：

```text
POST /api/code-analysis/handle
```

请求：

```json
{
  "repo_id": "workspace",
  "message": "帮我分析 app/code_analysis/agent.py 的流程",
  "context": "可选上下文",
  "options": {
    "timeout_seconds": 300,
    "session_title": "可选标题"
  }
}
```

成功响应：

```json
{
  "ok": true,
  "status": "completed",
  "data": {
    "summary": "分析摘要",
    "answer_markdown": "Markdown 分析结果",
    "repo_id": "workspace",
    "engine": "opencode",
    "opencode_session_id": "ses_xxx",
    "opencode_url": "http://127.0.0.1:9101",
    "duration_ms": 1000,
    "debug": {
      "request_id": "REQ-...",
      "message_id": "msg_xxx",
      "parts_count": 4
    }
  }
}
```

失败响应：

```json
{
  "ok": false,
  "status": "error",
  "error": "message is required"
}
```
