# OpenCode API 手动测试流程

本文档记录本地验证 opencode HTTP API 的步骤。你可以按这个流程在公司电脑上手动测试。

## 1. 确认 opencode 已安装

```powershell
opencode --version
```

期望能看到版本号，例如：

```text
1.14.50
```

如果提示找不到命令，说明 opencode 没有加入 PATH，先处理安装或环境变量。

## 2. 查看 serve 参数

```powershell
opencode serve --help
```

确认支持：

```text
--hostname
--port
--print-logs
```

## 2.1 确认 curl 命令

后面的 HTTP 测试默认使用：

```powershell
curl
```

先确认公司电脑上是否可用：

```powershell
curl --version
```

如果能输出版本号，就直接使用文档里的 `curl` 命令。

如果你的 Windows 环境里只有 `curl.exe`，也可以把文档里的：

```text
curl
```

替换成：

```text
curl.exe
```

两者作用一样，都是用命令行发送 HTTP 请求。

## 3. 进入要分析的代码目录

先进入一个真实代码仓库目录。测试当前项目时可以用：

```powershell
cd D:\Professional\myCode\codeAnalysis\codeAgent
```

后续在公司测 MES / EAP 代码时，进入对应代码根目录，例如：

```powershell
cd D:\CompanyCode\MES-Fab12
```

opencode session 会以当前目录作为工作目录。

## 4. 启动 opencode server

```powershell
opencode serve --hostname 127.0.0.1 --port 9101 --print-logs
```

正常会看到类似输出：

```text
Warning: OPENCODE_SERVER_PASSWORD is not set; server is unsecured.
opencode server listening on http://127.0.0.1:9101
```

说明：

- 本地测试用 `127.0.0.1` 即可。
- 如果要给其他机器访问，可以改成 `0.0.0.0`。
- 正式环境建议设置 `OPENCODE_SERVER_PASSWORD` 或限制内网访问。

## 5. 测试 OpenAPI 文档接口

新开一个命令行窗口，执行：

```bash
curl -i http://127.0.0.1:9101/doc
```

如果成功，说明 HTTP API 可访问。

也可以只看状态码：

```bash
curl -o NUL -s -w "%{http_code}\n" http://127.0.0.1:9101/doc
```

期望：

```text
200
```

说明：Windows PowerShell 里 `curl` 有时可能是别名。如果 `curl --version` 输出正常，就继续用 `curl`；如果不正常，改用 `curl.exe`。

## 6. 查看有哪些 session 接口

如果你本机有 `findstr`，可以粗略查看 OpenAPI 里是否包含 session 相关接口：

```bash
curl -s http://127.0.0.1:9101/doc | findstr /i "session message prompt wait"
```

如果有 `python`，更推荐用下面这个命令格式化查看：

```bash
curl -s http://127.0.0.1:9101/doc > opencode-doc.json
python -c "import json; d=json.load(open('opencode-doc.json',encoding='utf-8')); print('\n'.join(sorted(p for p in d['paths'] if any(x in p for x in ['session','message','prompt','wait']))))"
```

正常能看到类似：

```text
/session
/session/{sessionID}
/session/{sessionID}/message
/session/{sessionID}/prompt_async
/api/session
/api/session/{sessionID}/prompt
/api/session/{sessionID}/wait
```

## 7. 创建 session

```bash
curl -s -X POST http://127.0.0.1:9101/session ^
  -H "Content-Type: application/json" ^
  -d "{\"title\":\"CodeAgent API test\"}"
```

期望返回类似：

```json
{
  "id": "ses_xxx",
  "directory": "D:\\Professional\\myCode\\codeAnalysis\\codeAgent",
  "title": "CodeAgent API test",
  "version": "1.14.50"
}
```

记录返回里的 `id`，后面用它替换命令中的 `SESSION_ID`。

如果你有 `python`，也可以直接提取 session id：

```bash
curl -s -X POST http://127.0.0.1:9101/session ^
  -H "Content-Type: application/json" ^
  -d "{\"title\":\"CodeAgent API test\"}" > session.json

python -c "import json; print(json.load(open('session.json',encoding='utf-8'))['id'])"
```

