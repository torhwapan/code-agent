# CodeAnalysis HTTP 接口说明

本文档说明 CodeAgent HTTP 服务作为代码分析工具提供给“平台代码分析子 Agent”调用时的接口、入参、出参和使用建议。

## 1. 服务定位

当前 CodeAgent 只做一件事：分析代码。

它负责：

- 根据用户问题分析代码
- 根据异常堆栈、报错片段等补充上下文定位相关代码
- 调用 CodeGraph 查询代码地图
- 必要时读取文件片段
- 输出面向平台代码分析子 Agent 的结构化结果
- 输出可直接展示给用户的 Markdown 分析报告

它不负责：

- 查询 DB
- 通过 FTP 获取日志
- 检索 SOP、历史 CASE、需求文档知识库
- 管理生产环境连接信息

## 2. 服务启动

独立 CodeAnalysis 服务启动方式：

```powershell
cd D:\Professional\myCode\codeAnalysis\codeAgent
python -m app.code_analysis.server --host 127.0.0.1 --port 8010
```

默认地址：

```text
http://127.0.0.1:8010
```

健康检查：

```http
GET /health
```

响应：

```json
{
  "ok": true,
  "service": "code-analysis-agent"
}
```

## 3. 推荐接口

平台代码分析子 Agent 推荐调用：

```http
POST /api/code-analysis/handle
Content-Type: application/json
```

该接口接收平台代码分析子 Agent 整理后的代码分析请求，内部会自动归一化为 CodeAnalysis 任务。

## 4. 请求结构

推荐请求：

```json
{
  "case_id": "可选，平台侧 case id",
  "repo_id": "mes_fab12",
  "user_message": "用户当前代码分析问题",
  "conversation_summary": "可选，压缩后的必要对话上下文",
  "attachments": {
    "extra_text": "可选，异常堆栈、代码片段、接口名、业务规则名等补充上下文"
  },
  "known_context": {
    "fab": "Fab1",
    "module": "TrackIn",
    "rule_name": "SomeRule",
    "code_system": "MES",
    "code_repo_id": "mes_fab12"
  },
  "options": {
    "max_steps": 8
  }
}
```

### 4.1 顶层字段

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `case_id` | string | 否 | 外部平台 case id，便于串联业务日志 |
| `repo_id` | string | 否 | 代码仓库 id，默认 `workspace` |
| `user_message` | string | 建议 | 用户当前代码分析问题 |
| `message` | string | 否 | `user_message` 的兼容字段 |
| `description` | string | 否 | `user_message` 的兼容字段 |
| `conversation_summary` | string | 否 | 平台父 Agent 或代码分析子 Agent 压缩后的历史上下文 |
| `attachments` | object | 否 | 补充上下文 |
| `known_context` | object | 否 | 平台已识别出的结构化上下文 |
| `options` | object | 否 | 分析选项 |

### 4.2 `attachments`

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `extra_text` | string | 否 | 异常堆栈、代码片段、接口名、业务规则名等补充上下文 |

兼容写法：

```json
{
  "extra_text": "也可以直接放顶层"
}
```

说明：旧版本支持 `log_text`，当前版本建议统一使用 `extra_text`。如果用户贴了报错或堆栈，也把它作为补充上下文传入，不表示 CodeAgent 会去检索日志。

### 4.3 `known_context`

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `fab` | string | 否 | Fab1 / Fab2 / Fab3 |
| `module` | string | 否 | 模块名 |
| `rule_name` | string | 否 | Rule 名称 |
| `code_system` | string | 否 | MES / EAP / R2R / CIM 等 |
| `code_repo_id` | string | 否 | 代码分析子 Agent 选择出的代码仓库 id |

注意：实际选择代码仓库主要看顶层 `repo_id`。`known_context.code_repo_id` 只用于记录代码分析子 Agent 的选择理由。

### 4.4 `options`

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `max_steps` | number | 8 | LLM 规划搜索、读文件的最大步数 |

## 5. 代码仓库选择

平台代码分析子 Agent 应该在调用前确定 `repo_id`。

建议 repo_id：

```text
mes_fab12
mes_fab3
eap_fab1
eap_fab2
eap_fab3
```

