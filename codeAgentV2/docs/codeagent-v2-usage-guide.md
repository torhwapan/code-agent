# CodeAgentV2 使用说明

本文档说明 CodeAgentV2 怎么启动、怎么调用、怎么配置代码仓库，以及它依赖了哪些 opencode HTTP API。

## 1. CodeAgentV2 是什么

CodeAgentV2 是 opencode 的 HTTP 包装层。

它本身不再实现复杂的代码搜索、读文件、LLM 多步 agent loop，而是把这些能力交给 opencode。

整体链路：

```text
公司平台父 Agent / 子 Agent
  -> CodeAgentV2 HTTP API
       -> opencode HTTP Server
            -> 代码搜索
            -> 文件读取
            -> LLM 分析
            -> 返回结果
```

CodeAgentV2 负责：

- 提供稳定的企业内部 HTTP API。
- 根据 `repo_id` 选择对应 opencode server。
- 创建 opencode session。
- 把用户需求和上下文拼成 prompt。
- 调用 opencode 执行代码分析。
- 提取 opencode 返回文本。
- 返回统一 JSON 格式。
- 记录业务日志。

CodeAgentV2 不负责：

- 查询 DB。
- 获取服务器日志。
- 检索 SOP / CASE / 需求文档。
- 自己实现代码分析 agent loop。
- 自动启动或停止 opencode 进程。

## 2. 目录结构

```text
codeAgentV2/
  app/
    server.py             # HTTP 服务入口
    engine.py             # CodeAgentV2 主流程
    opencode_client.py    # opencode HTTP 客户端
    prompt_builder.py     # prompt 拼装
    result_parser.py      # opencode 返回结果解析
    config.py             # repositories.json 读取
    business_logger.py    # 本地业务日志

  configs/
    repositories.json     # repo_id -> opencode_url 映射

  docs/
    codeagent-v2-design.md
    codeagent-v2-http-api.md
    codeagent-v2-usage-guide.md

  opencode-api-manual-test.md
  README.md
```

## 3. 使用前提

### 3.1 已安装 opencode

检查：

```powershell
opencode --version
```

能看到版本号即可。

### 3.2 opencode 能正常调用模型

建议先用 opencode CLI 自己测试一次普通代码问题，确认模型、网络、权限都正常。

### 3.3 Python 可用

检查：

```powershell
python --version
```

CodeAgentV2 目前只用 Python 标准库，不需要额外安装第三方依赖。

## 4. 第一步：启动 opencode server

先进入要分析的代码仓库目录。

例如分析当前 `codeAgent` 项目：

```powershell
cd D:\Professional\myCode\codeAnalysis\codeAgent
opencode serve --hostname 127.0.0.1 --port 9101 --print-logs
```

正常会看到：

```text
opencode server listening on http://127.0.0.1:9101
```

说明：

- opencode server 的工作目录就是你执行命令时所在的目录。
- 如果要分析 MES 代码，就在 MES 代码根目录启动 opencode。
- 如果要分析 EAP 代码，就在 EAP 代码根目录启动 opencode。

例如：

```powershell
cd D:\CompanyCode\MES-Fab12
opencode serve --hostname 127.0.0.1 --port 9111 --print-logs
```

## 5. 第二步：配置 CodeAgentV2 仓库映射

配置文件：

```text
codeAgentV2/configs/repositories.json
```

示例：

```json
{
  "default_repo_id": "workspace",
  "repositories": [
    {
      "id": "workspace",
      "name": "CodeAgent workspace",
      "root": "D:/Professional/myCode/codeAnalysis/codeAgent",
      "opencode_url": "http://127.0.0.1:9101",
      "opencode_password": ""
    },
    {
      "id": "mes_fab12",
      "name": "MES Fab1/Fab2",
      "root": "D:/CompanyCode/MES-Fab12",
      "opencode_url": "http://127.0.0.1:9111",
      "opencode_password": ""
    }
  ]
}
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `id` | 平台调用时传入的 `repo_id` |
| `name` | 仓库显示名称 |
| `root` | 代码目录，当前主要用于说明和排查 |
| `opencode_url` | 对应 opencode server 地址 |
| `opencode_password` | opencode server 密码，可为空 |

当前第一版不会自动启动 opencode，所以要确保 `opencode_url` 对应的 server 已经启动。

## 6. 第三步：启动 CodeAgentV2

```powershell
cd D:\Professional\myCode\codeAnalysis\codeAgentV2
python -m app.server --host 127.0.0.1 --port 8020
```

如果要给其他机器访问：

```powershell
python -m app.server --host 0.0.0.0 --port 8020
```

健康检查：

```powershell
curl http://127.0.0.1:8020/health
```

期望返回：

```json
{
  "ok": true,
  "service": "code-agent-v2"
}
```

## 7. 第四步：调用 CodeAgentV2

接口：

```http
POST /api/code-analysis
```

等价接口：

```http
POST /api/code-analysis/handle
```

最小请求：

```powershell
curl -s -X POST http://127.0.0.1:8020/api/code-analysis ^
  -H "Content-Type: application/json" ^
  -d "{\"repo_id\":\"workspace\",\"message\":\"Analyze app/code_analysis/agent.py\"}"
```

带上下文请求：

```powershell
curl -s -X POST http://127.0.0.1:8020/api/code-analysis ^
  -H "Content-Type: application/json" ^
  -d "{\"repo_id\":\"workspace\",\"message\":\"Analyze app/code_analysis/agent.py\",\"context\":\"Focus on the main flow and important files.\",\"options\":{\"timeout_seconds\":300}}"
