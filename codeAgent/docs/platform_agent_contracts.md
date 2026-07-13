# 平台父子 Agent 参数契约

本文档定义公司平台父 Agent、代码分析子 Agent、CodeAgent HTTP 服务之间的职责边界和参数结构。

## 1. 总体架构

```text
用户
  -> 平台父 Agent
       -> 平台代码分析子 Agent
            -> HTTP
                 -> CodeAgent /api/code-analysis/handle
                      -> CodeGraph
                      -> 本地代码搜索
                      -> 文件读取
                      -> LLM 分析
```

## 2. 职责边界

### 2.1 平台父 Agent

负责：

- 和用户对话。
- 理解用户总意图。
- 维护全局上下文。
- 提取生产制造相关上下文。
- 判断是否需要代码分析。
- 调用代码分析子 Agent。
- 向用户追问子 Agent 要求补充的信息。
- 汇总代码分析结果并回复用户。

不负责：

- 选择 CodeGraph 查询策略。
- 读取代码文件。
- 直接访问 CodeAgent HTTP 接口。
- 查询 DB 或获取日志。

### 2.2 平台代码分析子 Agent

负责：

- 接收父 Agent 的压缩上下文。
- 判断是否满足调用 CodeAgent 的必要条件。
- 缺少厂别或系统时返回追问。
- 根据厂别和系统选择 `repo_id`。
- 组装 CodeAgent HTTP 请求。
- 调用 CodeAgent HTTP 服务。
- 将 CodeAgent 结果压缩后返回父 Agent。

不负责：

- 和用户直接闲聊。
- 管理完整历史对话。
- 直接分析代码文件。
- 查询 DB、FTP 日志、知识库。

### 2.3 CodeAgent HTTP 服务

负责：

- 接收一次性代码分析请求。
- 调用 CodeGraph。
- 搜索代码。
- 读取文件。
- 使用 LLM 或规则生成代码分析报告。
- 返回结构化结果。

不负责：

- 多轮对话。
- 追问用户。
- 判断生产上下文是否完整。
- 访问生产环境。

## 3. 父 Agent -> 子 Agent 输入

推荐结构：

```json
{
  "current_user_message": "帮我分析 TrackInRule 为什么会报 NullReferenceException",
  "conversation_summary": "用户在排查 Fab1 MES TrackIn 相关问题，前面提到 lotId=L123456，toolId=EQP001。",
  "manufacturing_context": {
    "fab": "Fab1",
    "code_system": "MES",
    "lot_id": "L123456",
    "wafer_id": "",
    "tool_id": "EQP001",
    "module": "TrackIn",
    "rule_name": "TrackInRule",
    "interface_name": "",
    "class_name": "",
    "method_name": "",
    "error_summary": "NullReferenceException",
    "time_range": ""
  },
  "extra_text": "用户粘贴的异常堆栈或补充说明",
  "intent": "code_analysis"
}
```

### 字段说明

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `current_user_message` | 是 | 用户当前这轮原始问题 |
| `conversation_summary` | 否 | 和当前任务强相关的历史摘要 |
| `manufacturing_context` | 否 | 父 Agent 抽取出的制造上下文 |
| `extra_text` | 否 | 异常堆栈、代码片段、接口名等补充上下文 |
| `intent` | 是 | 当前固定为 `code_analysis` |

## 4. 子 Agent 必要参数判断

调用业务代码仓库时，子 Agent 必须确认：

```text
fab
code_system
```

缺少任一字段时，子 Agent 不调用 CodeAgent，而是返回：

```json
{
  "action": "ask_user",
  "missing_fields": ["fab", "code_system"],
  "question": "为了选择正确的代码仓库，请补充厂别和系统：厂别是 Fab1/Fab2/Fab3？系统是 MES 还是 EAP？"
}
```

例外：

如果用户明确说分析当前项目、当前 codeAgent 或当前仓库，可以使用：

```json
{
  "repo_id": "workspace",
  "code_system": "CodeAgent"
}
```

这种情况下不需要 `fab`。

## 5. repo_id 映射

