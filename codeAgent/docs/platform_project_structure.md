# 平台父子 Agent 项目结构设计

## 1. 设计目标

当前目标不是把所有能力都塞进 CodeAgent，而是形成清晰的三层结构：

```text
平台父 Agent
  -> 平台代码分析子 Agent
       -> CodeAgent HTTP 服务
```

这样做的原因：

- 公司平台可以做多 Agent 调度，但主要依赖提示词。
- CodeAgent 只能作为 HTTP 工具被平台调用。
- CodeAgent 应保持单一职责，只做代码分析。
- 多轮对话、追问、上下文记忆应留在平台父子 Agent 中。

## 2. 推荐目录

```text
codeAgent/
  app/
    agents/
      parent_agent.py
      code_analysis_agent.py
      input_parse_agent.py
      intent_agent.py
      report_agent.py
      code_analysis_tool_prompt_agent.py

    code_analysis/
      agent.py
      server.py
      codegraph_tool.py
      tools.py
      llm.py
      business_logger.py

    logs/
      parser.py

    web/
      index.html

  configs/
    repositories.json
    codegraph.json
    llm.json

  prompts/
    platform_parent_agent_prompt.md
    code_analysis_child_agent_prompt.md

  docs/
    platform_agent_contracts.md
    platform_project_structure.md

  README.md
```

## 3. 哪些是本地测试用

以下代码主要用于本地测试父子 Agent 流程：

```text
app/agents/parent_agent.py
app/agents/intent_agent.py
app/agents/input_parse_agent.py
app/agents/report_agent.py
app/web/index.html
app/main.py
```

公司平台上线后，这些 Python 父 Agent 不一定会被使用，因为平台父 Agent 和子 Agent 由平台托管。

## 4. 哪些是核心服务

以下代码是 CodeAgent HTTP 服务核心：

```text
app/code_analysis/agent.py
app/code_analysis/server.py
app/code_analysis/codegraph_tool.py
app/code_analysis/tools.py
app/code_analysis/llm.py
app/code_analysis/business_logger.py
configs/repositories.json
configs/codegraph.json
configs/llm.json
```

公司平台真正需要调用的是：

```http
POST /api/code-analysis/handle
```

## 5. 哪些是给平台复制的提示词

```text
prompts/platform_parent_agent_prompt.md
prompts/code_analysis_child_agent_prompt.md
```

平台父 Agent 使用：

```text
platform_parent_agent_prompt.md
```

平台代码分析子 Agent 使用：

```text
code_analysis_child_agent_prompt.md
```

## 6. 当前保留的本地父 Agent

虽然公司平台会托管父 Agent 和子 Agent，但本地仍保留 Python 版父 Agent。

用途：

- 本地自测。
- 验证 CodeAgent HTTP 入参。
- 在没有公司平台时模拟父子 Agent 调用。
- 做 demo 页面。

注意：

本地 Python 父 Agent 不代表最终平台实现。最终平台实现主要靠提示词和 HTTP 工具配置。

## 7. CodeAgent 的能力边界

CodeAgent 负责：

- CodeGraph 查询。
- 代码搜索。
- 文件读取。
- LLM 代码分析。
- 返回 Markdown 报告。

CodeAgent 不负责：

- 厂别和系统的多轮追问。
- 全局会话记忆。
- DB 查询。
- FTP 获取日志。
- SOP / CASE / 需求文档检索。

## 8. 后续扩展建议

### 8.1 CodeRepoRouter 配置化

后续可以新增：

```text
configs/repo_router.json
```

用于维护：

```json
{
  "MES": {
    "Fab1": "mes_fab12",
    "Fab2": "mes_fab12",
    "Fab3": "mes_fab3"
  },
  "EAP": {
    "Fab1": "eap_fab1",
    "Fab2": "eap_fab2",
    "Fab3": "eap_fab3"
  }
}
```

短期可以先写在平台子 Agent 提示词里。

### 8.2 流式输出

当前 CodeAgent 是一次请求、一次返回。

后续如果分析慢，可以新增：

```http
POST /api/code-analysis/stream
```

先流式返回步骤状态，再考虑 LLM token 级流式输出。

### 8.3 C# 代码增强

MES/EAP 是 C# 代码时，后续可以增强：

- namespace 解析。
- class / method 提取。
- Controller / Service / Repository 识别。
- `.csproj` 依赖关系。
- 异常堆栈到文件路径的映射。

## 9. 当前建议结论

短期按提示词驱动实现平台父子 Agent。

不要让 CodeAgent 承担追问和对话职责。CodeAgent 应保持为稳定的 HTTP 代码分析工具，这样平台侧 Agent 怎么变化，都不会影响底层代码分析能力。
