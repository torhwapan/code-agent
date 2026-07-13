from __future__ import annotations

import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from app.code_analysis.agent import CodeAnalysisAgent
from app.code_analysis.codegraph_tool import CodeGraphTool
from app.code_analysis.config import RepositoryRegistry
from app.code_analysis.llm import LLMClient
from app.code_analysis.tools import LocalCodeTools
from app.agents.parent_agent import OnCallParentAgent


ROOT = Path(__file__).resolve().parent.parent
WEB_ROOT = ROOT / "app" / "web"
CASE_DIR = ROOT / "data" / "cases"


class AppContext:
    def __init__(self) -> None:
        self.registry = RepositoryRegistry(ROOT / "configs" / "repositories.json")
        self.tools = LocalCodeTools(self.registry)
        self.codegraph_tool = CodeGraphTool(self.registry, ROOT / "configs" / "codegraph.json")
        self.llm = LLMClient()
        self.agent = CodeAnalysisAgent(self.tools, self.llm, CASE_DIR, codegraph_tool=self.codegraph_tool)
        self.parent_agent = OnCallParentAgent(
            code_agent=self.agent,
            code_agent_url=os.getenv("CODE_ANALYSIS_AGENT_URL"),
        )


CTX = AppContext()


class OnCallHandler(BaseHTTPRequestHandler):
    server_version = "CodeAgent/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_file(WEB_ROOT / "index.html")
            return
        if parsed.path == "/api/repositories":
            self._send_json(
                {
                    "repositories": [repo.to_dict() for repo in CTX.registry.list()],
                    "llm_enabled": CTX.llm.available,
                    "model": CTX.llm.model if CTX.llm.available else None,
                }
            )
            return
        if parsed.path.startswith("/api/cases/"):
            case_id = parsed.path.rsplit("/", 1)[-1]
            self._send_case(case_id)
            return
        if parsed.path.startswith("/static/"):
            self._send_file(WEB_ROOT / parsed.path.removeprefix("/static/"))
            return
        self._send_json({"error": "Not found"}, status=404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/oncall":
            payload = self._read_json()
            try:
                result = CTX.parent_agent.handle(payload)
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)
                return
            status = 200 if result.get("ok") else 400
            self._send_json(result, status=status)
            return
        if parsed.path == "/api/analyze":
            payload = self._read_json()
            repo_id = str(payload.get("repo_id") or "workspace")
            description = str(payload.get("message") or payload.get("description") or payload.get("user_message") or "")
            analysis_text = "\n".join(
                part for part in [description, str(payload.get("extra_text") or "")] if part.strip()
            )
            max_steps = int(payload.get("max_steps") or 8)
            if not analysis_text.strip():
                self._send_json({"error": "message is required"}, status=400)
                return
            try:
                result = CTX.agent.analyze(
                    repo_id=repo_id,
                    analysis_text=analysis_text,
                    description=description,
                    max_steps=max_steps,
                )
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)
                return
            self._send_json(result)
            return
        self._send_json({"error": "Not found"}, status=404)

    def log_message(self, fmt: str, *args) -> None:
        print(f"[CodeAgent] {self.address_string()} - {fmt % args}")

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw)

    def _send_case(self, case_id: str) -> None:
        safe = "".join(ch for ch in case_id if ch.isalnum() or ch in "-_")
        path = CASE_DIR / f"{safe}.json"
        if not path.exists():
            self._send_json({"error": "Case not found"}, status=404)
            return
        self._send_json(json.loads(path.read_text(encoding="utf-8")))

    def _send_file(self, path: Path) -> None:
        try:
            resolved = path.resolve()
            web_root = WEB_ROOT.resolve()
            if resolved != web_root and web_root not in resolved.parents:
                self._send_json({"error": "Forbidden"}, status=403)
                return
            if not resolved.exists() or not resolved.is_file():
                self._send_json({"error": "Not found"}, status=404)
                return
            content_type = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
            body = resolved.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=500)

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), OnCallHandler)
    print(f"CodeAgent is running at http://{host}:{port}")
    print("Open the page and ask code analysis questions. Configure configs/llm.json to enable LLM analysis.")
    server.serve_forever()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run CodeAgent web server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    args = parser.parse_args()
    run(args.host, args.port)
