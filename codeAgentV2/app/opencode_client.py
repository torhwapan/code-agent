import json
import urllib.error
import urllib.request


class OpenCodeClient:
    def __init__(self, base_url, password="", timeout_seconds=300):
        self.base_url = (base_url or "").rstrip("/")
        self.password = password or ""
        self.timeout_seconds = timeout_seconds

    def health(self):
        return self.get_json("/doc", timeout_seconds=20)

    def create_session(self, title="CodeAgentV2 analysis"):
        payload = {"title": title}
        return self.post_json("/session", payload, timeout_seconds=60)

    def send_message(self, session_id, message, timeout_seconds=None):
        payload = {
            "parts": [
                {
                    "type": "text",
                    "text": message,
                }
            ]
        }
        return self.post_json(
            f"/session/{session_id}/message",
            payload,
            timeout_seconds=timeout_seconds or self.timeout_seconds,
        )

    def list_messages(self, session_id):
        return self.get_json(f"/session/{session_id}/message", timeout_seconds=60)

    def get_json(self, path, timeout_seconds=None):
        request = urllib.request.Request(
            self.base_url + path,
            headers=self._headers(),
            method="GET",
        )
        return self._send(request, timeout_seconds or self.timeout_seconds)

    def post_json(self, path, payload, timeout_seconds=None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + path,
            data=body,
            headers=self._headers(),
            method="POST",
        )
        return self._send(request, timeout_seconds or self.timeout_seconds)

    def _headers(self):
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if self.password:
            # opencode serve documents OPENCODE_SERVER_PASSWORD as basic auth.
            import base64

            token = base64.b64encode(f":{self.password}".encode("utf-8")).decode("ascii")
            headers["Authorization"] = f"Basic {token}"
        return headers

    def _send(self, request, timeout_seconds):
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read().decode("utf-8")
                if not raw:
                    return {}
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"opencode HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"opencode connection failed: {exc.reason}") from exc
