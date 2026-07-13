# CodeAgent 代码分析版本使用说明

本文档记录当前这一版 CodeAgent 的功能边界、项目结构、启动方式、VS Code 调试方式和公司平台接入方式。

## 1. 当前版本定位

当前版本只保留一个核心能力：

```text
代码分析
```

CodeAgent 会根据用户问题，在配置好的本地代码仓库中：

- 调用 CodeGraph 查询代码地图。
- 搜索代码。
- 读取相关文件片段。
- 调用 LLM 做多步分析。
- 输出 Markdown 分析报告。
- 记录本地业务日志，方便排查调用过程。

如果用户提供异常堆栈、报错片段、接口名、类名、方法名、Rule 名称等内容，CodeAgent 会把它们作为“代码定位上下文”使用。

## 2. 当前版本不负责什么

当前版本不负责：

- 查询 DB。
- 通过 FTP 获取服务器日志。
- 检索 SOP。
- 检索历史 CASE。
- 检索需求文档知识库。
- 和用户进行多轮追问。
- 维护全局会话记忆。

这些能力如果后续需要，应放在公司平台父 Agent、其他子 Agent 或独立工具中，不放进 CodeAgent 核心服务。

## 3. 当前整体架构

推荐按三层理解：

```text
平台父 Agent
  -> 平台代码分析子 Agent
       -> CodeAgent HTTP 服务
            -> CodeGraph
            -> 本地代码搜索 / 文件读取
            -> LLM 分析
```

### 3.1 平台父 Agent

负责：

- 和用户对话。
- 理解用户意图。
- 维护全局上下文。
- 提取制造上下文，例如 Fab、系统、lotId、waferId、toolId。
- 判断是否需要代码分析。
- 调用平台代码分析子 Agent。

提示词：

```text
prompts/platform_parent_agent_prompt.md
```

### 3.2 平台代码分析子 Agent

负责：

- 判断是否缺少 `fab` 或 `code_system`。
- 缺参数时要求父 Agent 追问用户。
- 根据 Fab 和系统选择 `repo_id`。
- 组装 CodeAgent HTTP 请求。
- 调用 `/api/code-analysis/handle`。

提示词：

```text
prompts/code_analysis_child_agent_prompt.md
```

### 3.3 CodeAgent HTTP 服务

负责：

- CodeGraph 查询。
- 代码搜索。
- 文件读取。
- LLM 代码分析。
- 返回结构化结果和 Markdown 报告。

核心代码：

```text
app/code_analysis/
```

## 4. 主要目录说明

```text
codeAgent/
  app/
    code_analysis/     # CodeAgent 核心代码分析服务
    agents/            # 本地测试用父子 Agent 适配层
    logs/              # 文本信号解析器
    web/               # 本地测试页面

  configs/
    repositories.json  # 可分析代码仓库配置
    codegraph.json     # CodeGraph 配置
    llm.json           # LLM 配置

  prompts/
    platform_parent_agent_prompt.md
    code_analysis_child_agent_prompt.md

  docs/
    platform_agent_contracts.md
    platform_project_structure.md
    codeagent_code_only_version_guide.md
```

## 5. 最小运行目录

如果只启动真正的 CodeAgent HTTP 服务：

```powershell
python -m app.code_analysis.server --host 127.0.0.1 --port 8010
```

最小只需要这些内容：

```text
codeAgent/
  app/
    __init__.py
    code_analysis/
    logs/
  configs/
```

说明：

- `app/code_analysis/`：CodeAgent 核心代码分析服务。
- `app/logs/`：文本信号解析器，用来从用户问题、异常堆栈、补充上下文中提取类名、方法名、异常、关键词等。
- `configs/`：运行配置，包括 `repositories.json`、`codegraph.json`、`llm.json`。
- `app/__init__.py`：Python 包识别文件，建议保留。

只启动 HTTP 服务时，不需要：

```text
app/agents/
app/web/
app/main.py
prompts/
docs/
```

实际部署时建议额外保留：

```text
README.md
docs/code_analysis_http_api.md
docs/codeagent_code_only_version_guide.md
```

方便运维和平台同事查看启动方式、接口格式和排查说明。

## 6. 启动方式一：启动 CodeAgent HTTP 服务

这是公司平台正式接入时推荐的启动方式。

```powershell
cd D:\Professional\myCode\codeAnalysis\codeAgent
python -m app.code_analysis.server --host 127.0.0.1 --port 8010
```

如果给其他机器访问，可以改成：

```powershell
python -m app.code_analysis.server --host 0.0.0.0 --port 8010
```

健康检查：

```text
http://127.0.0.1:8010/health
```

HTTP 工具接口：

```http
POST http://127.0.0.1:8010/api/code-analysis/handle
```

这个方式只启动 CodeAgent HTTP 服务，不启动本地 Web 页面，也不启动本地 Python 父 Agent。

## 7. 启动方式二：启动本地 Web Demo

