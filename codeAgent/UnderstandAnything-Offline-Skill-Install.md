# Understand Anything 离线手动安装教程

本文档记录在公司网络无法直接执行在线安装脚本时，如何通过“已下载源码 + 手动复制 skills”的方式，在 Codex 环境中使用 Understand Anything。

## 1. 背景

官方在线安装方式是：

```powershell
iwr -useb https://raw.githubusercontent.com/Egonex-AI/Understand-Anything/main/install.ps1 | iex
```

如果公司网络无法访问 GitHub raw 地址，或者不允许直接执行网上脚本，可以改用离线手动安装。

核心思路：

```text
1. 提前下载 Understand-Anything 源码
2. 把源码拷贝到公司机器
3. 把源码里的 skills 复制到 Codex 的 skills 目录
4. 准备 Node.js / pnpm / 依赖
5. 重启 Codex
6. 在 Codex 对话中使用 $understand
```

注意：`$understand` 不是 PowerShell 命令，而是 Codex 对话里的 skill 调用方式。

## 2. 目录说明

假设源码放在：

```text
D:\Professional\myCode\codeAnalysis\Understand-Anything
```

核心插件目录是：

```text
D:\Professional\myCode\codeAnalysis\Understand-Anything\understand-anything-plugin
```

skills 目录是：

```text
D:\Professional\myCode\codeAnalysis\Understand-Anything\understand-anything-plugin\skills
```

里面包含：

```text
understand
understand-dashboard
understand-chat
understand-diff
understand-domain
understand-explain
understand-figma
understand-knowledge
understand-onboard
```

Codex 的本地 skills 目录一般是：

```text
C:\Users\Administrator\.codex\skills
```

如果不是 Administrator 用户，请替换成自己的用户目录：

```text
C:\Users\<你的用户名>\.codex\skills
```

## 3. 准备源码

如果公司电脑不能访问 GitHub，可以在外部网络机器上提前下载：

```powershell
git clone https://github.com/Egonex-AI/Understand-Anything.git
```

然后把整个目录打包，拷贝到公司机器。

建议保留完整目录，不要只拷贝 `skills`，因为运行时还需要插件里的：

```text
packages/core
packages/dashboard
agents
scripts
```

## 4. 手动复制 skills

### 4.1 创建 Codex skills 目录

```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.codex\skills"
```

### 4.2 复制 skills

假设源码在：

```text
D:\Professional\myCode\codeAnalysis\Understand-Anything
```

执行：

```powershell
$src = "D:\Professional\myCode\codeAnalysis\Understand-Anything\understand-anything-plugin\skills"
$dst = "$env:USERPROFILE\.codex\skills"

Copy-Item "$src\understand" -Destination "$dst\understand" -Recurse -Force
Copy-Item "$src\understand-dashboard" -Destination "$dst\understand-dashboard" -Recurse -Force
Copy-Item "$src\understand-chat" -Destination "$dst\understand-chat" -Recurse -Force
Copy-Item "$src\understand-diff" -Destination "$dst\understand-diff" -Recurse -Force
Copy-Item "$src\understand-domain" -Destination "$dst\understand-domain" -Recurse -Force
Copy-Item "$src\understand-explain" -Destination "$dst\understand-explain" -Recurse -Force
Copy-Item "$src\understand-knowledge" -Destination "$dst\understand-knowledge" -Recurse -Force
Copy-Item "$src\understand-onboard" -Destination "$dst\understand-onboard" -Recurse -Force
```

如果你也要试 Figma 相关能力，再复制：

```powershell
Copy-Item "$src\understand-figma" -Destination "$dst\understand-figma" -Recurse -Force
```

### 4.3 验证复制结果

检查：

```powershell
Get-ChildItem "$env:USERPROFILE\.codex\skills" | Where-Object { $_.Name -like "understand*" }
```

应该能看到：

