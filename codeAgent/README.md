# CodeAgent

这是一个代码分析 Agent 原型，当前只保留一个核心能力：

> 根据用户的问题，在本机配置好的代码目录中进行 CodeGraph 查询、代码搜索、文件读取和代码分析，并生成 Markdown 分析报告。

当前版本不负责：

- 查询 DB
- 通过 FTP 获取服务器日志
- 检索 SOP、历史 CASE、需求文档知识库

如果用户提供异常堆栈、报错片段、接口名或业务规则名，系统会把这些内容当作代码分析的补充上下文使用。

## 启动

先进入项目目录：

```powershell
cd codeAgent
```

启动本地 Web 服务：

```powershell
python -m app.main --host 127.0.0.1 --port 8000
```

浏览器打开：

```text
http://127.0.0.1:8000
```

## 配置代码仓库

代码仓库配置在：

```text
configs/repositories.json
```

示例：

```json
[
  {
    "id": "workspace",
    "name": "当前项目",
    "root": "D:/Professional/myCode/codeAnalysis/codeAgent",
    "include": ["**/*.py", "**/*.html", "**/*.md", "**/*.json"],
    "exclude": [".git", "__pycache__", "data"]
  }
]
```

如果后续要分析 MES / EAP / 不同 Fab 的代码，可以配置多套仓库：

```json
[
  {
    "id": "mes_fab12",
    "name": "MES Fab1/Fab2",
    "root": "D:/CompanyCode/MES-Fab12",
    "include": ["**/*.cs", "**/*.config", "**/*.xml", "**/*.sql"],
    "exclude": [".git", "bin", "obj", "packages"]
  },
  {
    "id": "eap_fab1",
    "name": "EAP Fab1",
    "root": "D:/CompanyCode/EAP-Fab1",
    "include": ["**/*.cs", "**/*.config", "**/*.xml", "**/*.sql"],
    "exclude": [".git", "bin", "obj", "packages"]
  }
]
```

Agent 只能读取配置过的仓库根目录下的文件。

## 配置大模型

大模型配置在：

```text
configs/llm.json
```

里面可以配置多套模型：

```json
{
  "active_profile": "openai",
  "profiles": {
    "openai": {
      "provider": "openai",
      "base_url": "https://api.openai.com/v1",
      "api_key": "your-key",
      "model": "gpt-4o-mini",
      "supports_json_mode": true
    },
    "qwen": {
      "provider": "qwen",
      "base_url": "https://your-bailian-endpoint/compatible-mode/v1",
      "api_key": "your-key",
      "model": "qwen-plus",
      "supports_json_mode": false
    },
    "deepseek": {
      "provider": "deepseek",
      "base_url": "https://api.deepseek.com/v1",
      "api_key": "your-key",
      "model": "deepseek-chat",
      "supports_json_mode": false
    }
  }
}
```

切换模型时，只改：

```json
"active_profile": "openai"
```

如果不想把 key 写进文件，也可以用环境变量覆盖：

```powershell
$env:LLM_PROFILE="openai"
$env:LLM_API_KEY="your-key"
python -m app.main --host 127.0.0.1 --port 8000
```

优先级：

```text
环境变量 > configs/llm.json > 默认值
```

不同模型参数不一致时，优先改 `configs/llm.json`，不要改 Agent 业务逻辑。

## CodeGraph

目标代码目录建议先执行：

```powershell
codegraph init
```

每套代码仓库都要单独初始化。没有 CodeGraph 时，CodeAgent 会用本地代码搜索兜底，但速度和准确性会下降。

## HTTP 接口

本地页面调用：

```http
POST /api/oncall
```

公司平台父 Agent 推荐把 CodeAnalysis 作为 HTTP 工具调用：

```http
POST /api/code-analysis/handle
```

详细说明见：

```text
docs/code_analysis_http_api.md
docs/local_parent_agent_workflow.md
docs/code_analysis_agent_design.md
```

## 公司平台父子 Agent 提示词

平台父 Agent 和平台代码分析子 Agent 主要靠提示词工作时，直接参考：

```text
prompts/platform_parent_agent_prompt.md
prompts/code_analysis_child_agent_prompt.md
docs/platform_agent_contracts.md
docs/platform_project_structure.md
docs/codeagent_code_only_version_guide.md
```
