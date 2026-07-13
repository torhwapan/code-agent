# Parent Agent 编排流程说明

本文档说明当前本地 Python 版父 Agent 的编排流程，以及它如何调用 CodeAnalysis 子 Agent。

## 1. 当前定位

当前 CodeAgent 已做减法，只保留代码分析能力。

本地父 Agent 负责：

- 接收用户输入
- 识别代码分析任务类型
- 提取 Fab、模块、ruleName、关键词等轻量上下文
- 组装 CodeAnalysis 子 Agent 请求
- 汇总代码分析结果并返回 Markdown 报告

本地父 Agent 不负责：

- 查询 DB
- 通过 FTP 获取日志
- 检索 SOP、历史 CASE、需求文档
- 管理生产环境连接信息

## 2. 代码位置

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

本地 Web 服务入口：

```text
app/main.py
```

页面请求接口：

```http
POST /api/oncall
```

## 3. 当前调用链

```text
前端页面
  -> POST /api/oncall
  -> app/main.py
  -> CTX.parent_agent.handle(payload)
  -> OnCallParentAgent.handle()
  -> IntentAgent
  -> InputParseAgent
  -> CodeAnalysisChildAgent
  -> ReportAgent
  -> 返回用户
```

## 4. 编排流程

```text
用户输入
  -> 创建 context
  -> IntentAgent 判断代码分析任务类型
  -> InputParseAgent 提取轻量上下文
  -> CodeAnalysisChildAgent 调用代码分析子 Agent
  -> ReportAgent 生成最终 Markdown 报告
  -> 返回用户
```

## 5. context 结构

父 Agent 内部使用 `context` 作为共享上下文。

主要字段：

| 字段 | 说明 |
| --- | --- |
| `status` | 当前状态，例如 running / completed |
| `intent` | 当前固定为 `code_question` |
| `task_type` | 代码任务类型 |
| `user_message` | 用户原始问题 |
| `repo_id` | 代码仓库 id |
| `max_steps` | 子 Agent 最大分析步数 |
| `parsed` | 输入解析结果 |
| `extra_text` | 用户提供的补充上下文 |
| `code_result` | 代码分析结果 |
| `report` | 最终 Markdown 报告 |
| `steps` | 编排步骤记录 |

## 6. IntentAgent

代码位置：

```text
app/agents/intent_agent.py
```

当前版本不再做复杂业务意图判断。所有输入都按代码分析处理，只区分任务类型：

| task_type | 说明 |
| --- | --- |
| `code_question` | 通用代码问题 |
| `flow_analysis` | 流程 / 调用链分析 |
| `impact_analysis` | 影响范围分析 |
| `bug_hunt` | bug / 异常排查 |

## 7. InputParseAgent

代码位置：

```text
app/agents/input_parse_agent.py
```

负责从用户输入和补充上下文中提取：

- `fab`
- `module`
- `rule_name`
- `keywords`

这些字段会传给 CodeAnalysis，帮助它更快定位相关代码。

## 8. CodeAnalysisChildAgent

代码位置：

```text
app/agents/code_analysis_agent.py
```

它负责把父 Agent 的 `context` 转成 CodeAnalysis HTTP 接口需要的结构：

```json
{
  "case_id": "",
  "repo_id": "workspace",
  "user_message": "用户问题",
  "conversation_summary": "压缩后的上下文",
  "attachments": {
    "extra_text": "补充上下文"
  },
  "known_context": {
    "fab": "Fab1",
    "module": "MES",
    "rule_name": "SomeRule"
  },
  "options": {
    "max_steps": 8
  }
}
```

## 9. 两种调用方式

### 9.1 本地模式

如果没有配置 `CODE_ANALYSIS_AGENT_URL`：

```python
result = self.code_agent.handle_input(request)
```

也就是直接调用本进程中的 Python 对象。

### 9.2 远程 HTTP 模式

如果配置：

```text
CODE_ANALYSIS_AGENT_URL=http://127.0.0.1:8010
```

则会调用：

```http
POST /api/code-analysis/handle
```

这更接近公司平台里“把 CodeAnalysis HTTP 接口作为工具”的方式。

## 10. ReportAgent

代码位置：

```text
app/agents/report_agent.py
```

负责汇总：

- 当前判断
- 输入解析
- 代码分析结果

最终返回 Markdown 报告。

## 11. 返回结构

父 Agent 最终返回：

```json
{
  "ok": true,
  "status": "completed",
  "intent": "code_question",
  "task_type": "code_question",
  "answer": "...",
  "report": "...",
  "steps": [],
  "context": {
    "parsed": {},
    "code_result": {}
  }
}
```

页面当前主要展示：

- `report`
- `steps`

## 12. 和公司平台父 Agent 的关系

当前本地父 Agent 是 Python 代码编排，方便本地测试。

公司平台父 Agent 可能无法写 Python 编排逻辑，而是靠 LLM + prompt + tool schema 调用工具。此时建议采用三层结构：

```text
平台父 Agent
  -> 平台代码分析子 Agent
       -> CodeAgent HTTP 服务 /api/code-analysis/handle
```

建议：

1. 平台父 Agent 使用 `prompts/platform_parent_agent_prompt.md`。
2. 平台代码分析子 Agent 使用 `prompts/code_analysis_child_agent_prompt.md`。
3. 把 `/api/code-analysis/handle` 配成代码分析子 Agent 可调用的 HTTP 工具。
4. 父 Agent 负责对话、全局上下文和最终回复。
5. 代码分析子 Agent 负责追问厂别/系统、选择 `repo_id`、组装 HTTP 请求。
6. CodeAgent HTTP 服务只负责一次性代码分析。

详细契约见：

```text
docs/platform_agent_contracts.md
docs/platform_project_structure.md
```

## 13. 后续建议

1. 新增 CodeRepoRouter，负责 MES/EAP/Fab 到 repo_id 的选择。
2. 扩展 `configs/repositories.json`，配置多套代码库。
3. 给 CodeAnalysis 增加流式输出接口。
4. 把 `app/logs/parser.py` 改名为更中性的 `context_parser.py`，避免概念上还像日志系统。