## 8. 查询 session

把 `SESSION_ID` 替换成上一步返回的 session id：

```bash
curl -s http://127.0.0.1:9101/session/SESSION_ID
```

确认返回的 `directory` 是你启动 opencode server 时所在的代码目录。

## 9. 查询消息列表

```bash
curl -s http://127.0.0.1:9101/session/SESSION_ID/message
```

刚创建的 session 一般为空。

## 10. 发送一个最小 prompt

注意：PowerShell 直接写中文 JSON 时，可能会出现编码问题。为了先验证链路，建议先用英文测试。

```bash
curl -s -X POST http://127.0.0.1:9101/session/SESSION_ID/message ^
  -H "Content-Type: application/json" ^
  -d "{\"parts\":[{\"type\":\"text\",\"text\":\"Please reply with exactly: OK\"}]}"
```

如果成功，会返回 assistant message，里面一般包含：

```text
info
parts
```

其中 `parts` 里 `type=text` 的部分就是模型回答。

## 11. 提取文本回答

如果你有 `python`，可以这样提取 `type=text` 的回答：

```bash
curl -s -X POST http://127.0.0.1:9101/session/SESSION_ID/message ^
  -H "Content-Type: application/json" ^
  -d "{\"parts\":[{\"type\":\"text\",\"text\":\"Please reply with exactly: OK\"}]}" > response.json

python -c "import json; d=json.load(open('response.json',encoding='utf-8')); print('\n'.join(p.get('text','') for p in d.get('parts',[]) if p.get('type')=='text'))"
```

## 12. 测试代码分析问题

如果你是在 `codeAgent` 目录启动的 opencode server，可以测试：

```bash
curl -s -X POST http://127.0.0.1:9101/session/SESSION_ID/message ^
  -H "Content-Type: application/json" ^
  -d "{\"parts\":[{\"type\":\"text\",\"text\":\"Analyze how app/code_analysis/agent.py works. Please answer with key flow and important files.\"}]}" > code-analysis-response.json

python -c "import json; d=json.load(open('code-analysis-response.json',encoding='utf-8')); print('\n'.join(p.get('text','') for p in d.get('parts',[]) if p.get('type')=='text'))"
```

如果是在 MES / EAP 代码目录启动的，把问题换成真实代码问题。

## 13. 停止 opencode server

在启动 opencode server 的窗口按：

```text
Ctrl + C
```

如果你是后台启动的，可以查端口并停止进程：

```powershell
$conns = Get-NetTCPConnection -LocalPort 9101 -ErrorAction SilentlyContinue
foreach ($conn in $conns) {
  Stop-Process -Id $conn.OwningProcess -Force
}
```

## 14. 常见问题

### 14.1 `/doc` 能访问，但发 prompt 失败

可能原因：

- opencode 没有配置可用模型。
- 当前模型鉴权失败。
- 公司网络无法访问模型服务。
- 请求超时太短。

建议先在 opencode CLI 里确认普通对话是否能跑通。

### 14.2 中文变成问号

PowerShell 直接构造 JSON 时可能有编码问题。

后续我们做 CodeAgentV2 时会用 Python `requests` 发 UTF-8 JSON，避免这个问题。

手动测试阶段可以先用英文 prompt 验证接口链路。

### 14.3 server 提示没有密码

提示：

```text
OPENCODE_SERVER_PASSWORD is not set; server is unsecured.
```

本地测试可以先忽略。

正式部署建议：

- 设置 `OPENCODE_SERVER_PASSWORD`。
- 或只监听 `127.0.0.1`，由本机 CodeAgentV2 转发。
- 或通过内网网关加鉴权。

## 15. 本次已验证结论

本地已验证：

- `opencode --version` 可用。
- `opencode serve` 可启动。
- `GET /doc` 返回 OpenAPI JSON。
- `POST /session` 可创建 session。
- `GET /session/{sessionID}` 可查询 session。
- `GET /session/{sessionID}/message` 可查询消息列表。
- `POST /session/{sessionID}/message` 可发送 prompt 并拿到 assistant response。

这说明 opencode 可以作为 CodeAgentV2 的底层代码分析引擎。

