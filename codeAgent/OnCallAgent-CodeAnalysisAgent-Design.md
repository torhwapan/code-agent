# OnCallAgent 通用代码分析子 Agent 设计

## 1. 目标

这版改造后，`CodeAnalysisAgent` 不再只面向错误日志场景，而是作为一个通用代码分析子 Agent 使用。

它可以处理：

- 根据用户问题分析代码
- 根据错误日志分析代码
- 根据类名、方法名、接口名、模块名定位代码
- 分析调用链和业务流程
- 根据 DB、日志、知识库证据辅助分析代码
- 后续扩展为独立进程，由父 Agent 通过 HTTP 调用

核心原则：

```text
父 Agent 负责对话、调度、会话和记忆管理。
CodeAnalysisAgent 负责代码搜索、文件读取、调用链分析和代码推理。
日志只是 evidence，不再是 CodeAnalysisAgent 的唯一入口。
受平台限制时，父 Agent 只做轻量路由，复杂意图识别和任务规范化下沉到 CodeAnalysisAgent。
```

## 2. 当前进程架构

当前代码已经支持两种运行方式。

### 2.1 本地直连模式

父 Agent 和 CodeAnalysisAgent 在同一个进程里。

```text
用户
  -> OnCallParentAgent
       -> CodeAnalysisChildAgent
            -> CodeAnalysisAgent.handle_input()
            -> CodeAnalysisAgent.normalize_request()
            -> CodeAnalysisAgent.analyze_task()
```

这是默认模式，不需要额外配置。

### 2.2 独立子进程模式

CodeAnalysisAgent 可以单独作为 HTTP 服务启动。

```text
用户
  -> 父 Agent 进程
       -> HTTP JSON
            -> CodeAnalysisAgent 子进程
```

启动子 Agent：

```bash
python -m app.code_analysis.server --host 127.0.0.1 --port 8010
```

父 Agent 使用环境变量连接它：

```bash
CODE_ANALYSIS_AGENT_URL=http://127.0.0.1:8010
python -m app.main
```

健康检查：

```text
GET /health
```

代码分析接口：

```text
POST /api/code-analysis/handle   # 推荐给父 Agent 使用，接收宽输入
POST /api/code-analysis/analyze
```

## 3. 父 Agent 如何调用代码分析

父 Agent 不再把代码分析等同于日志分析，也不需要负责复杂的代码任务规范化。

只要用户意图和代码有关，就调用 CodeAnalysisAgent。

当前典型意图：

```text
code_question   通用代码问题
code_with_log   根据日志或检索日志分析代码
flow_analysis   流程 / 调用链分析
impact_analysis 影响面分析
bug_hunt        缺陷定位
```

在平台受限的情况下，父 Agent 推荐只构造“宽输入”：

```json
{
  "case_id": "CASE-001",
  "repo_id": "workspace",
  "user_message": "帮我分析 CodeAnalysisAgent 的流程",
  "conversation_summary": "用户正在了解 OnCallAgent 的代码分析能力。",
  "attachments": {
    "log_text": "",
    "extra_text": ""
  },
  "known_context": {
    "lot_id": "",
    "fab": "",
    "env": "",
    "module": "",
    "rule_name": ""
  },
  "db_evidence": {},
  "knowledge_evidence": {},
  "options": {
    "max_steps": 8
  }
}
```

这里最重要的变化是：

```text
父 Agent 不需要把用户输入转成严格 task。
父 Agent 只传用户原文、对话摘要、附件和已知上下文。
CodeAnalysisAgent 自己把宽输入 normalize 成规范 task。
```

## 4. CodeAnalysisAgent 的新入口

新增两个入口：

```python
CodeAnalysisAgent.handle_input(request)
```

这是给父 Agent 使用的宽输入入口。它内部会调用：

```python
CodeAnalysisAgent.normalize_request(request)
```

生成规范 task：

```json
{
  "task_type": "flow_analysis",
  "repo_id": "workspace",
  "user_goal": "帮我分析 CodeAnalysisAgent 的流程",
  "code_signals": {
    "keywords": ["CodeAnalysisAgent"],
    "classes": [],
    "methods": [],
    "error_codes": [],
    "exceptions": [],
    "tables": [],
    "module": null,
    "rule_name": null
  },
  "evidence": {
    "log_text": "",
    "extra_text": "",
    "db": {},
    "knowledge": {}
  },
  "context_summary": "用户正在了解 OnCallAgent 的代码分析能力。",
  "max_steps": 8
}
```

然后再调用：

```python
CodeAnalysisAgent.analyze_task(task)
```

它会把通用 task 转换成内部分析输入：

- `user_goal`
- `task_type`
- `code_signals`
- `evidence.log_text`
- `evidence.db`
- `context_summary`

然后继续复用旧的代码搜索和文件读取能力。

旧入口仍然保留：

```python
CodeAnalysisAgent.analyze(repo_id, raw_log, description="", max_steps=8)
```

