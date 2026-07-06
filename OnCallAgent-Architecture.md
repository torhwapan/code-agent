# OnCallAgent 总体架构设计

## 1. 背景

OnCallAgent 面向半导体 OP 和 CIM 工程团队，目标是在接收到 MES、R2R、EAP、APC、CIM 等系统报案时，协助定位问题、整理证据、分析代码和日志，并给出可追溯的诊断建议。

它不应该只是一个聊天机器人，而应该是一个：

> 面向半导体生产系统的、安全可控、证据驱动的值班诊断助手。

长期目标是让 Agent 能够结合：

- 报案单。
- 错误日志。
- 实时只读 DB 数据。
- 代码仓库。
- 需求文档。
- 历史 CASE。
- OP 经验 SOP。
- 最近发布和变更记录。

最终输出可解释、可复盘、可追踪来源的诊断结论。

## 2. 总体能力

OnCallAgent 长期应具备以下能力：

- 解析 MES、R2R、CIM、EAP、APC 等系统报案。
- 抽取 lot、equipment、recipe、route step、product、alarm code、transaction time 等制造领域实体。
- 查询日志、代码、需求、SOP、历史 CASE 和只读生产数据。
- 关联多个系统的证据。
- 生成带证据来源和置信度的诊断报告。
- 推荐下一步操作或升级方向。
- 对高风险动作进行人工确认。
- 自动记录处理过程，便于审计和复盘。
- 将关闭后的 CASE 反哺知识库。

## 3. 总体架构

```text
                 OP / Engineer
                      |
              Web Console / ChatOps
                      |
                OnCallAgent API
                      |
          Incident Orchestrator / Workflow
                      |
   ------------------------------------------------
   |        |          |          |        |       |
 Intake   RAG      Code       Log       DB     SOP
 Agent    Agent    Agent      Agent     Agent  Agent
   |        |          |          |        |       |
   ------------------------------------------------
                      |
              Evidence Graph / Case State
                      |
   ------------------------------------------------
   |              Tool Gateway / Policy             |
   ------------------------------------------------
     |          |          |          |          |
   MES DB    Logs      Git Repo    Docs KB   Ticket/CASE
```

推荐把系统拆成四根主梁：

```text
Incident Workflow + Tool Gateway + Evidence Graph + Hybrid RAG
```

这四个骨架分别解决：

| 骨架 | 解决的问题 |
| --- | --- |
| Incident Workflow | 一个报案如何从进入、分析、确认到关闭 |
| Tool Gateway | Agent 如何安全访问外部系统 |
| Evidence Graph | 证据和实体关系如何沉淀、复用 |
| Hybrid RAG | 文档、历史 CASE、SOP 如何准确检索 |

## 4. 骨架一：Incident Workflow

Incident Workflow 管理一个 CASE 从进入到关闭的完整生命周期。

生产现场的报案不是一次普通问答。一个 CASE 可能持续几分钟、几十分钟，甚至跨班次。因此流程层需要支持：

- 状态保存。
- 失败重试。
- 人工确认。
- 服务重启后恢复。
- Timeline 记录。
- 审计和复盘。

典型流程：

```text
接收报案
 -> 解析关键信息
 -> 判断系统和模块
 -> 收集日志
 -> 查询只读 DB 数据
 -> 检索 SOP 和历史 CASE
 -> 分析代码或最近变更
 -> 构建证据链
 -> 生成诊断结论
 -> 等待人工确认
 -> 记录处理结果
 -> 关闭 CASE
```

Incident Workflow 要回答：

- 这个报案现在处于哪个阶段？
- 哪些信息已经检查过？
- 哪些证据已经收集？
- 下一步应该做什么？
- 谁确认过什么动作？
- 这个 CASE 能不能恢复和重放？

长期推荐技术：

- Temporal：长流程、重试、超时、恢复。
- LangGraph：Agent 状态图、多轮推理、人机中断。
- PostgreSQL：CASE 状态、Timeline、审计记录。

第一版可以先不用 Temporal 和 LangGraph，用普通 Python pipeline + JSON/DB 记录状态即可。

## 5. 骨架二：Tool Gateway

Tool Gateway 是 Agent 和外部系统之间的安全访问层。

LLM 不应该直接访问生产 DB、日志平台、Git、工单系统或服务器文件。正确方式是：

```text
LLM 提出意图
  |
  v
Tool Gateway 校验权限、参数、范围、风险
  |
  v
受控工具执行
  |
  v
返回结构化结果给 Agent
```

例如 Agent 想查：

```text
查询 lot L123456 在 10:00 到 10:30 的 transaction history
```

Tool Gateway 需要检查：

- 用户有没有权限？
- Agent 有没有权限？
- 数据源是否允许访问？
- SQL 是否只读？
- 表是否在白名单？
- 时间窗口是否合理？
- 返回行数是否超限？
- 是否需要字段脱敏？
- 是否需要人工审批？

Tool Gateway 应暴露受控工具，例如：

