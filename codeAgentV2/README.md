# CodeAgentV2

CodeAgentV2 是 opencode 的企业包装层。

它不再自己实现代码搜索、读文件和 LLM agent loop，而是通过 HTTP 调用 opencode server。

## 能力边界

CodeAgentV2 负责：

- 接收统一 HTTP 请求。
- 根据 `repo_id` 找到 opencode server。
- 创建 opencode session。
- 把用户需求和上下文拼成 prompt。
- 调用 opencode 分析代码。
- 提取文本结果并返回统一 JSON。
- 记录业务日志。

CodeAgentV2 不负责：

- 查询 DB。
- 获取服务器日志。
- 检索 SOP / CASE / 需求文档。
- 自己实现代码分析 agent loop。

## 启动 opencode

先在目标代码目录启动 opencode server：

```powershell
cd D:\Professional\myCode\codeAnalysis\codeAgent
opencode serve --hostname 127.0.0.1 --port 9101 --print-logs
```

## 启动 CodeAgentV2

另开一个终端：

```powershell
cd D:\Professional\myCode\codeAnalysis\codeAgentV2
python -m app.server --host 0.0.0.0 --port 8020
```

健康检查：

```bash
curl http://127.0.0.1:8020/health
```

其他电脑访问时，把 `127.0.0.1` 换成服务器 IP：

```bash
curl http://服务器IP:8020/health
```

## 请求示例

```bash
curl -s -X POST http://127.0.0.1:8020/api/code-analysis ^
  -H "Content-Type: application/json" ^
  -d "{\"repo_id\":\"workspace\",\"message\":\"Analyze app/code_analysis/agent.py\",\"context\":\"Focus on the main flow.\"}"
```

## 入参

```json
{
  "repo_id": "workspace",
  "message": "用户代码分析需求",
  "context": "可选。父 Agent 压缩后的上下文、报错、业务背景。",
  "options": {
    "timeout_seconds": 300,
    "session_title": "可选 session 标题"
  }
}
```

## 出参

```json
{
  "ok": true,
  "status": "completed",
  "data": {
    "summary": "摘要",
    "answer_markdown": "Markdown 分析结果",
    "repo_id": "workspace",
    "engine": "opencode",
    "opencode_session_id": "ses_xxx",
    "duration_ms": 12345
  }
}
```

## 配置仓库

配置文件：

```text
configs/repositories.json
```

每个仓库配置一个 opencode server：

```json
{
  "id": "mes_fab12",
  "name": "MES Fab1/Fab2",
  "root": "D:/CompanyCode/MES-Fab12",
  "opencode_url": "http://127.0.0.1:9111",
  "opencode_password": ""
}
```