```

请求字段：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `repo_id` | 否 | 代码仓库 id，不传则使用 `default_repo_id` |
| `message` | 是 | 用户代码分析需求 |
| `context` | 否 | 父 Agent 压缩后的上下文、报错片段、业务背景 |
| `options.timeout_seconds` | 否 | 调 opencode 的超时时间，默认 300 秒 |
| `options.session_title` | 否 | opencode session 标题 |

## 8. 返回结构

成功：

```json
{
  "ok": true,
  "status": "completed",
  "data": {
    "summary": "仓库摘要",
    "answer_markdown": "## 分析结果...",
    "repo_id": "workspace",
    "engine": "opencode",
    "opencode_session_id": "ses_xxx",
    "opencode_url": "http://127.0.0.1:9101",
    "duration_ms": 39812,
    "debug": {
      "request_id": "REQ-...",
      "message_id": "msg_xxx",
      "parts_count": 4
    }
  }
}
```

失败：

```json
{
  "ok": false,
  "status": "error",
  "error": "message is required"
}
```

## 9. CodeAgentV2 依赖的 opencode API

CodeAgentV2 当前依赖 opencode 的 3 个接口。

### 9.1 `GET /doc`

用途：

- 检查 opencode server 是否可访问。
- 返回 OpenAPI JSON。

手动测试：

```powershell
curl http://127.0.0.1:9101/doc
```

代码位置：

```text
app/opencode_client.py
OpenCodeClient.health()
```

当前业务主流程不强制调用它，但排查问题时很有用。

### 9.2 `POST /session`

用途：

- 创建一个新的 opencode session。
- 每次 CodeAgentV2 分析请求都会创建一个新 session。

请求：

```json
{
  "title": "CodeAgentV2 analysis"
}
```

响应里重点字段：

```json
{
  "id": "ses_xxx",
  "directory": "D:\\CompanyCode\\MES-Fab12",
  "title": "CodeAgentV2 analysis"
}
```

CodeAgentV2 会保存：

```text
opencode_session_id
```

代码位置：

```text
app/opencode_client.py
OpenCodeClient.create_session()
```

### 9.3 `POST /session/{sessionID}/message`

用途：

- 向指定 opencode session 发送用户问题。
- opencode 会在当前代码目录内完成代码分析。

请求：

```json
{
  "parts": [
    {
      "type": "text",
      "text": "最终拼好的 prompt"
    }
  ]
}
```

响应里重点字段：

```json
{
  "info": {
    "id": "msg_xxx",
    "sessionID": "ses_xxx"
  },
  "parts": [
    {
      "type": "text",
      "text": "模型回答"
    }
  ]
}
```

CodeAgentV2 会从 `parts` 里提取所有：

```text
type=text
```

然后拼成：

```text
answer_markdown
```

代码位置：

```text
app/opencode_client.py
OpenCodeClient.send_message()

app/result_parser.py
extract_answer_text()
```

### 9.4 `GET /session/{sessionID}/message`

用途：

- 查询某个 session 的消息列表。
- 当前 CodeAgentV2 主流程暂时没有使用。
- 后续如果要做异步任务、排查历史消息、重新拉取结果，可以用它。

代码位置：

```text
app/opencode_client.py
OpenCodeClient.list_messages()
```

## 10. CodeAgentV2 如何拼 prompt

代码位置：

```text
app/prompt_builder.py
```

拼接逻辑：

```text
你是资深代码分析助手。请基于当前 opencode 工作目录中的代码回答用户问题。

代码仓库：xxx

用户需求：
{message}

补充上下文：
{context}

输出要求：
1. 使用中文 Markdown。
2. 先给结论，再给关键证据。
3. 尽量列出相关文件、类、方法和调用链。
4. 如果证据不足，明确说明不确定点。
5. 不要编造没有在代码中确认的信息。
```

## 11. 多仓库部署建议

第一版建议：

```text
一个代码仓库启动一个 opencode server
一个 repo_id 对应一个 opencode_url
```

示例：

```text
workspace  -> http://127.0.0.1:9101
mes_fab12  -> http://127.0.0.1:9111
mes_fab3   -> http://127.0.0.1:9112
eap_fab1   -> http://127.0.0.1:9121
```

优点：

- 简单。
- 稳定。
- 不需要 CodeAgentV2 管理进程。
- opencode 工作目录明确，不容易串仓库。

## 12. 常见问题

### 12.1 CodeAgentV2 返回 opencode connection failed

检查：

1. opencode server 是否启动。
2. `configs/repositories.json` 里的 `opencode_url` 是否正确。
3. 端口是否被防火墙拦截。
4. opencode 是否监听了正确 hostname。

### 12.2 opencode 返回慢

原因通常是：

- 代码仓库大。
- 首次分析需要建立上下文。
- 模型响应慢。

可以先把 `options.timeout_seconds` 调大。

### 12.3 返回内容不符合格式

CodeAgentV2 只是给 opencode prompt 里写了输出要求。

如果需要更稳定格式，可以后续增加：

- 固定 prompt 模板。
- JSON 输出模式。
- 二次结果整理。

第一版先保持简单。

## 13. 关闭服务

关闭 CodeAgentV2：

```text
Ctrl + C
```

关闭 opencode server：

```text
Ctrl + C
```

如果后台启动，可以按端口结束进程。
