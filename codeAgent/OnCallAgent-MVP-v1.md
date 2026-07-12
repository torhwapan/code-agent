# OnCallAgent MVP v1 设计

## 1. 第一版目标

第一版 OnCallAgent 先做简单、聚焦、可落地的能力：

> OP 上传或粘贴错误日志后，Agent 根据日志分析本机代码目录中的相关代码，并生成代码分析报告。

第一版先不追求完整 OnCallAgent 平台，而是优先把“日志 -> 代码定位 -> 多轮代码分析 -> 报告”这条链路做扎实。

## 2. 第一版范围

### 2.1 包含

- OP 粘贴错误日志或上传日志文件。
- OP 可选填写报案描述、系统、模块。
- Agent 解析日志，提取错误码、异常、类名、方法名、SQL、表名、关键日志行。
- Agent 根据日志线索搜索本机配置好的代码目录。
- Agent 通过受控工具读取相关代码文件。
- Agent 使用 LLM 多轮分析多个文件之间的关系。
- Agent 输出结构化代码分析报告。
- 没有配置 LLM 时，支持规则回退分析。

### 2.2 暂不包含

- 实时 DB 查询。
- 生产环境自动处置。
- 完整 Incident Workflow。
- 完整 Evidence Graph。
- Temporal / LangGraph 编排。
- 复杂审批流。
- MES、R2R、EAP、APC 多系统联动。
- 自动接入日志平台。
- 需求文档知识库检索。

需求知识库、日志平台、DB 查询都放到后续版本。

## 3. 第一版交互方式

第一版采用：

```text
先上传日志
 -> Agent 自动分析
 -> 生成第一版诊断报告
 -> OP 再基于同一个 Case 追问或补充上下文
```

不要一开始就让 OP 反复回答问题。OP 现场处理报案时通常压力比较大，Agent 应该先尽量从日志里自动提取信息并做初步分析。

只有在信息不足时，Agent 才需要追问，例如：

- 无法判断系统或模块。
- 日志太短，没有错误码、类名、方法名、堆栈。
- 代码搜索命中太多，需要缩小范围。
- 多个模块都可能相关，需要 OP 确认。
- 置信度较低，但补充一个字段就能明显提升判断。

## 4. MVP 业务架构

```text
OP / Engineer
    |
    v
Web 页面
    |
    v
Case Analyzer
    |
    |-- Log Parser
    |-- Code Analysis Agent
    |-- LLM Client
    |-- Report Generator
    |
    v
代码分析报告
```

### 4.1 业务角色

| 角色 | 第一版职责 |
| --- | --- |
| OP | 上传日志、描述现象、查看报告、执行人工确认 |
| CIM Engineer | 查看代码分析结果、确认根因、补充后续修复建议 |
| 系统负责人 | 维护代码仓库配置、模块边界和负责人信息 |
| Agent 管理员 | 维护模型配置、仓库白名单、安全边界 |

### 4.2 业务对象

| 对象 | 说明 |
| --- | --- |
| Case | 一次日志分析会话 |
| Log Input | OP 粘贴或上传的原始日志 |
| Parsed Log | 从日志中提取出的结构化线索 |
| Search Term | 用于搜索代码的关键词 |
| Code Match | 代码搜索命中结果 |
| Code Snippet | 读取进来的代码片段 |
| Agent Step | Agent 每一轮搜索、读取或停止动作 |
| Diagnosis Report | 最终代码分析报告 |

## 5. MVP 技术架构

```text
浏览器
  |
  v
Python HTTP Server
  |
  v
CodeAnalysisAgent
  |
  |-- LogParser
  |-- LLMClient
  |-- LocalCodeTools
  |     |-- search_code
  |     |-- read_file
  |     |-- read_around
  |
  v
data/cases/*.json
```

### 5.1 当前运行组件

| 组件 | 文件 | 职责 |
| --- | --- | --- |
| Web 页面 | `app/web/index.html` | 填写日志、上传文件、展示报告和步骤 |
| Web API | `app/main.py` | 提供 `/api/analyze`、`/api/repositories` 等接口 |
| 日志解析 | `app/logs/parser.py` | 从日志中提取结构化信号 |
| Agent 主体 | `app/code_analysis/agent.py` | 多轮搜索、读取、分析和报告生成 |
| 本地代码工具 | `app/code_analysis/tools.py` | 受控搜索和读取本地代码 |
| 仓库配置 | `app/code_analysis/config.py` | 加载代码仓库白名单配置 |
| LLM 适配 | `app/code_analysis/llm.py` | 屏蔽 OpenAI、DeepSeek、千问等模型差异 |
| 仓库配置文件 | `configs/repositories.json` | 配置可读取的代码目录 |