默认规则：

1. 用户未说明系统，默认 MES。
2. 用户未说明 Fab，默认 Fab1/Fab2 的 MES 代码。
3. MES + Fab1/Fab2 -> `mes_fab12`
4. MES + Fab3 -> `mes_fab3`
5. EAP + Fab1 -> `eap_fab1`
6. EAP + Fab2 -> `eap_fab2`
7. EAP + Fab3 -> `eap_fab3`

如果平台暂时只配置了当前项目，可以使用：

```json
"repo_id": "workspace"
```

## 6. 请求示例

### 6.1 单纯代码分析

```json
{
  "repo_id": "workspace",
  "user_message": "帮我分析 app/code_analysis/agent.py 的分析流程",
  "options": {
    "max_steps": 8
  }
}
```

### 6.2 结合异常堆栈分析代码

```json
{
  "repo_id": "mes_fab12",
  "user_message": "帮我根据这个异常堆栈分析相关代码原因",
  "attachments": {
    "extra_text": "2026-07-12 10:01:02 ERROR ... NullReferenceException ..."
  },
  "known_context": {
    "fab": "Fab1",
    "code_system": "MES",
    "code_repo_id": "mes_fab12"
  },
  "options": {
    "max_steps": 8
  }
}
```

### 6.3 分析修改影响范围

```json
{
  "repo_id": "eap_fab2",
  "user_message": "如果修改 AlarmHandler.handle 方法，会影响哪些调用链？",
  "known_context": {
    "fab": "Fab2",
    "module": "Alarm",
    "code_system": "EAP",
    "code_repo_id": "eap_fab2"
  },
  "options": {
    "max_steps": 10
  }
}
```

## 7. 响应结构

成功响应：

```json
{
  "ok": true,
  "status": "completed",
  "data": {
    "case_id": "CASE-20260712-182605-2F4B3E",
    "repo_id": "workspace",
    "task_type": "code_question",
    "summary": "代码分析完成，已使用 CodeGraph 获取代码地图上下文。",
    "answer_markdown": "## 结论\n\n...",
    "evidence": [],
    "diagnosis": {},
    "debug": {},
    "normalized_task": {},
    "steps": [],
    "matches": [],
    "snippets": [],
    "codegraph_results": [],
    "errors": [],
    "report": "## ..."
  }
}
```

失败响应：

```json
{
  "ok": false,
  "error": "错误信息"
}
```

## 8. 平台代码分析子 Agent 应优先读取的字段

| 字段 | 说明 |
| --- | --- |
| `data.summary` | 一句话摘要 |
| `data.answer_markdown` | 给用户看的 Markdown 答案 |
| `data.evidence` | 代码证据摘要 |
| `data.diagnosis` | 结构化诊断结果 |
| `data.debug` | 调试摘要 |

不建议直接展示：

| 字段 | 说明 |
| --- | --- |
| `data.steps` | 调试用步骤明细 |
| `data.matches` | 搜索命中明细 |
| `data.snippets` | 代码片段全文 |
| `data.codegraph_results` | CodeGraph 原始输出，可能较长 |
| `data.normalized_task` | 子 Agent 内部标准化任务 |

## 9. CodeGraph 前置条件

目标代码目录建议先执行：

```powershell
codegraph init
```

每套代码仓库都要单独初始化。

例如：

```powershell
cd D:\CompanyCode\MES-Fab12
codegraph init

cd D:\CompanyCode\EAP-Fab1
codegraph init
```

如果没有初始化，CodeAnalysis 仍会尝试用文件搜索和文件读取回答，但速度和准确性会下降。

## 10. 调用建议

1. 涉及代码的问题，父 Agent 应优先调用平台代码分析子 Agent。
2. 代码分析子 Agent 调用 CodeAgent 前应选择正确 `repo_id`。
3. 不要把完整历史对话塞进 `conversation_summary`。
4. 异常堆栈、代码片段、接口名等补充信息放入 `attachments.extra_text`。
5. 最终给用户展示时，优先使用 `data.answer_markdown`。
6. 如果 `data.debug.error_count > 0`，代码分析子 Agent 可以把风险提示返回给父 Agent。