```text
understand
understand-dashboard
understand-chat
understand-diff
understand-domain
understand-explain
understand-knowledge
understand-onboard
```

每个目录下都应该有：

```text
SKILL.md
```

例如：

```powershell
Test-Path "$env:USERPROFILE\.codex\skills\understand\SKILL.md"
```

返回：

```text
True
```

## 5. 配置插件根目录

Understand Anything 的 skill 在运行时需要找到完整插件目录。

源码里的 `SKILL.md` 会尝试自动寻找这些路径：

```text
$env:CLAUDE_PLUGIN_ROOT
$HOME\.understand-anything-plugin
$HOME\.codex\understand-anything\understand-anything-plugin
```

为了稳妥，建议创建一个固定目录：

```text
C:\Users\<用户名>\.codex\understand-anything\understand-anything-plugin
```

### 5.1 创建目录

```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.codex\understand-anything"
```

### 5.2 复制插件目录

```powershell
$pluginSrc = "D:\Professional\myCode\codeAnalysis\Understand-Anything\understand-anything-plugin"
$pluginDst = "$env:USERPROFILE\.codex\understand-anything\understand-anything-plugin"

Copy-Item $pluginSrc -Destination $pluginDst -Recurse -Force
```

最终应该存在：

```text
C:\Users\<用户名>\.codex\understand-anything\understand-anything-plugin\package.json
C:\Users\<用户名>\.codex\understand-anything\understand-anything-plugin\packages\core
C:\Users\<用户名>\.codex\understand-anything\understand-anything-plugin\packages\dashboard
```

验证：

```powershell
Test-Path "$env:USERPROFILE\.codex\understand-anything\understand-anything-plugin\package.json"
Test-Path "$env:USERPROFILE\.codex\understand-anything\understand-anything-plugin\packages\core"
```

都应该返回：

```text
True
```

## 6. 准备 Node.js 和 pnpm

Understand Anything 是 Node.js / TypeScript 项目。

建议准备：

```text
Node.js >= 22
pnpm >= 10
```

检查：

```powershell
node -v
pnpm -v
```

如果没有 pnpm，可以在允许联网或已有 npm 源的环境执行：

```powershell
npm install -g pnpm
```

如果公司不能联网，需要提前准备 Node.js 安装包和 pnpm 安装包，或使用公司内部 npm 镜像。

## 7. 安装依赖和构建 core

进入插件目录：

```powershell
cd "$env:USERPROFILE\.codex\understand-anything\understand-anything-plugin"
```

安装依赖：

```powershell
pnpm install
```

构建核心包：

```powershell
pnpm --filter @understand-anything/core build
```

验证构建产物：

```powershell
Test-Path "$env:USERPROFILE\.codex\understand-anything\understand-anything-plugin\packages\core\dist\index.js"
```

返回：

```text
True
```

如果 `pnpm install` 因为无法联网失败，需要提前准备依赖缓存或使用公司内部 npm registry。

## 8. 重启 Codex

复制 skills 后，需要重启 Codex 会话。

原因：

```text
Codex 通常在会话开始时加载 skills。
当前会话中新增的 skill 不一定立即可见。
```

重启后，在 Codex 对话里才能使用：

```text
$understand
```

## 9. 分析 codeAgent 项目

让 Codex 的工作目录位于：

```text
D:\Professional\myCode\codeAnalysis\codeAgent
```

在 Codex 对话里输入：

```text
$understand --language zh
```

注意：这不是 PowerShell 命令。

它会分析当前项目，并生成：

```text
D:\Professional\myCode\codeAnalysis\codeAgent\.ua\knowledge-graph.json
```

如果你想分析指定目录，可以输入：

```text
$understand D:\Professional\myCode\codeAnalysis\codeAgent --language zh
```

## 10. 打开 Dashboard

分析完成后，在 Codex 对话里输入：

```text
$understand-dashboard
```

它会启动一个本地 Dashboard，并给出类似：

```text
http://127.0.0.1:5173?token=xxxx
```

