# OnCallAgent MVP

这是 OnCallAgent 第一版原型，当前重点是：

> 根据 OP 上传或粘贴的错误日志，在本机配置好的代码目录中进行多轮代码搜索、文件读取和代码分析，并生成诊断报告。

## 启动

先进入项目目录：

```powershell
cd codeAgent
```

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
{
  "id": "mes-core",
  "name": "MES Core",
  "root": "D:/apps/repos/mes-core",
  "include": ["**/*.java", "**/*.xml", "**/*.sql", "**/*.properties"],
  "exclude": [".git", "target", "build", "node_modules"]
}
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
  "active_profile": "bailian-qwen",
  "profiles": {
    "bailian-qwen": {
      "provider": "qwen",
      "base_url": "https://your-bailian-endpoint/compatible-mode/v1",
      "api_key": "your-key",
      "model": "qwen3.7-plus",
      "supports_json_mode": false
    },
    "openai": {
      "provider": "openai",
      "base_url": "https://api.openai.com/v1",
      "api_key": "your-key",
      "model": "gpt-4o-mini",
      "supports_json_mode": true
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

或者：

```json
"active_profile": "deepseek"
```

## 环境变量覆盖

如果你在生产环境不想把 key 写进文件，也可以用环境变量覆盖：

```powershell
$env:LLM_PROFILE="bailian-qwen"
$env:LLM_API_KEY="your-key"
python -m app.main --host 127.0.0.1 --port 8000
```

优先级是：

```text
环境变量 > configs/llm.json > 默认值
```

## 常用配置项

```json
{
  "provider": "qwen",
  "base_url": "https://your-endpoint/v1",
  "api_key": "your-key",
  "model": "qwen3.7-plus",
  "timeout_seconds": 60,
  "supports_json_mode": false,
  "include_temperature": true,
  "temperature": 0.2,
  "max_tokens": null,
  "max_tokens_param": "max_tokens",
  "top_p": null,
  "extra_params": {}
}
```

不同模型参数不一致时，尽量只改 `configs/llm.json`，不要改 Agent 业务逻辑。


20260708新增需求：
提取lotId，厂别，运行环境。

日志，通过ftp传输日志文件，一个30M，每个文件只是近2min的日志量
通过DB SQL查询环境、serverIp、module
{env}/{serverIp}/{module}/{....26-07-06T05_02_56}


1, DB 查询Agent。 有一些固定的sql示例，比如查询LotHistory的，查询Lot是哪个module的
2，要根据LotHistory 及 半导体业务经验，判断是哪个rule的，然后根据ruleName lotId 查询是哪个ip服务器处理的，是什么时间处理的，是在哪个模块处理的，是在什么环境处理的。
3, 根据解析出来的数据，查询日志，日志服务器的访问方式为ftp，通过ip port + 账号密码访问，每个厂别一个ip，这个ip会提前配置好。日志文件在服务器的{env}/{serverIp}/{module}/{....26-07-06T05_02_56}目录中，其中{....26-07-06T05_02_56}中文件名的后缀为日志时间，平均每2分钟就有一个日志文件，一个日志文件30min，我理解是要先将日志传输出来再提取关键时间点的日志

