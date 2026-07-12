# CodeAnalysis HTTP 接口说明

本文档说明 CodeAnalysis 子 Agent 作为 HTTP 工具提供给父 Agent 调用时的接口、入参、出参和使用建议。

## 1. 服务定位

CodeAnalysis 是代码分析子 Agent。

它负责：

- 根据用户问题分析代码
- 根据错误日志定位相关代码
- 调用 CodeGraph 查询代码地图
- 必要时读取文件片段
- 输出面向父 Agent 的结构化结果
- 输出可直接展示给用户的 Markdown 分析报告

父 Agent 不需要理解 CodeGraph、文件搜索、代码读取等细节，只需要选择正确的 `repo_id`，整理好用户问题和上下文，然后调用 CodeAnalysis。

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

父 Agent 推荐调用：

```http
POST /api/code-analysis/handle
```

请求头：

```http
Content-Type: application/json
```

该接口接收“父 Agent 整理后的用户请求”，内部会自动归一化为代码分析任务。

## 4. 请求参数

完整请求结构：

```json
{
  "case_id": "可选，父 Agent 或平台侧 case id",
  "repo_id": "mes_fab12",
  "user_message": "用户原始问题",
  "conversation_summary": "压缩后的对话上下文",
  "attachments": {
    "log_text": "用户提供的日志或日志检索结果",
    "extra_text": "补充材料，例如 DB 结果、SOP 摘要、历史 CASE 摘要"
  },
  "known_context": {
    "lot_id": "L123456",
    "fab": "Fab1",
    "env": "prod",
    "module": "TrackIn",
    "rule_name": "SomeRule",
    "code_system": "MES",
    "code_repo_id": "mes_fab12"
  },
  "db_evidence": {
    "summary": "DB 查询摘要",
    "data": {}
  },
  "knowledge_evidence": {
    "summary": "知识库摘要",
    "data": {}
  },
  "options": {
    "max_steps": 8
  }
}
```

### 4.1 顶层字段

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `case_id` | string | 否 | 外部平台 case id，便于串联日志 |
| `repo_id` | string | 否 | 代码仓库 id，默认 `workspace` |
| `user_message` | string | 建议 | 用户当前问题 |
| `message` | string | 否 | `user_message` 的兼容字段 |
| `description` | string | 否 | `user_message` 的兼容字段 |
| `conversation_summary` | string | 否 | 父 Agent 压缩后的历史上下文 |
| `context_summary` | string | 否 | `conversation_summary` 的兼容字段 |
| `attachments` | object | 否 | 日志、补充文本 |
| `known_context` | object | 否 | 父 Agent 已识别出的结构化上下文 |
| `db_evidence` | object | 否 | DB 工具返回的证据 |
| `knowledge_evidence` | object | 否 | SOP、历史 CASE、需求文档等知识库证据 |
| `options` | object | 否 | 分析选项 |

### 4.2 `attachments`

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `log_text` | string | 否 | 错误日志、异常堆栈、日志检索结果 |
| `extra_text` | string | 否 | 额外材料，例如 SQL、DB 摘要、知识库摘要 |

兼容写法：

```json
{
  "log_text": "也可以直接放顶层",
  "extra_text": "也可以直接放顶层"
}
```

### 4.3 `known_context`

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `lot_id` | string | 否 | lotId |
| `fab` | string | 否 | Fab1 / Fab2 / Fab3 |
| `env` | string | 否 | pirun / prod |
| `module` | string | 否 | 模块名 |
| `rule_name` | string | 否 | Rule 名称 |
| `code_system` | string | 否 | MES / EAP / R2R / CIM 等 |
| `code_repo_id` | string | 否 | 父 Agent 选择出的代码仓库 id |

注意：当前 CodeAnalysis 实际选择代码仓库主要看顶层 `repo_id`。`known_context.code_repo_id` 用于记录父 Agent 的选择理由和上下文，不替代顶层 `repo_id`。

### 4.4 `options`

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `max_steps` | number | 8 | LLM 规划搜索/读文件的最大步数 |

## 5. 代码仓库选择

父 Agent 应该在调用前确定 `repo_id`。

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

```http
POST /api/code-analysis/handle
Content-Type: application/json
```

```json
{
  "repo_id": "mes_fab12",
  "user_message": "MES 中 LotHistory 是怎么写入的？",
  "known_context": {
    "code_system": "MES",
    "fab": "Fab1",
    "code_repo_id": "mes_fab12"
  },
  "options": {
    "max_steps": 8
  }
}
```

### 6.2 根据用户提供的错误日志分析代码

```json
{
  "repo_id": "mes_fab12",
  "user_message": "帮我根据这个报错分析代码原因",
  "attachments": {
    "log_text": "2026-07-12 10:01:02 ERROR ... NullReferenceException ..."
  },
  "known_context": {
    "fab": "Fab1",
    "env": "prod",
    "code_system": "MES",
    "code_repo_id": "mes_fab12"
  },
  "options": {
    "max_steps": 8
  }
}
```

