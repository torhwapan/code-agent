import time

from app.opencode_client import OpenCodeClient
from app.prompt_builder import build_opencode_prompt
from app.result_parser import extract_answer_text, summarize_answer


class CodeAgentV2Engine:
    def __init__(self, repositories, logger):
        self.repositories = repositories
        self.logger = logger

    def handle(self, payload):
        started = time.perf_counter()
        request_id = self.logger.new_request_id()
        repo_id = payload.get("repo_id") or self.repositories.data.get("default_repo_id") or "workspace"
        options = payload.get("options") or {}
        timeout_seconds = int(options.get("timeout_seconds") or 300)

        if not (payload.get("message") or "").strip():
            raise ValueError("message is required")

        repo = self.repositories.get_repository(repo_id)
        client = OpenCodeClient(
            repo.get("opencode_url"),
            password=repo.get("opencode_password") or "",
            timeout_seconds=timeout_seconds,
        )
        prompt = build_opencode_prompt(payload, repo)
        session_title = options.get("session_title") or self._session_title(payload)

        self.logger.write(
            "code_agent_v2.request_received",
            {
                "request_id": request_id,
                "repo_id": repo_id,
                "opencode_url": repo.get("opencode_url"),
                "message_preview": self.logger.preview(payload.get("message")),
                "context_length": len(payload.get("context") or ""),
            },
        )

        session = client.create_session(session_title)
        session_id = session.get("id")
        response = client.send_message(session_id, prompt, timeout_seconds=timeout_seconds)
        answer = extract_answer_text(response)
        duration_ms = int((time.perf_counter() - started) * 1000)

        result = {
            "ok": True,
            "status": "completed",
            "data": {
                "summary": summarize_answer(answer),
                "answer_markdown": answer,
                "repo_id": repo_id,
                "engine": "opencode",
                "opencode_session_id": session_id,
                "opencode_url": repo.get("opencode_url"),
                "duration_ms": duration_ms,
                "debug": {
                    "request_id": request_id,
                    "session": session,
                    "message_id": (response.get("info") or {}).get("id"),
                    "parts_count": len(response.get("parts") or []),
                },
            },
        }

        self.logger.write(
            "code_agent_v2.request_completed",
            {
                "request_id": request_id,
                "repo_id": repo_id,
                "opencode_session_id": session_id,
                "duration_ms": duration_ms,
                "answer_length": len(answer),
            },
        )
        return result

    def _session_title(self, payload):
        message = (payload.get("message") or "CodeAgentV2 analysis").strip()
        return message[:80]
