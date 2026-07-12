# Parent Agent 编排流程说明

本文档说明当前本地 Python 版父 Agent 的编排流程、核心代码位置、上下文结构，以及它和公司平台 LLM 父 Agent 的区别。

## 1. 当前父 Agent 是什么

当前本地父 Agent 是一个代码编排型 Agent。

它不是靠 LLM 自己规划下一步，而是由 Python 代码按固定流程调用各个子 Agent。

核心代码：

```text
app/agents/parent_agent.py
```

核心类：

```python
class OnCallParentAgent
```

核心入口：

```python
OnCallParentAgent.handle(payload)
```

## 2. 请求入口

本地 Web 服务入口：

```text
app/main.py
```

页面请求接口：

```http
POST /api/oncall
```

调用链：

```text
前端页面
  -> POST /api/oncall
  -> app/main.py
  -> CTX.parent_agent.handle(payload)
  -> OnCallParentAgent.handle()
```

## 3. 父 Agent 负责什么

父 Agent 负责：

- 接收用户输入
- 判断用户意图
- 解析 lotId / fab / env / module / ruleName
- 判断是否需要追问补充字段
- 调用知识库 Agent
- 调用 DB 调查 Agent
- 调用日志检索 Agent
- 调用 CodeAnalysis 子 Agent
- 汇总所有结果
- 生成最终报告

父 Agent 不负责：

- 直接分析代码细节
- 直接读取代码文件
- 直接调用 CodeGraph
- 直接连接 FTP
- 直接查询真实生产 DB

这些事情交给对应子 Agent 或工具处理。

## 4. 总体编排流程

当前流程如下：

```text
用户输入
  -> 创建 context
  -> IntentAgent 判断意图
  -> InputParseAgent 解析输入字段
  -> 检查是否缺少必要字段
  -> KnowledgeRouterAgent 第一轮知识库查询
  -> 如果需要检索日志：
       -> DBInvestigationAgent
       -> LogRetrievalAgent
     如果用户已提供日志：
       -> 直接使用用户日志
  -> KnowledgeRouterAgent 第二轮知识库查询
  -> 如果需要代码分析：
       -> CodeAnalysisChildAgent
  -> ReportAgent 汇总报告
  -> 返回用户
```

## 5. 初始化上下文

父 Agent 收到请求后，会先执行：

```python
context = self._new_context(payload)
```

`context` 是整个编排过程的共享上下文。

主要字段：

| 字段 | 说明 |
| --- | --- |
| `status` | 当前状态，例如 running / completed / need_more_info |
| `intent` | 用户意图 |
| `log_source` | 日志来源 |
| `task_type` | 任务类型 |
| `user_message` | 用户原始问题 |
| `repo_id` | 代码仓库 id |
| `max_steps` | 子 Agent 最大分析步数 |
| `parsed` | 输入解析结果 |
| `db_result` | DB 调查结果 |
| `log_result` | 日志检索结果 |
| `log_text` | 最终用于分析的日志文本 |
| `knowledge` | 知识库检索结果 |
| `code_result` | 代码分析结果 |
| `missing_fields` | 缺少的字段 |
| `question` | 需要追问用户的问题 |
| `answer` | 最终答复 |
| `report` | 最终 Markdown 报告 |
| `steps` | 编排步骤记录 |

## 6. IntentAgent：判断意图

代码位置：

```text
app/agents/intent_agent.py
```

调用：

```python
intent = self.intent_agent.decide(payload)
```

输出字段：

```json
{
  "intent": "code_question",
  "log_source": "none",
  "task_type": "code_question",
  "reason": "..."
}
```

### 6.1 intent

| 值 | 说明 |
| --- | --- |
| `code_question` | 单纯代码问题 |
| `code_with_log` | 代码 + 日志问题 |
| `knowledge_question` | 知识库问题 |

### 6.2 log_source

| 值 | 说明 |
| --- | --- |
| `none` | 不涉及日志 |
| `user_provided` | 用户直接提供日志 |
| `need_retrieve` | 用户给了条件，需要系统检索日志 |

### 6.3 task_type

| 值 | 说明 |
| --- | --- |
| `code_question` | 通用代码问题 |
| `log_diagnosis` | 日志诊断 |
| `flow_analysis` | 流程 / 调用链分析 |
| `impact_analysis` | 影响范围分析 |
| `bug_hunt` | bug / 异常排查 |
| `knowledge_question` | 知识库问题 |