## 6. Code Analysis Agent 设计

代码分析不是一次 LLM 调用，而是一个多轮 Agent 流程：

```text
解析日志
 -> 提取搜索线索
 -> LLM 决定下一步
 -> 搜索代码
 -> LLM 决定读取哪个文件
 -> 读取代码片段
 -> LLM 根据新证据继续规划
 -> 多轮循环
 -> 生成最终报告
```

核心循环是：

```text
Plan -> Tool -> Observe -> Plan -> Tool -> Observe -> Final Report
```

### 6.1 LLM 负责什么

LLM 负责推理和规划：

- 判断先查哪个类、方法、错误码或表名。
- 根据搜索结果选择应该读哪个文件。
- 读完一个文件后，判断是否要继续查调用方、被调用方、配置文件、Mapper XML、SQL 文件。
- 把多个文件串成可能的调用链。
- 输出代码层面的可能原因、证据和下一步建议。

### 6.2 工具负责什么

工具负责安全执行：

```text
search_code(query)
read_file(path, start_line, end_line)
read_around(path, center_line)
```

LLM 不能执行任意 shell，也不能读取服务器任意路径。它只能通过受控工具访问 `configs/repositories.json` 中配置的仓库目录。

### 6.3 Agent 状态

每次分析都会维护一个 `AgentState`：

```json
{
  "case_id": "CASE-20260706-001",
  "repo_id": "workspace",
  "description": "Lot cannot track out",
  "parsed_log": {},
  "search_terms": [],
  "steps": [],
  "matches": [],
  "snippets": [],
  "observations": [],
  "errors": []
}
```

这个状态就是 Agent 的工作记忆，也是前端展示“分析过程”的来源。

## 7. 日志解析

第一版用规则解析日志，先提取最常见的定位信息：

- 错误码，例如 `MES-LOT-STATE-409`、`ORA-00060`。
- 异常类型，例如 `NullPointerException`、`TimeoutException`。
- Java stack trace 中的类名、方法名、文件名、行号。
- 数据库表名，例如 `WIP_LOT_STATE`。
- SQL 片段。
- 包含 `error`、`failed`、`timeout`、`mismatch` 等关键词的日志行。
- 时间戳。

后续可以再引入 LLM 辅助解析更复杂的非结构化日志。

## 8. 多模型适配设计

你们公司同时有千问、DeepSeek、OpenAI，这时不要让业务代码直接绑定某一个模型 SDK。

推荐做法：

```text
CodeAnalysisAgent
    |
    v
LLMClient / LLMGateway
    |
    |-- OpenAI Adapter
    |-- DeepSeek Adapter
    |-- Qwen Adapter
    |-- Internal Gateway Adapter
```

当前代码已经使用 `LLMClient` 做统一适配。Agent 只调用：

```python
llm.chat(messages, json_mode=True)
```

Agent 不关心底层是谁。

### 8.1 需要屏蔽的模型差异

| 差异 | 处理方式 |
| --- | --- |
| API 地址不同 | 放在 `LLM_BASE_URL` |
| 模型名称不同 | 放在 `LLM_MODEL` |
| API Key 不同 | 放在 `LLM_API_KEY` |
| JSON mode 支持不同 | 用 `LLM_SUPPORTS_JSON_MODE` 控制 |
| temperature/top_p 支持不同 | 用 `LLM_INCLUDE_TEMPERATURE`、`LLM_TEMPERATURE`、`LLM_TOP_P` 控制 |
| max token 参数名不同 | 用 `LLM_MAX_TOKENS_PARAM` 控制 |
| 模型或网关私有参数 | 用 `LLM_EXTRA_PARAMS` 追加 |
| 上下文长度不同 | 后续在适配层加 token budget |
| 输出风格不同 | 用统一 prompt 和结构化输出约束 |
| 错误格式不同 | 在适配层统一异常 |
| 函数调用能力不同 | 第一版不用厂商 function calling，统一用 JSON 动作协议 |