这是本地自测页面用的启动方式。

```powershell
cd D:\Professional\myCode\codeAnalysis\codeAgent
python -m app.main --host 127.0.0.1 --port 8000
```

浏览器打开：

```text
http://127.0.0.1:8000
```

这个方式会把以下内容聚合在一个 Python 进程里：

```text
本地 Web 页面
  -> 本地 Python 父 Agent
  -> 本地代码分析适配层
  -> CodeAgent 核心代码分析能力
```

它适合本地演示和调试，不是公司平台最终接入的必要方式。

## 8. VS Code 调试方式

已新增 VS Code 启动配置：

```text
.vscode/launch.json
```

打开 VS Code 左侧“运行和调试”，选择：

```text
CodeAgent HTTP Server
```

点击绿色三角，即可 debug：

```powershell
python -m app.code_analysis.server --host 127.0.0.1 --port 8010
```

备用启动项：

```text
CodeAgent Web Demo
```

它用于 debug 本地 Web Demo：

```powershell
python -m app.main --host 127.0.0.1 --port 8000
```

## 9. CodeAgent HTTP 请求示例

接口：

```http
POST /api/code-analysis/handle
Content-Type: application/json
```

请求体：

```json
{
  "repo_id": "workspace",
  "user_message": "帮我分析 app/code_analysis/agent.py 的分析流程",
  "conversation_summary": "用户正在了解 CodeAgent 的代码分析流程。",
  "attachments": {
    "extra_text": "重点关注 CodeGraph、代码搜索、文件读取、LLM 分析这几个步骤。"
  },
  "known_context": {
    "code_system": "CodeAgent",
    "code_repo_id": "workspace"
  },
  "options": {
    "max_steps": 8
  }
}
```

返回中优先看：

```text
data.summary
data.answer_markdown
data.evidence
data.diagnosis
data.debug
```

## 10. 代码仓库配置

代码仓库配置文件：

```text
configs/repositories.json
```

示例：

```json
[
  {
    "id": "workspace",
    "name": "当前 CodeAgent 项目",
    "root": "D:/Professional/myCode/codeAnalysis/codeAgent",
    "include": ["**/*.py", "**/*.html", "**/*.md", "**/*.json"],
    "exclude": [".git", "__pycache__", "data"]
  }
]
```

后续接 MES / EAP 代码时，建议增加：

```text
mes_fab12
mes_fab3
eap_fab1
eap_fab2
eap_fab3
```

## 11. CodeGraph 使用

目标代码目录建议先执行：

```powershell
codegraph init
```

每套代码仓库都要单独执行一次。

CodeAgent 分析时会先调用 CodeGraph 获取代码地图上下文。如果 CodeGraph 不可用，CodeAgent 会记录错误，并继续使用本地代码搜索和读文件兜底。

## 12. LLM 配置

LLM 配置文件：

```text
configs/llm.json
```

支持多 profile，例如 OpenAI、千问、DeepSeek 或公司代理网关。

注意：

- `configs/llm.json` 可能包含 API Key。
- 提交代码前要确认不要把真实 key 提交到远端。
- 生产环境更建议用环境变量覆盖 key。

常用环境变量：

```powershell
$env:LLM_PROFILE="openai"
$env:LLM_API_KEY="your-key"
```

## 13. 平台接入步骤

1. 启动 CodeAgent HTTP 服务。

```powershell
python -m app.code_analysis.server --host 0.0.0.0 --port 8010
```

2. 在公司平台创建父 Agent，复制：

```text
prompts/platform_parent_agent_prompt.md
```

3. 在公司平台创建代码分析子 Agent，复制：

```text
prompts/code_analysis_child_agent_prompt.md
```

4. 给代码分析子 Agent 配置 HTTP 工具：

```http
POST http://服务器IP:8010/api/code-analysis/handle
```

5. 按下面链路测试：

```text
用户问题
  -> 平台父 Agent
  -> 平台代码分析子 Agent
  -> CodeAgent HTTP 服务
  -> 返回代码分析结果
```

## 14. 这版变更总结

本版主要完成：

- 删除 DB 查询相关 Agent 和配置。
- 删除 FTP 日志获取相关 Agent 和配置。
- 删除 Investigation 旧链路。
- 保留 CodeAgent 代码分析主能力。
- 保留 CodeGraph 集成。
- 新增平台父 Agent 提示词。
- 新增平台代码分析子 Agent 提示词。
- 新增平台父子 Agent 参数契约文档。
- 新增 VS Code debug 启动配置。
- 更新 Web 页面为代码分析场景。

## 15. 当前推荐使用方式

本地调试 CodeAgent：

```text
VS Code -> Run and Debug -> CodeAgent HTTP Server
```

本地页面演示：

```text
VS Code -> Run and Debug -> CodeAgent Web Demo
```

公司平台接入：

```text
启动 app.code_analysis.server
平台代码分析子 Agent 调用 /api/code-analysis/handle
```