```text
query_lot_state(lot_id, time_window)
query_lot_transaction_history(lot_id, time_window)
query_equipment_status(eqp_id)
search_logs(system, keywords, time_window)
get_recent_commits(module, since)
search_sop(system, alarm_code)
search_historical_cases(system, module, alarm_code)
search_code(query)
read_file(path, start_line, end_line)
```

它不应该暴露任意 shell、任意 SQL 或任意文件读取。

核心职责：

- 权限控制。
- 参数校验。
- 策略控制。
- SQL 校验。
- 超时和限流。
- 数据脱敏。
- 操作审计。
- 人工审批。
- 工具结果标准化。

## 6. 骨架三：Evidence Graph

Evidence Graph 用来保存诊断背后的证据链。

Agent 不应该只说：

```text
可能是 retry job 失败。
```

它应该说明：

- 报案单显示 lot move 失败。
- 日志显示 transaction timeout。
- DB 显示 WIP state 和 transaction state 不一致。
- 历史 CASE 有相同 alarm pattern。
- 最近某个 commit 修改了 timeout 逻辑。
- SOP 建议先检查 interface retry queue。

Evidence Graph 把这些实体和证据连起来：

```text
Incident
 -> affects -> Lot
 -> observed_on -> Equipment
 -> has_alarm -> AlarmCode
 -> supported_by -> LogEvent
 -> supported_by -> DBQueryResult
 -> related_to -> CodeFile
 -> changed_by -> Commit
 -> matched_with -> HistoricalCase
 -> follows -> SOP
 -> candidate_root_cause -> RootCause
```

它要回答：

- Agent 为什么得出这个判断？
- 哪些证据支持结论？
- 哪些证据互相冲突？
- 历史上是否发生过类似问题？
- 哪个设备、模块、recipe 经常出类似 CASE？
- 哪些 SOP 真正在现场有效？
- 当前 CASE 是否能沉淀成可复用知识？

初期可以用 PostgreSQL 表实现：

```text
incidents
incident_entities
evidence_items
incident_evidence_links
entity_relations
diagnosis_candidates
recommended_actions
case_timeline
```

后续关系复杂后，再考虑 Neo4j 或其他图数据库。

## 7. 骨架四：Hybrid RAG

Hybrid RAG 用来从需求文档、设计文档、SOP、历史 CASE、OP 经验文档、Release Note、DB Schema、代码文档中检索相关知识。

半导体 CIM 场景不能只靠向量检索。

有些内容需要语义相似：

```text
lot cannot move
wafer cannot track out
move transaction failed
lot stuck at current step
```

有些内容必须精确匹配：

```text
MES-LOT-STATE-409
LotTrack
TrackOut
WIP_LOT_STATE
ORA-00060
recipe_id
eqp_id
```

因此推荐轻量 Hybrid RAG：

```text
实体抽取
 -> metadata filter
 -> keyword search
 -> vector search
 -> 合并结果
 -> rerank
 -> 权限过滤
 -> 返回带来源片段
```

第一版可以先做：

- Metadata 设计。
- 关键词检索。
- 向量检索。
- 来源引用。

后续再加 reranker、权限过滤和图谱关联。

## 8. 模块设计

### 8.1 Incident Intake

职责：

- 接收报案单、Webhook、邮件或 ChatOps 消息。
- 标准化成统一 Incident Schema。
- 抽取 system、module、lot、equipment、recipe、alarm code、fab、timestamp。
- 创建 CASE。

### 8.2 Context Builder

职责：

- 根据报案生成调查计划。
- 决定要查哪些日志、DB、代码、SOP、历史 CASE。
- 维护 CASE 状态。
- 将证据写入 Evidence Graph。

### 8.3 Knowledge RAG

职责：

- 导入需求、SOP、历史 CASE、设计文档、OP 经验。
- 抽取 metadata。
- 建立关键词索引和向量索引。
- 返回带来源的上下文。

### 8.4 Code Analysis Agent

职责：

- 根据日志中的错误码、类名、方法名、表名、SQL、关键字搜索代码。
- 读取相关文件。
- 多轮分析调用链、配置、异常处理、SQL、Mapper。
- 输出代码层面的可疑点和证据。

第一版已经先实现这个模块。

### 8.5 Log Analysis

职责：

- 根据系统、关键词、lot、equipment、alarm code、trace id、时间窗口检索日志。
- 聚合异常模式。
- 和历史 CASE 做 pattern matching。
- 把结构化日志事件作为证据。

第一版暂时采用 OP 手动粘贴或上传日志。

### 8.6 DB Analyst

职责：

- 安全查询只读生产数据。
- 用预定义模板处理常见诊断场景。
- 校验 SQL。
- 限流、限行、脱敏、审计。

强约束：

- 只读账号。
- 默认禁止 `INSERT/UPDATE/DELETE/MERGE/DDL`。
- 表白名单。
- 查询超时。
- 返回行数限制。
- 全量审计。

### 8.7 SOP Executor

职责：

