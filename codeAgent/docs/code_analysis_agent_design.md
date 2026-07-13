# CodeAnalysisAgent 设计说明

## 1. 当前目标

当前 CodeAgent 已做减法，只保留一个核心能力：分析代码。

CodeAnalysisAgent 负责：

- 根据用户问题分析代码
- 根据类名、方法名、接口名、模块名定位代码
- 分析调用链、业务流程和实现逻辑
- 分析代码改动影响范围
- 在用户提供异常堆栈或报错片段时，把它作为补充上下文辅助定位相关代码
- 调用 CodeGraph 查询代码地图
- 必要时读取文件片段
- 输出 Markdown 分析结果和结构化证据

CodeAnalysisAgent 不负责：

- 查询 DB
- 获取服务器日志
- 检索 SOP、历史 CASE、需求文档
- 和用户进行多轮业务澄清

## 2. 父子 Agent 职责

```text
平台父 Agent
  -> 和用户对话
  -> 压缩必要上下文
  -> 调用平台代码分析子 Agent
  -> 整理最终回复

平台代码分析子 Agent
  -> 提取 fab / code_system
  -> 必要时要求父 Agent 追问用户
  -> 选择 repo_id
  -> 组装 CodeAgent HTTP 请求

CodeAnalysisAgent
  -> 归一化代码分析请求
  -> 提取代码搜索信号
  -> 调用 CodeGraph
  -> 搜索和读取代码文件
  -> 使用 LLM 或规则生成代码分析报告
```

## 3. 当前进程架构

当前支持两种运行方式。

### 3.1 本地直连模式

父 Agent 和 CodeAnalysisAgent 在同一个进程里。

```text
用户
  -> /api/oncall
  -> OnCallParentAgent
  -> CodeAnalysisChildAgent
  -> CodeAnalysisAgent.handle_input()
```

这是本地 Web 页面默认模式。

### 3.2 独立 HTTP 子进程模式

CodeAnalysisAgent 可以单独作为 HTTP 服务启动。

```text
公司平台父 Agent
  -> 平台代码分析子 Agent
  -> HTTP Tool
  -> /api/code-analysis/handle
  -> CodeAnalysisAgent
```

启动子 Agent：

```powershell
cd D:\Professional\myCode\codeAnalysis\codeAgent
python -m app.code_analysis.server --host 127.0.0.1 --port 8010
```

健康检查：

```http
GET /health
```

推荐调用接口：

```http
POST /api/code-analysis/handle
```

## 4. 平台代码分析子 Agent 推荐请求

```json
{
  "case_id": "CASE-001",
  "repo_id": "workspace",
  "user_message": "帮我分析 CodeAnalysisAgent 的分析流程",
  "conversation_summary": "可选，压缩后的必要对话上下文",
  "attachments": {
    "extra_text": "可选，异常堆栈、代码片段、接口名、业务规则名等补充上下文"
  },
  "known_context": {
    "fab": "Fab1",
    "module": "MES",
    "rule_name": "SomeRule",
    "code_system": "MES",
    "code_repo_id": "workspace"
  },
  "options": {
    "max_steps": 8
  }
}
```

说明：

- `repo_id` 决定分析哪套代码。
- `user_message` 是用户当前问题。
- `conversation_summary` 只放压缩后的必要上下文，不放完整历史对话。
- `attachments.extra_text` 只放和代码定位强相关的补充材料。
- `known_context` 用来传平台已识别出的系统、Fab、模块、ruleName 等信息。

## 5. 内部标准任务

`CodeAnalysisAgent.handle_input(request)` 会先调用：

```python
CodeAnalysisAgent.normalize_request(request)
```

生成内部 task：

```json
{
  "task_type": "flow_analysis",
  "repo_id": "workspace",
  "user_goal": "帮我分析 CodeAnalysisAgent 的分析流程",
  "code_signals": {
    "keywords": ["CodeAnalysisAgent"],
    "classes": [],
    "methods": [],
    "error_codes": [],
    "exceptions": [],
    "tables": [],
    "module": null,
    "rule_name": null,
    "known_context": {}
  },
  "evidence": {
    "extra_text": ""
  },
  "context_summary": "可选上下文摘要",
  "max_steps": 8
}
```

然后调用：

```python
CodeAnalysisAgent.analyze_task(task)
```

## 6. 任务类型

当前只区分代码分析内部任务类型：

| task_type | 说明 |
| --- | --- |
| `code_question` | 通用代码问题 |
| `flow_analysis` | 流程 / 调用链分析 |
| `impact_analysis` | 影响范围分析 |
| `bug_hunt` | bug / 异常排查 |

即使用户提供异常堆栈，也只是 `bug_hunt` 的补充上下文，不表示 CodeAgent 会去获取日志。

## 7. 分析流程

```text
handle_input()
  -> normalize_request()
  -> analyze_task()
  -> analyze()
  -> 解析代码信号
  -> CodeGraph explore
  -> LLM 规划搜索/读文件动作
  -> LocalCodeTools.search_code()
  -> LocalCodeTools.read_file()
  -> 生成 Markdown 报告
  -> 保存 case 记录和业务日志
```

如果没有配置 LLM，会走规则兜底：

```text
解析关键词
  -> 搜索代码
  -> 读取靠前命中文件
  -> 生成规则版报告
```

## 8. CodeGraph 的作用

CodeGraph 用来在正式搜索代码前先拿到代码地图上下文。

当前接入方式是 CLI：

```text
CodeAnalysisAgent
  -> CodeGraphTool
  -> codegraph explore "用户问题 + 关键词"
```

CodeGraph 不是后台常驻进程。它是一个命令行工具，每次分析时由 CodeAgent 调用命令获取结果。

目标代码目录建议先执行：

```powershell
codegraph init
```

每套代码仓库都要单独初始化。

## 9. 返回给父 Agent 的关键字段

```json
{
  "summary": "一句话摘要",
  "answer_markdown": "可直接给用户看的 Markdown 答案",
  "evidence": [],
  "diagnosis": {
    "confidence": "medium",
    "related_files": [],
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
```

父 Agent 给用户回复时，优先使用：

```text
answer_markdown
```

`debug`、`steps`、`matches`、`snippets` 主要用于排查问题，不建议直接展示给用户。

## 10. 本地 Web 页面

本地页面调用：

```http
POST /api/oncall
```

页面只提供：

- 代码仓库选择
- 用户问题输入
- 可选补充上下文输入

不会再提供 DB 查询、日志检索或知识库检索流程。

## 11. 后续建议

1. 增加 CodeRepoRouter，根据 MES/EAP/Fab 选择 `repo_id`。
2. 扩展 `configs/repositories.json`，配置公司多套代码库。
3. 把 `app/logs/parser.py` 改名为 `context_parser.py`，避免命名上继续像日志系统。
4. 给 `/api/code-analysis/handle` 增加流式输出。
5. 针对 C# 项目增强类名、方法名、命名空间、异常堆栈解析。
