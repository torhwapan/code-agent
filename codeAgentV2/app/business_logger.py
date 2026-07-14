import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


class BusinessLogger:
    def __init__(self, log_dir):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def new_request_id(self):
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"REQ-{stamp}-{uuid.uuid4().hex[:8]}"

    def write(self, event, payload):
        record = {
            "event": event,
            "logged_at": datetime.now(timezone.utc).isoformat(),
        }
        record.update(payload or {})

        path = self.log_dir / (datetime.now().strftime("%Y%m%d") + ".jsonl")
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def preview(self, value, limit=500):
        text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
        if len(text) <= limit:
            return text
        return text[:limit] + "...<truncated>"