### 6.3 已经有 DB 和日志检索结果

```json
{
  "repo_id": "mes_fab12",
  "user_message": "根据 DB 和日志结果分析这次 lot 报错对应的代码原因",
  "conversation_summary": "用户要排查 lot L123456 在 prod 环境的 MES 报错。",
  "attachments": {
    "log_text": "关键错误日志文本",
    "extra_text": "DB 定位到 ruleName=TrackInRule, module=TrackIn, serverIp=10.1.2.3, handledAt=2026-07-12 10:01:02"
  },
  "known_context": {
    "lot_id": "L123456",
    "fab": "Fab1",
    "env": "prod",
    "module": "TrackIn",
    "rule_name": "TrackInRule",
    "code_system": "MES",
    "code_repo_id": "mes_fab12"
  },
  "db_evidence": {
    "summary": "DB 已定位 rule/module/server/time",
    "data": {
      "rule_name": "TrackInRule",
      "module": "TrackIn",
      "server_ip": "10.1.2.3",
      "handled_at": "2026-07-12 10:01:02"
    }
  },
  "options": {
    "max_steps": 8
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
    "created_at": "2026-07-12T10:26:05.123456+00:00",
    "repo_id": "mes_fab12",
    "task_type": "code_question",
    "llm_enabled": true,
    "summary": "代码分析完成，任务类型：code_question，已使用 CodeGraph 获取代码地图上下文。",
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

## 8. 父 Agent 应优先读取的字段

父 Agent 不应该默认消费所有详细字段。

优先读取：

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

这些字段用于排查问题或平台审计，不建议直接给用户展示。

## 9. `data.evidence`

示例：

```json
[
  {
    "type": "codegraph",
    "title": "CodeGraph 查询",
    "repo_id": "mes_fab12",
    "ok": true,
    "query": "用户问题和关键信号",
    "project_path": "D:/MES/SourceCode",
    "output_length": 11154,
    "error": ""
  },
  {
    "type": "file",
    "title": "代码片段",
    "repo_id": "mes_fab12",
    "path": "src/xxx/TrackInRule.cs",
    "start_line": 120,
    "end_line": 220,
    "reason": "LLM requested file read"
  }
]
```

父 Agent 可以用它判断本次回答是否有代码证据支撑。

## 10. `data.diagnosis`

示例：

```json
{
  "confidence": "medium",
  "related_files": [
    "src/xxx/TrackInRule.cs",
    "src/xxx/LotHistoryRepository.cs"
  ],
  "codegraph_used": true,
  "codegraph_ok": true,
  "next_steps": [
    "如果要继续深入，可补充具体报错日志、调用入口或业务规则名。"
  ]
}
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `confidence` | `high` / `medium` / `low` |
| `related_files` | 相关文件列表 |
| `codegraph_used` | 是否尝试调用 CodeGraph |
| `codegraph_ok` | CodeGraph 是否成功返回上下文 |
| `next_steps` | 下一步建议 |

## 11. `data.debug`

示例：

```json
{
  "case_id": "CASE-20260712-182605-2F4B3E",
  "step_count": 3,
  "match_count": 25,
  "snippet_count": 2,
  "error_count": 0
}
```

父 Agent 可以把 `case_id` 放入最终回复或平台日志，方便事后追踪。

## 12. 兼容接口

### 12.1 `/api/code-analysis/analyze`

```http
POST /api/code-analysis/analyze
```

该接口接收已经标准化的内部任务结构，主要用于调试或内部调用。

一般父 Agent 不需要直接使用它。

### 12.2 `/api/oncall`

```http
POST /api/oncall
```

这是当前本地 Web 页面调用父 Agent 的接口，不是给公司平台父 Agent 调 CodeAnalysis 工具的首选接口。

公司平台如果已经有自己的父 Agent，应调用：

```text
/api/code-analysis/handle
```

## 13. CodeGraph 前置条件

目标代码目录必须先执行：

```powershell
codegraph init
```

否则 `data.diagnosis.codegraph_ok` 可能为 `false`，并在 `data.evidence` 或 `data.errors` 中看到相关错误。

每套代码仓库都要单独初始化。

例如：

```powershell
cd D:\CompanyCode\MES-Fab12
codegraph init

cd D:\CompanyCode\EAP-Fab1
codegraph init
```

## 14. 调用建议

1. 涉及代码的问题，父 Agent 应优先调用 CodeAnalysis。
2. 调用前尽量选择正确 `repo_id`。
3. 不要把完整历史对话塞进 `conversation_summary`。
4. 日志可以放 `attachments.log_text`。
5. DB、SOP、历史 CASE 摘要可以放 `attachments.extra_text` 或对应 evidence 字段。
6. 最终给用户展示时，优先使用 `data.answer_markdown`。
7. 如果 `data.debug.error_count > 0`，父 Agent 可以提示“分析过程中存在部分工具异常，结论需谨慎”。