### 8.2 推荐环境变量

```powershell
$env:LLM_PROVIDER="openai"     # openai / deepseek / qwen / custom
$env:LLM_API_KEY="your-key"
$env:LLM_BASE_URL="https://api.openai.com/v1"
$env:LLM_MODEL="gpt-4o-mini"
$env:LLM_SUPPORTS_JSON_MODE="true"
```

DeepSeek：

```powershell
$env:LLM_PROVIDER="deepseek"
$env:LLM_API_KEY="your-key"
$env:LLM_MODEL="deepseek-chat"
```

千问：

```powershell
$env:LLM_PROVIDER="qwen"
$env:LLM_API_KEY="your-key"
$env:LLM_MODEL="qwen-plus"
```

公司内部模型网关：

```powershell
$env:LLM_PROVIDER="custom"
$env:LLM_API_KEY="your-key"
$env:LLM_BASE_URL="http://your-internal-llm-gateway/v1"
$env:LLM_MODEL="your-model-name"
$env:LLM_SUPPORTS_JSON_MODE="false"
```

### 8.3 最佳实践

- 优先让公司内部模型平台提供 OpenAI-compatible 接口。
- Agent 内部不要使用厂商专属 SDK。
- Agent 和模型之间用统一 JSON 协议沟通。
- 不同模型的特殊参数只放在 `LLMClient`。
- 对 JSON 解析失败、超时、HTTP 错误做统一兜底。
- 重要动作不要依赖模型自由发挥，只允许返回白名单动作。

### 8.4 可选参数适配

不同模型虽然可能都兼容 `/v1/chat/completions`，但可选参数经常不同。第一版用环境变量屏蔽这些差异：

```powershell
$env:LLM_INCLUDE_TEMPERATURE="true"
$env:LLM_TEMPERATURE="0.2"
$env:LLM_TOP_P="0.8"
$env:LLM_MAX_TOKENS="4096"
$env:LLM_MAX_TOKENS_PARAM="max_tokens"
$env:LLM_EXTRA_PARAMS='{"enable_thinking": false}'
```

如果某个模型不支持 `temperature`，就设置：

```powershell
$env:LLM_INCLUDE_TEMPERATURE="false"
```

如果某个模型使用不同的 token 参数名，例如 `max_completion_tokens`，就设置：

```powershell
$env:LLM_MAX_TOKENS_PARAM="max_completion_tokens"
```

## 9. 技术选型

| 部分 | 当前选择 | 原因 |
| --- | --- | --- |
| 语言 | Python | 适合快速构建 Agent、RAG、代码分析工具 |
| Web 服务 | Python 标准库 HTTP Server | 第一版无外部依赖，方便跑通 |
| 前端 | 原生 HTML/CSS/JS | 简单、无需构建 |
| 代码搜索 | ripgrep | 快速、稳定、适合本地代码搜索 |
| 文件读取 | 受控 read_file 工具 | 限制读取范围，便于审计 |
| Case 存储 | JSON 文件 | 第一版简单可查，后续可迁移 DB |
| LLM 接入 | OpenAI-compatible HTTP | 便于接 OpenAI、DeepSeek、千问或内部网关 |

## 10. 当前 API

```text
GET  /api/repositories
POST /api/analyze
GET  /api/cases/{case_id}
```

`POST /api/analyze` 输入：

```json
{
  "repo_id": "workspace",
  "description": "Lot cannot track out",
  "log_text": "...",
  "max_steps": 8
}
```

## 11. 后续演进

建议按这个顺序扩展：

1. 加入需求文档知识库。
2. 加入日志平台自动查询。
3. 加入 Git 最近变更分析。
4. 加入 tree-sitter / Semgrep 做更准的代码结构分析。
5. 加入 follow-up 多轮问答。
6. 加入 Evidence Graph。
7. 加入 DB 只读查询。
8. 迁移到 FastAPI + PostgreSQL。
9. 引入 LangGraph 管理复杂代码分析流程。

## 12. 总结

第一版的核心价值是：

```text
上传日志
 -> 提取线索
 -> 多轮搜索代码
 -> 读取相关文件
 -> LLM 分析多个代码片段
 -> 输出代码分析报告
```

这一版先把代码分析做成一个受控、可解释、可替换模型的子 Agent。后续再逐步接需求知识库、日志平台和 DB 查询。
