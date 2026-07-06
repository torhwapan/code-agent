# OnCallAgent MVP

这是 OnCallAgent 第一版原型，当前重点是：

> 根据 OP 上传或粘贴的错误日志，在本机配置好的代码目录中进行多轮代码搜索、文件读取和代码分析，并生成诊断报告。

## 启动

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

第一次使用时，可以从模板复制一份：

```powershell
Copy-Item configs/llm.example.json configs/llm.json
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
