# CodeAgentV2 设计说明

## 1. 定位

CodeAgentV2 是 opencode 的企业包装层。

核心思路：

```text
平台父 Agent / 子 Agent
  -> CodeAgentV2 HTTP API
       -> opencode HTTP server
            -> 代码分析
```

CodeAgentV2 不再重复实现代码分析 agent loop。

## 2. 为什么简化入参

opencode 本身已经可以理解自然语言、搜索代码、读取文件、串联流程。

因此 CodeAgentV2 第一版只保留：

```json
{
  "repo_id": "workspace",
  "message": "用户需求",
  "context": "可选上下文",
  "options": {}
}
```

`repo_id` 用于选择正确代码仓库和 opencode server。

`message` 直接传用户需求。

`context` 放父 Agent 压缩后的上下文、报错片段、业务背景。

## 3. 运行流程

```text
POST /api/code-analysis
  -> 校验 message
  -> repo_id 查 configs/repositories.json
  -> 创建 opencode session
  -> 构造 prompt
  -> POST /session/{sessionID}/message
  -> 提取 parts[type=text]
  -> 返回 answer_markdown
```

## 4. 第一版不做什么

- 不自动启动 opencode 进程。
- 不做流式输出。
- 不做异步 job。
- 不直接访问代码目录。
- 不查询 DB / FTP / 知识库。

这些后续按需要扩展。
