import json
import os
import urllib.error
import urllib.request
from pathlib import Path


class LLMClient:
    # Keep model differences here. Agent code should only call chat().
    PROVIDER_DEFAULTS = {
        "openai": {
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o-mini",
            "supports_json_mode": True,
            "include_temperature": True,
            "default_temperature": 0.2,
            "max_tokens_param": "max_tokens",
        },
        "deepseek": {
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
            "supports_json_mode": False,
            "include_temperature": True,
            "default_temperature": 0.2,
            "max_tokens_param": "max_tokens",
        },
        "qwen": {
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model": "qwen-plus",
            "supports_json_mode": False,
            "include_temperature": True,
            "default_temperature": 0.2,
            "max_tokens_param": "max_tokens",
        },
        "custom": {
            "base_url": "http://127.0.0.1:8001/v1",
            "model": "default",
            "supports_json_mode": False,
            "include_temperature": True,
            "default_temperature": 0.2,
            "max_tokens_param": "max_tokens",
        },
    }

    def __init__(self, config_path="configs/llm.json"):
        self.config = self._load_config(config_path)
        self.profile = self._load_active_profile(self.config)

        self.provider = self._setting("LLM_PROVIDER", "provider", "openai")
        self.provider = self.provider.strip().lower()
        self.defaults = self.PROVIDER_DEFAULTS.get(self.provider, self.PROVIDER_DEFAULTS["custom"])

        self.api_key = self._setting("LLM_API_KEY", "api_key", None) or os.getenv("OPENAI_API_KEY")
        self.base_url = self._setting("LLM_BASE_URL", "base_url", self.defaults["base_url"]).rstrip("/")
        self.model = self._setting("LLM_MODEL", "model", self.defaults["model"])
        self.timeout = int(self._setting("LLM_TIMEOUT_SECONDS", "timeout_seconds", 60))

        self.supports_json_mode = self._setting_bool("LLM_SUPPORTS_JSON_MODE", "supports_json_mode", self.defaults["supports_json_mode"])
        self.include_temperature = self._setting_bool("LLM_INCLUDE_TEMPERATURE", "include_temperature", self.defaults["include_temperature"])
        self.temperature = self._setting_float("LLM_TEMPERATURE", "temperature", self.defaults["default_temperature"])
        self.max_tokens = self._setting_int("LLM_MAX_TOKENS", "max_tokens", None)
        self.max_tokens_param = self._setting("LLM_MAX_TOKENS_PARAM", "max_tokens_param", self.defaults["max_tokens_param"])
        self.top_p = self._setting_float("LLM_TOP_P", "top_p", None)
        self.extra_params = self._load_extra_params()

    @property
    def available(self):
        return bool(self.api_key)

    def chat(self, messages, json_mode=False):
        if not self.available:
            raise RuntimeError("LLM is not configured. Set LLM_API_KEY or OPENAI_API_KEY.")

        payload = self._build_payload(messages, json_mode)
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM request failed: HTTP {exc.code}: {body}")

        return data["choices"][0]["message"]["content"]

    def _build_payload(self, messages, json_mode):
        payload = {
            "model": self.model,
            "messages": messages,
        }

        if self.include_temperature and self.temperature is not None:
            payload["temperature"] = self.temperature
        if self.top_p is not None:
            payload["top_p"] = self.top_p
        if self.max_tokens is not None:
            payload[self.max_tokens_param] = self.max_tokens
        if json_mode and self.supports_json_mode:
            payload["response_format"] = {"type": "json_object"}

        payload.update(self.extra_params)
        return payload

    def _load_config(self, config_path):
        path = Path(config_path)
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _load_active_profile(self, config):
        profiles = config.get("profiles", {})
        active_name = os.getenv("LLM_PROFILE") or config.get("active_profile")
        if not active_name:
            return {}
        if active_name not in profiles:
            raise ValueError(f"LLM profile not found: {active_name}")
        return profiles[active_name]

    def _setting(self, env_name, config_name, default_value=None):
        value = os.getenv(env_name)
        if value is not None and value != "":
            return value
        value = self.profile.get(config_name)
        if value is not None and value != "":
            return value
        return default_value

    def _setting_bool(self, env_name, config_name, default_value):
        value = os.getenv(env_name)
        if value is not None:
            return self._parse_bool(value)
        if config_name in self.profile and self.profile[config_name] is not None:
            return bool(self.profile[config_name])
        return default_value

    def _setting_float(self, env_name, config_name, default_value=None):
        value = os.getenv(env_name)
        if value is not None and value != "":
            return float(value)
        value = self.profile.get(config_name)
        if value is not None and value != "":
            return float(value)
        return default_value

    def _setting_int(self, env_name, config_name, default_value=None):
        value = os.getenv(env_name)
        if value is not None and value != "":
            return int(value)
        value = self.profile.get(config_name)
        if value is not None and value != "":
            return int(value)
        return default_value

    def _parse_bool(self, value):
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def _resolve_bool(self, name, default_value):
        value = os.getenv(name)
        if value is None:
            return default_value
        return self._parse_bool(value)

    def _resolve_float(self, name, default_value=None):
        value = os.getenv(name)
        if value is None or value == "":
            return default_value
        return float(value)

    def _resolve_int(self, name, default_value=None):
        value = os.getenv(name)
        if value is None or value == "":
            return default_value
        return int(value)

    def _load_extra_params(self):
        raw = os.getenv("LLM_EXTRA_PARAMS")
        if raw:
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("LLM_EXTRA_PARAMS must be a JSON object")
            return data

        data = self.profile.get("extra_params", {})
        if data is None:
            return {}
        if not isinstance(data, dict):
            raise ValueError("extra_params in llm config must be an object")
        return data
