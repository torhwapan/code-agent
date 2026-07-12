import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from app.code_analysis.agent import CodeAnalysisAgent
from app.code_analysis.config import RepositoryRegistry
from app.code_analysis.llm import LLMClient
from app.code_analysis.tools import LocalCodeTools


ROOT = Path(__file__).resolve().parent.parent.parent
CASE_DIR = ROOT / "data" / "cases"


class CodeAnalysisContext:
    def __init__(self):
        registry = RepositoryRegistry(ROOT / "configs" / "repositories.json")
        tools = LocalCodeTools(registry)
        self.agent = CodeAnalysisAgent(tools, LLMClient(), CASE_DIR)


CTX = CodeAnalysisContext()


class CodeAnalysisHandler(BaseHTTPRequestHandler):
    server_version = "CodeAnalysisAgent/0.1"

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._send_json({"ok": True, "service": "code-analysis-agent"})
            return
        self._send_json({"error": "Not found"}, status=404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/code-analysis/handle":
            request = self._read_json()
            try:
                result = CTX.agent.handle_input(request)
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=500)
                return
            self._send_json({"ok": True, "status": "completed", "data": result})
            return
        if parsed.path == "/api/code-analysis/analyze":
            task = self._read_json()
            try:
                result = CTX.agent.analyze_task(task)
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=500)
                return
            self._send_json({"ok": True, "status": "completed", "data": result})
            return
        self._send_json({"error": "Not found"}, status=404)

    def log_message(self, fmt, *args):
        print(f"[CodeAnalysisAgent] {self.address_string()} - {fmt % args}")

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw)

    def _send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run(host="127.0.0.1", port=8010):
    server = ThreadingHTTPServer((host, port), CodeAnalysisHandler)
    print(f"CodeAnalysisAgent is running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run standalone CodeAnalysisAgent service.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8010, type=int)
    args = parser.parse_args()
    run(args.host, args.port)