- 根据证据匹配 SOP。
- 推荐下一步动作。
- 按风险等级分类。
- 高风险动作必须人工确认。

动作等级：

```text
L0：只读分析，无需审批
L1：只给建议，由 OP 手动执行
L2：低风险只读或通知动作，需要审计
L3：可能影响生产，必须人工审批
L4：禁止 Agent 执行，只能升级给工程师
```

## 9. 多模型适配架构

你们公司有千问、DeepSeek、OpenAI 等模型时，最重要的是不要让业务代码依赖某个模型厂商。

推荐抽象：

```text
业务模块
  |
  v
LLMClient / LLMGateway
  |
  |-- OpenAI Adapter
  |-- DeepSeek Adapter
  |-- Qwen Adapter
  |-- Internal Model Adapter
```

业务代码只认统一接口：

```python
llm.chat(messages, json_mode=True)
```

不要在 Agent 里写：

```text
if model == qwen:
    ...
elif model == deepseek:
    ...
```

这些差异应该放进适配层。

### 9.1 需要屏蔽的差异

| 差异 | 适配方式 |
| --- | --- |
| base url | 配置化 |
| model name | 配置化 |
| API key | 配置化 |
| JSON mode 能力 | 配置化，不支持时靠 prompt + 解析兜底 |
| temperature/top_p | 配置化，不支持时关闭 |
| max token 参数名 | 配置化，例如 `max_tokens` 或 `max_completion_tokens` |
| 私有扩展参数 | 通过 JSON 配置追加 |
| 上下文长度 | 适配层维护 token budget |
| 错误格式 | 适配层统一异常 |
| 流式输出 | 适配层统一 stream 接口 |
| function calling | 第一版不用厂商专属 function calling，统一 JSON 动作协议 |
| 输出稳定性 | 统一 prompt、统一 schema、失败重试 |

### 9.2 推荐公司内部做法

最好由公司内部模型平台提供一个 OpenAI-compatible 网关：

```text
/v1/chat/completions
/v1/embeddings
```

然后 Agent 只配置：

```text
LLM_PROVIDER
LLM_BASE_URL
LLM_API_KEY
LLM_MODEL
LLM_SUPPORTS_JSON_MODE
```

这样千问、DeepSeek、OpenAI 的切换不会影响业务代码。

## 10. 推荐技术选型

| 层级 | 推荐 |
| --- | --- |
| 后端 API | Python FastAPI 或 Java Spring Boot |
| 第一版 Web | Python 标准库 HTTP Server |
| Agent 编排 | 第一版普通 Python loop，复杂后上 LangGraph |
| 长流程 | 后续用 Temporal |
| 主数据库 | PostgreSQL |
| 向量检索 | pgvector，规模大后 Milvus/Qdrant |
| 关键词检索 | PostgreSQL full-text 或 OpenSearch |
| 日志平台 | OpenSearch / Elasticsearch / Splunk / Loki |
| 代码搜索 | ripgrep，后续 Sourcegraph |
| 代码结构分析 | tree-sitter / Semgrep |
| 权限策略 | OPA / Casbin |
| SQL 校验 | sqlglot |
| 前端 | React + Ant Design / Semi Design |
| 部署 | Kubernetes + Helm |
| 可观测性 | Prometheus + Grafana + OpenTelemetry |
| Secret | Vault / KMS |

## 11. 建设路线

### Phase 1：代码分析 MVP

- OP 上传日志。
- 日志解析。
- 本机代码搜索。
- 多轮 Code Analysis Agent。
- 生成代码分析报告。
- 多模型适配层。

### Phase 2：需求知识库

- 导入需求文档、SOP、历史 CASE。
- 建轻量 Hybrid RAG。
- 报告中补充需求依据。

### Phase 3：日志平台接入

- 接 ELK/OpenSearch/Splunk/Loki。
- 支持按时间窗口自动拉日志。
- 将日志事件结构化为证据。

### Phase 4：只读 DB 查询

- 接 MES/R2R/CIM 只读库。
- SQL 白名单和模板化。
- 查询审计、脱敏、限流。

### Phase 5：完整 Incident Workflow

- 引入 Workflow。
- 加入人工确认。
- CASE 生命周期管理。
- Timeline 和复盘。

### Phase 6：Evidence Graph

- 沉淀实体和证据关系。
- 支持跨系统根因分析。
- 让历史 CASE 反哺诊断。

## 12. 总结

OnCallAgent 的长期架构建议围绕四根主梁：

```text
Incident Workflow + Tool Gateway + Evidence Graph + Hybrid RAG
```

第一版先做最有价值、最容易落地的一段：

```text
错误日志
 -> 日志解析
 -> 本机代码搜索
 -> 多轮 LLM 代码分析
 -> 代码分析报告
```

同时从一开始就做好两件事：

- 工具访问必须受控，不能让 LLM 随意读文件或执行命令。
- 大模型必须通过统一适配层接入，避免被 OpenAI、DeepSeek、千问任意一家绑定。
