# CodeGraph 实践流程记录

本文档记录本次在 `codeAgent` 项目中实践 CodeGraph 的完整流程。后续在公司 MES 项目上可以按同样步骤验证。

## 1. 本次目标

我们要验证两件事：

1. CodeGraph 能否给目标代码项目建立代码地图。
2. `codeAgent` 的 Code Analysis Agent 能否在分析代码前，先调用 CodeGraph 获取相关代码上下文。

本次测试时，MES 代码还没有放进来，所以先用 `codeAgent` 自己作为被分析项目。

## 2. CodeGraph 的作用

CodeGraph 的核心作用是提前给代码项目建立本地代码图谱。

可以理解为：

```text
codegraph init    = 给项目建立代码地图
codegraph explore = 查询代码地图
```

执行 `codegraph init` 后，项目目录下会生成：

```text
.codegraph/
  codegraph.db
```

这个 SQLite 数据库里会保存：

- 文件信息
- 类
- 方法
- 函数
- 字段
- 调用关系
- 引用关系
- 搜索索引

后续 `codegraph explore` 会读取这个索引，而不是每次重新全量扫描代码。

## 3. 接入方式选择

CodeGraph 有两种常见接入方式：

### 3.1 MCP 模式

```text
Agent / IDE
  -> MCP Client
    -> codegraph serve --mcp
      -> 查询 .codegraph/codegraph.db
```

这种方式适合 Claude Code、Cursor、Codex CLI 等支持 MCP 的工具。

### 3.2 CLI 模式

```text
codeAgent
  -> subprocess 执行 codegraph explore
    -> 查询 .codegraph/codegraph.db
```

我们当前选择的是 CLI 模式。

原因：

- `codeAgent` 是 Python 项目。
- 当前还没有实现 MCP Client。
- CLI 接入简单，方便先验证效果。
- 后续如果平台支持 MCP，可以再切换到 MCP 模式。

## 4. 安装 CodeGraph

Windows PowerShell 可以执行：

```powershell
irm https://raw.githubusercontent.com/colbymchenry/codegraph/main/install.ps1 | iex
```

如果公司网络不能访问 GitHub，也可以用 npm：

```powershell
npm install -g @colbymchenry/codegraph
```

安装后验证：

```powershell
codegraph version
```

## 5. 给项目建立代码地图

本次我们用 `codeAgent` 自己作为被分析项目。

进入项目目录：

```powershell
cd D:\Professional\myCode\codeAnalysis\codeAgent
```

执行初始化：

```powershell
codegraph init
```

检查状态：

```powershell
codegraph status
```

本次测试结果显示：

```text
Files: 35
Nodes: 353
Edges: 762
Journal: wal
Index is up to date
```

这说明 CodeGraph 已成功给当前项目建立代码地图。

## 6. CLI 验证 CodeGraph

可以先直接用 CLI 验证 CodeGraph 是否能返回相关代码片段。

示例：

```powershell
codegraph explore "app/code_analysis/agent.py 的分析流程"
```

或者：

```powershell
codegraph explore "Code Analysis Agent 是怎么调用 CodeGraph 的？"
```

如果能返回相关源码片段、文件路径、调用关系，就说明 CodeGraph 本身工作正常。

## 7. codeAgent 中的配置

我们新增了配置文件：

```text
configs/codegraph.json
```

当前内容类似：

```json
{
  "enabled": true,
  "cliPath": "codegraph",
  "timeoutSeconds": 60,
  "maxFiles": 8,
  "maxOutputChars": 24000,
  "maxQueryChars": 4000,
  "repositories": {
    "workspace": {
      "projectPath": "."
    }
  }
}
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `enabled` | 是否启用 CodeGraph |
| `cliPath` | CodeGraph CLI 命令路径 |
| `timeoutSeconds` | 单次查询超时时间 |
| `maxFiles` | 最多返回多少个相关文件 |
| `maxOutputChars` | 最大输出长度 |
| `maxQueryChars` | 最大查询文本长度 |
| `repositories.workspace.projectPath` | 当前 repo_id 对应的项目路径 |

当前 `projectPath` 是 `.`，表示分析 `codeAgent` 项目自身。

后续切换到 MES 项目时，可以改成：

```json
"projectPath": "D:/MES/SourceCode"
```

同时需要先在 MES 项目目录执行：

```powershell
codegraph init
```

## 8. 代码接入位置

新增工具类：

```text
app/code_analysis/codegraph_tool.py
```

它的职责是：

- 读取 `configs/codegraph.json`
- 检查 CodeGraph 是否启用
- 检查项目目录是否存在
- 检查 `.codegraph` 索引是否存在
- 执行 `codegraph explore`
- 捕获超时和错误
- 返回 CodeGraph 查询结果

主流程接入位置：

```text
app/code_analysis/agent.py
```

每次分析代码时，会先执行：

```text
CodeGraph explore
```

再继续原有的：

```text
rg/search_code
read_file
LLM 总结
```

也就是说，CodeGraph 是优先使用的代码地图上下文，不是唯一工具。即使 CodeGraph 失败，原来的代码搜索逻辑仍然可以兜底。

服务启动注入位置：

```text
app/main.py
app/code_analysis/server.py
```

## 9. 启动 codeAgent 页面

进入项目目录：

```powershell
cd D:\Professional\myCode\codeAnalysis\codeAgent
```

启动：

```powershell
python -m app.main --host 127.0.0.1 --port 8000
```

访问：

```text
http://127.0.0.1:8000
```

如果端口被占用，可以先查看：

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen
```