| code_system | fab | repo_id |
| --- | --- | --- |
| MES | Fab1 | `mes_fab12` |
| MES | Fab2 | `mes_fab12` |
| MES | Fab3 | `mes_fab3` |
| EAP | Fab1 | `eap_fab1` |
| EAP | Fab2 | `eap_fab2` |
| EAP | Fab3 | `eap_fab3` |
| CodeAgent / 当前项目 | 任意 | `workspace` |

后续如果要支持 R2R / CIM / FDC / APC，先在 `configs/repositories.json` 增加对应仓库，再扩展映射。

## 6. 子 Agent -> CodeAgent HTTP 请求

接口：

```http
POST /api/code-analysis/handle
Content-Type: application/json
```

请求体：

```json
{
  "case_id": "平台 case id，可选",
  "repo_id": "mes_fab12",
  "user_message": "帮我分析 TrackInRule 为什么会报 NullReferenceException",
  "conversation_summary": "用户在排查 Fab1 MES TrackIn 相关问题。",
  "attachments": {
    "extra_text": "lotId=L123456, toolId=EQP001, module=TrackIn, error=NullReferenceException\n用户粘贴的异常堆栈..."
  },
  "known_context": {
    "fab": "Fab1",
    "module": "TrackIn",
    "rule_name": "TrackInRule",
    "code_system": "MES",
    "code_repo_id": "mes_fab12"
  },
  "options": {
    "max_steps": 8
  }
}
```

## 7. CodeAgent -> 子 Agent 响应

CodeAgent 原始响应：

```json
{
  "ok": true,
  "status": "completed",
  "data": {
    "summary": "代码分析完成...",
    "answer_markdown": "## 结论\n...",
    "evidence": [],
    "diagnosis": {
      "confidence": "medium",
      "related_files": ["xxx.cs"],
      "codegraph_used": true,
      "codegraph_ok": true,
      "next_steps": []
    },
    "debug": {
      "case_id": "CASE-...",
      "step_count": 3,
      "error_count": 0
    }
  }
}
```

子 Agent 返回父 Agent 时建议压缩为：

```json
{
  "action": "code_agent_completed",
  "repo_id": "mes_fab12",
  "summary": "代码分析完成...",
  "answer_markdown": "## 结论\n...",
  "confidence": "medium",
  "related_files": ["xxx.cs"],
  "codegraph_used": true,
  "codegraph_ok": true,
  "case_id": "CASE-..."
}
```

## 8. 子 Agent 返回类型

### 8.1 需要追问

```json
{
  "action": "ask_user",
  "missing_fields": ["fab"],
  "question": "请补充厂别：Fab1、Fab2 还是 Fab3？"
}
```

### 8.2 不调用 CodeAgent

```json
{
  "action": "do_not_call_code_agent",
  "reason": "用户问题不涉及代码",
  "message_to_parent": "这个问题不需要查代码，可以直接回答。"
}
```

### 8.3 调用完成

```json
{
  "action": "code_agent_completed",
  "summary": "...",
  "answer_markdown": "..."
}
```

### 8.4 调用失败

```json
{
  "action": "code_agent_failed",
  "reason": "HTTP 500 或工具异常",
  "message_to_parent": "代码分析工具暂时不可用，请稍后重试或联系维护人员检查配置。"
}
```

## 9. 上下文传递原则

父 Agent 不要把全局 context 原样传给子 Agent。

应该传：

- 用户当前问题。
- 和当前问题强相关的历史摘要。
- 已抽取的制造上下文。
- 少量异常堆栈、接口名、代码片段。

不应该传：

- 完整历史对话。
- 大量重复日志。
- 完整文档。
- 无关工具输出。
- 密钥、账号密码、连接串。

## 10. 推荐落地顺序

1. 在平台中创建父 Agent，复制 `prompts/platform_parent_agent_prompt.md`。
2. 在平台中创建代码分析子 Agent，复制 `prompts/code_analysis_child_agent_prompt.md`。
3. 把 CodeAgent `/api/code-analysis/handle` 注册为子 Agent 可调用的 HTTP 工具。
4. 在 `configs/repositories.json` 配置真实 MES/EAP 代码目录。
5. 分别测试：
   - 当前项目 `workspace`
   - MES Fab1/Fab2
   - MES Fab3
   - EAP Fab1/Fab2/Fab3