## 7. InputParseAgent：解析输入字段

代码位置：

```text
app/agents/input_parse_agent.py
```

调用：

```python
context["parsed"] = self.input_agent.run(payload)
```

主要解析：

- `lot_id`
- `fab`
- `env`
- `module`
- `rule_name`
- `keywords`
- `log_signals`

这些字段后面会传给：

- DBInvestigationAgent
- LogRetrievalAgent
- KnowledgeRouterAgent
- CodeAnalysisChildAgent

## 8. 缺参判断

如果当前任务需要系统自己检索日志：

```python
context["log_source"] == "need_retrieve"
```

则必须具备：

```text
lot_id
fab
env
```

缺失时，父 Agent 不继续执行后续 DB / 日志 / 代码分析，而是返回：

```json
{
  "status": "need_more_info",
  "missing_fields": ["lot_id", "fab"],
  "question": "还需要补充：lotId、厂别..."
}
```

对应代码：

```python
missing = self._missing_fields(context)
```

## 9. KnowledgeRouterAgent：知识库查询

代码位置：

```text
app/agents/knowledge_router_agent.py
```

当前是 mock 实现。

父 Agent 会调用两次：

### 9.1 第一轮 pre

```python
context["knowledge"]["pre"] = self.knowledge_agent.run(context, phase="pre")
```

目的：

- 根据用户原始输入和初步解析字段，查一些粗粒度 SOP / CASE / 需求文档。

### 9.2 第二轮 post

```python
context["knowledge"]["post"] = self.knowledge_agent.run(context, phase="post")
```

目的：

- 在 DB / 日志结果出来后，再根据更精确的 ruleName、module、error 信息查询知识库。

## 10. DBInvestigationAgent：DB 调查

代码位置：

```text
app/agents/db_investigation_agent.py
```

调用条件：

```python
context["log_source"] == "need_retrieve"
```

调用：

```python
context["db_result"] = self.db_agent.run(context)
```

目标：

- 根据 lotId / fab / env 查询 lot 历史
- 判断对应 ruleName
- 判断 module
- 判断 server_ip
- 判断 handled_at
- 为日志检索提供精确时间和目录线索

当前可以使用 mock 数据，后续接真实 DB。

## 11. LogRetrievalAgent：日志检索

代码位置：

```text
app/agents/log_retrieval_agent.py
```

调用条件：

```python
context["log_source"] == "need_retrieve"
```

调用：

```python
context["log_result"] = self.log_agent.run(context)
context["log_text"] = context["log_result"].get("data", {}).get("log_text", "")
```

目标：

- 根据 DB 定位结果找到日志目录
- 通过 FTP 或 mock 获取日志
- 提取关键时间点附近日志
- 产出 `log_text`

## 12. 用户直接提供日志的情况

如果用户已经贴了日志：

```python
context["log_source"] == "user_provided"
```

父 Agent 会直接使用用户日志：

```python
context["log_text"] = payload.get("log_text") or ""
```

这种情况下不会先调用 DB 和日志检索。

## 13. CodeAnalysisChildAgent：代码分析

代码位置：

```text
app/agents/code_analysis_agent.py
```

调用条件：

```python
context.get("intent") in {"code_question", "code_with_log"}
```

对应方法：

```python
def _need_code_analysis(self, context):
    return context.get("intent") in {"code_question", "code_with_log"}
```

调用：

```python
context["code_result"] = self.code_agent.run(context)
```

## 14. CodeAnalysisChildAgent 做了什么

`CodeAnalysisChildAgent` 会把父 Agent 的 `context` 转换成 CodeAnalysis HTTP 接口需要的请求结构。

请求结构：

```json
{
  "case_id": "",
  "repo_id": "workspace",
  "user_message": "用户问题",
  "conversation_summary": "压缩后的上下文",
  "attachments": {
    "log_text": "日志文本",
    "extra_text": ""
  },
  "known_context": {
    "lot_id": "L123456",
    "fab": "Fab1",
    "env": "prod",
    "module": "TrackIn",
    "rule_name": "TrackInRule"
  },
  "db_evidence": {},
  "knowledge_evidence": {},
  "options": {
    "max_steps": 8
  }
}
```