注意：URL 里的 `token` 不能省略。

## 11. 常用命令

在 Codex 对话里使用：

```text
$understand --language zh
```

生成或更新代码知识图谱。

```text
$understand-dashboard
```

打开可视化 Dashboard。

```text
$understand-chat How does the parent agent call code analysis?
```

基于图谱问问题。

```text
$understand-explain app/agents/parent_agent.py
```

解释指定文件。

```text
$understand-diff
```

分析当前改动影响。

```text
$understand-onboard
```

生成新人 onboarding 指南。

## 12. 分析 MES / EAP 项目

假设 MES 代码目录：

```text
D:\CompanyCode\MES-Fab12
```

在 Codex 对话里输入：

```text
$understand D:\CompanyCode\MES-Fab12 --language zh
```

或者让 Codex 工作目录直接进入 MES 项目，再输入：

```text
$understand --language zh
```

生成：

```text
D:\CompanyCode\MES-Fab12\.ua\knowledge-graph.json
```

打开 Dashboard：

```text
$understand-dashboard D:\CompanyCode\MES-Fab12
```

## 13. 大项目建议

MES / EAP 项目可能很大，首次分析会消耗较多 token。

建议先分析子目录：

```text
$understand D:\CompanyCode\MES-Fab12\src\TrackIn --language zh
```

确认效果后，再考虑分析完整项目。

## 14. 需要加入 .gitignore 的目录

Understand Anything 会生成：

```text
.ua/
```

建议加入项目 `.gitignore`：

```text
.ua/
.understand-anything/
```

如果是在 `codeAgent` 项目里，可以添加到：

```text
codeAgent/.gitignore
```

## 15. 和 CodeGraph 的关系

CodeGraph 和 Understand Anything 不是一类工具。

```text
CodeGraph：
  在线代码检索工具
  适合接入 CodeAnalysis Agent
  OnCall 排障时实时查相关代码

Understand Anything：
  离线架构理解工具
  适合生成 Dashboard
  用于学习项目结构、领域流程、onboarding
```

当前建议：

```text
CodeGraph 继续接入 codeAgent 的 CodeAnalysis 流程。
Understand Anything 暂时作为离线架构分析工具使用。
```

## 16. 常见问题

### 16.1 PowerShell 里执行 `$understand` 没反应

正常。

`$understand` 不是 PowerShell 命令，它是 Codex 对话里的 skill 调用。

### 16.2 Codex 里看不到 `$understand`

检查：

```powershell
Test-Path "$env:USERPROFILE\.codex\skills\understand\SKILL.md"
```

如果是 `False`，说明 skill 没复制成功。

如果是 `True`，请重启 Codex 会话。

### 16.3 提示找不到插件根目录

检查：

```powershell
Test-Path "$env:USERPROFILE\.codex\understand-anything\understand-anything-plugin\package.json"
```

如果是 `False`，说明插件目录没有复制到推荐位置。

### 16.4 提示 core 没有 build

执行：

```powershell
cd "$env:USERPROFILE\.codex\understand-anything\understand-anything-plugin"
pnpm --filter @understand-anything/core build
```

### 16.5 依赖安装失败

通常是公司网络不能访问 npm。

解决方式：

- 配置公司内部 npm registry
- 提前准备 pnpm store 缓存
- 在外网机器安装好依赖后整体打包

## 17. 最小验证清单

到公司后按下面检查：

```powershell
Test-Path "$env:USERPROFILE\.codex\skills\understand\SKILL.md"
Test-Path "$env:USERPROFILE\.codex\skills\understand-dashboard\SKILL.md"
Test-Path "$env:USERPROFILE\.codex\understand-anything\understand-anything-plugin\package.json"
node -v
pnpm -v
```

然后重启 Codex，在 Codex 对话里输入：

```text
$understand --language zh
```

如果能开始分析项目，说明离线 skill 安装基本成功。