## 10. 页面测试问题

可以在页面中输入：

```text
分析 app/code_analysis/agent.py 的分析流程
```

或者：

```text
Code Analysis Agent 是怎么调用 CodeGraph 的？
```

预期结果：

- Agent 会先调用 CodeGraph。
- 返回结果中应该包含 CodeGraph 找到的相关代码上下文。
- LLM 会基于 CodeGraph 上下文和必要的文件读取结果进行总结。

## 11. 如何确认 CodeGraph 起作用

### 11.1 看 case 文件

每次分析会生成 case 文件：

```text
data/cases/CASE-xxxx.json
```

重点看：

```json
"codegraph_results": [
  {
    "ok": true,
    "query": "...",
    "project_path": "...",
    "output": "...",
    "error": ""
  }
]
```

如果 `ok` 是 `true`，说明 CodeGraph 成功返回了上下文。

还可以看：

```json
"steps": [
  {
    "type": "codegraph_explore"
  }
]
```

如果出现 `codegraph_explore`，说明本次分析尝试调用了 CodeGraph。

### 11.2 看业务日志

业务日志位置：

```text
data/business_logs/code_analysis/YYYYMMDD.jsonl
```

用户问题在：

```text
code_analysis.request_received
request.user_message_preview
```

本次我们补充了 CodeGraph 摘要字段。后续 `request_completed` 事件里可以看到：

```text
codegraph_used
codegraph_ok
codegraph_query_preview
codegraph_output_length
codegraph_error
```

字段含义：

| 字段 | 说明 |
| --- | --- |
| `codegraph_used` | 是否尝试调用 CodeGraph |
| `codegraph_ok` | CodeGraph 是否成功返回结果 |
| `codegraph_query_preview` | 传给 CodeGraph 的查询摘要 |
| `codegraph_output_length` | CodeGraph 返回文本长度 |
| `codegraph_error` | CodeGraph 错误信息 |

## 12. LLM 配置

LLM 配置文件：

```text
configs/llm.json
```

本次测试用的是：

```text
base_url = https://ai.mozhiapi.com/v1
model = gpt-5.4-mini
```

启动后可以通过接口确认：

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/repositories
```

如果返回：

```json
"llm_enabled": true,
"model": "gpt-5.4-mini"
```

说明页面服务已经读取到 LLM 配置。

注意：API Key 不建议提交到远端 Git。公司环境中建议用环境变量或本地私有配置管理。

## 13. 后续在 MES 项目上的实践步骤

到公司后可以按下面流程操作：

1. 安装 CodeGraph。
2. 进入 MES 代码目录。
3. 执行 `codegraph init`。
4. 执行 `codegraph status`，确认索引健康。
5. 直接用 `codegraph explore` 测几个典型问题。
6. 修改 `configs/codegraph.json`，把 `projectPath` 指向 MES 项目目录。
7. 启动 `codeAgent`。
8. 在页面输入代码分析问题。
9. 查看 case 文件和业务日志，确认 `codegraph_ok=true`。

示例：

```powershell
cd D:\MES\SourceCode
codegraph init
codegraph status
codegraph explore "LotHistory rule module 调用链"
```

修改：

```json
"projectPath": "D:/MES/SourceCode"
```

再启动：

```powershell
cd D:\Professional\myCode\codeAnalysis\codeAgent
python -m app.main --host 127.0.0.1 --port 8000
```

## 14. 当前结论

本次实践已经验证：

1. CodeGraph 可以给 `codeAgent` 项目建立代码地图。
2. `codegraph explore` 可以返回相关代码片段。
3. `codeAgent` 已通过 CLI 模式接入 CodeGraph。
4. Code Analysis Agent 会在分析前优先调用 CodeGraph。
5. case 文件和业务日志可以追踪 CodeGraph 是否生效。

后续重点是在公司 MES C# 项目上验证 CodeGraph 对真实业务代码的识别效果。