## 15. CodeAnalysisChildAgent 的两种调用方式

### 15.1 本地模式

如果没有配置 `CODE_ANALYSIS_AGENT_URL`：

```python
result = self.code_agent.handle_input(request)
```

也就是直接调用本进程中的 Python 对象。

### 15.2 远程 HTTP 模式

如果配置了：

```text
CODE_ANALYSIS_AGENT_URL=http://127.0.0.1:8010
```

则会调用：

```http
POST /api/code-analysis/handle
```

代码：

```python
result = self._call_remote_agent(request)
```

这更接近公司平台里“把 CodeAnalysis HTTP 接口作为工具”的方式。

## 16. CodeAnalysis 返回给父 Agent 的结构

当前 `CodeAnalysisChildAgent.run()` 会返回：

```json
{
  "ok": true,
  "agent": "CodeAnalysisAgent",
  "summary": "代码分析完成...",
  "answer_markdown": "## 结论\n...",
  "evidence": [],
  "diagnosis": {},
  "debug": {},
  "data": {},
  "child_request": {},
  "task": {},
  "warnings": []
}
```

父 Agent 和最终报告应优先使用：

- `summary`
- `answer_markdown`
- `evidence`
- `diagnosis`
- `debug`

完整 `data` 用于调试，不建议直接展示给用户。

## 17. ReportAgent：最终报告

代码位置：

```text
app/agents/report_agent.py
```

调用：

```python
context["report"] = self.report_agent.run(context)
context["answer"] = context["report"]
```

它会汇总：

- 当前判断
- 输入解析
- DB 证据
- 日志证据
- 知识库参考
- 代码分析结果
- 注意事项

最终返回 Markdown 报告。

## 18. 返回给前端的结构

父 Agent 最终返回：

```json
{
  "ok": true,
  "status": "completed",
  "intent": "code_question",
  "log_source": "none",
  "task_type": "code_question",
  "answer": "...",
  "question": "",
  "report": "...",
  "steps": [],
  "context": {
    "parsed": {},
    "db_result": {},
    "log_result": {},
    "knowledge": {},
    "code_result": {},
    "missing_fields": []
  }
}
```

页面当前主要展示：

- `report`
- `steps`

## 19. 当前本地父 Agent 和公司平台父 Agent 的区别

### 19.1 当前本地 Python 父 Agent

特点：

- 代码编排
- 固定流程
- 规则判断意图
- 规则解析字段
- 由 Python 代码决定调用哪些子 Agent

它的逻辑在：

```text
app/agents/parent_agent.py
```

### 19.2 公司平台父 Agent

特点：

- 平台封装
- 可能无法写 Python 编排逻辑
- 主要靠 LLM + prompt + tool schema 调用工具
- CodeAnalysis HTTP 接口会作为工具接入

公司平台父 Agent 需要使用：

```text
app/agents/code_analysis_tool_prompt_agent.py
```

里面的提示词告诉父 Agent：

- 什么时候调用 CodeAnalysis
- 怎么选择 repo_id
- 怎么传日志
- 怎么传 DB / SOP / CASE 结果
- 返回后该看哪些字段

## 20. 当前流程的优点

1. 流程稳定，可预测。
2. 每个子 Agent 职责清晰。
3. CodeAnalysis 可以本地调用，也可以 HTTP 调用。
4. 后续迁移到公司平台时，CodeAnalysis 可以独立作为工具。
5. 父 Agent 最终输出 Markdown，适合聊天页面展示。

## 21. 当前流程的限制

1. 本地父 Agent 不是 LLM 规划型，灵活性有限。
2. 意图识别和字段解析目前是规则实现，复杂表达可能识别不准。
3. 知识库、DB、日志检索部分还有 mock。
4. 多代码仓库路由还需要进一步配置化。
5. 流式输出还未实现。

## 22. 后续建议

建议后续逐步补充：

1. 新增 CodeRepoRouter，负责 MES/EAP/Fab 到 repo_id 的选择。
2. 扩展 `configs/repositories.json`，配置多套代码库。
3. DBInvestigationAgent 接真实 DB。
4. LogRetrievalAgent 接真实 FTP 日志。
5. KnowledgeRouterAgent 接 SOP / CASE / 需求文档 RAG。
6. 增加流式输出接口，先流式输出步骤，再考虑 LLM token 流式输出。

