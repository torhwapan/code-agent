import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from app.business_logger import BusinessLogger
from app.config import RepositoryConfig
from app.engine import CodeAgentV2Engine


ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "configs" / "repositories.json"
LOG_DIR = ROOT / "data" / "business_logs"


class AppContext:
    def __init__(self):
        self.repositories = RepositoryConfig(CONFIG_PATH)
        self.logger = BusinessLogger(LOG_DIR)
        self.engine = CodeAgentV2Engine(self.repositories, self.logger)


CTX = AppContext()


class CodeAgentV2Handler(BaseHTTPRequestHandler):
    server_version = "CodeAgentV2/0.1"

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._send_json({"ok": True, "service": "code-agent-v2"})
            return
        if parsed.path == "/api/repositories":
            self._send_json({"repositories": CTX.repositories.list_repositories()})
            return
        self._send_json({"ok": False, "error": "Not found"}, status=404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path in {"/api/code-analysis", "/api/code-analysis/handle"}:
            try:
                payload = self._read_json()
            except ValueError as exc:
                self._send_json({"ok": False, "status": "error", "error": str(exc)}, status=400)
                return
            try:
                result = CTX.engine.handle(payload)
            except Exception as exc:
                self._send_json({"ok": False, "status": "error", "error": str(exc)}, status=500)
                return
            self._send_json(result)
            return
        self._send_json({"ok": False, "error": "Not found"}, status=404)

    def log_message(self, fmt, *args):
        print(f"[CodeAgentV2] {self.address_string()} - {fmt % args}")

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON request body: {exc}") from exc

    def _send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run(host="127.0.0.1", port=8020):
    server = ThreadingHTTPServer((host, port), CodeAgentV2Handler)
    print(f"CodeAgentV2 is running at http://{host}:{port}")
    print("POST /api/code-analysis with repo_id, message, context.")
    server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run CodeAgentV2 HTTP server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8020, type=int)
    args = parser.parse_args()
    run(args.host, args.port)