这样旧接口 `/api/analyze` 还能继续用。

## 5. 子 Agent HTTP 协议

### 5.1 宽输入接口，推荐父 Agent 使用

```text
POST /api/code-analysis/handle
```

请求：

```json
{
  "case_id": "CASE-001",
  "repo_id": "workspace",
  "user_message": "帮我找一下 OnCallParentAgent 调 CodeAnalysisAgent 的链路",
  "conversation_summary": "用户正在梳理父子 Agent 架构。",
  "attachments": {
    "log_text": "",
    "extra_text": ""
  },
  "known_context": {
    "module": "OnCallAgent"
  },
  "db_evidence": {},
  "knowledge_evidence": {},
  "options": {
    "max_steps": 8
  }
}
```

响应：

```json
{
  "ok": true,
  "status": "completed",
  "data": {
    "case_id": "CASE-...",
    "task_type": "code_question",
    "user_goal": "帮我找一下 OnCallParentAgent 调 CodeAnalysisAgent 的链路",
    "normalized_task": {},
    "search_terms": [],
    "steps": [],
    "snippets": [],
    "report": "..."
  }
}
```

### 5.2 规范 task 接口，推荐测试或高级调用使用

```text
POST /api/code-analysis/analyze
```

这个接口直接接收规范 task，适合自动化测试或已经有明确 task 的平台。

## 6. 父 Agent 提示词建议

如果父 Agent 只能靠大模型和提示词，建议让它保持“薄”：

```text
你是 OnCallAgent 的父 Agent。
你的职责是和用户对话、维护上下文、判断是否需要调用 CodeAnalysisAgent。

当用户问题涉及以下内容时，调用 CodeAnalysisAgent：
- 分析代码
- 查找类、方法、接口、调用链
- 根据日志定位代码问题
- 根据 lot、rule、module、DB/日志证据分析代码
- 解释某个功能如何实现
- 判断改动影响范围

调用 CodeAnalysisAgent 时，只需要传：
- 用户原始问题 user_message
- 最近几轮对话摘要 conversation_summary
- 用户提供的日志或补充材料 attachments
- 已知 lotId/fab/env/module/ruleName known_context
- repo_id

不要在父 Agent 中尝试完成代码分析。
不要自己编造代码结论。
如果 CodeAnalysisAgent 返回需要补充信息，请原样转问用户。
```

## 7. 当前测试结果

已完成测试：

- `python -m compileall app`
- 父 Agent 本地直连 CodeAnalysisAgent
- 父 Agent 通过 HTTP 调用独立 CodeAnalysisAgent 子进程
- CodeAnalysisAgent `/api/code-analysis/handle` 宽输入接口
- 纯代码问题：`帮我分析 CodeAnalysisAgent 的流程`
- 代码链路问题：`帮我找一下 OnCallParentAgent 调 CodeAnalysisAgent 的链路`
- 日志分析问题：提供 `RuleExecutionTimeoutException` 日志
- lot/fab/env 自动 mock DB + mock 日志后分析代码

## 8. 业务日志

CodeAnalysisAgent 子 Agent 已经加入本地业务日志。

日志目录：

```text
data/business_logs/code_analysis/
```

文件格式：

```text
YYYYMMDD.jsonl
```

每一行是一条 JSON 事件，便于后续用脚本、日志平台或文本工具排查。

当前会记录这些事件：

```text
code_analysis.request_received      收到父 Agent 的宽输入
code_analysis.request_normalized    宽输入已经转换成规范 task
code_analysis.request_completed     宽输入处理完成
code_analysis.request_failed        宽输入处理失败
code_analysis.task_received         收到规范 task
code_analysis.task_completed        规范 task 处理完成
code_analysis.task_failed           规范 task 处理失败
code_analysis.legacy_analyze_received   旧 analyze 入口被调用
code_analysis.legacy_analyze_completed  旧 analyze 入口处理完成
```

日志会记录：

- `request_id`
- `case_id`
- `repo_id`
- `task_type`
- 用户问题预览
- 对话摘要预览
- 日志长度和补充材料长度
- 已知上下文字段
- 搜索词数量
- 读取代码片段数量
- 步骤数量
- 报告预览
- 耗时 `duration_ms`
- 异常信息

为避免本地业务日志误提交，`.gitignore` 已加入：

```text
data/business_logs/
```

注意：当前默认只记录文本预览和长度，不完整落原始日志全文，避免日志里混入过多敏感内容。

## 9. 后续建议

下一步可以继续增强：

- 增加 `CaseMemory`，让父 Agent 支持多轮会话恢复
- 给 CodeAnalysisAgent 增加 `need_user_input` 返回协议
- 将 CodeAnalysisAgent 的 HTTP 调用改成异步任务模式
- 将 SOP、历史 CASE、需求文档接入真实知识库
- 支持业务日志按环境配置保留天数和脱敏规则
