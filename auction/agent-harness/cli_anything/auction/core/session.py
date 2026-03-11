"""Session management for ZoneWise CLI.

Tracks current state: active county, scrape history, undo stack.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


SESSION_DIR = Path.home() / ".config" / "cli-anything" / "auction"


class Session:
    def __init__(self, path: Optional[str] = None):
        self.path = Path(path) if path else SESSION_DIR / "session.json"
        self.current_county: Optional[str] = None
        self.history: list[dict] = []
        self.undo_stack: list[dict] = []
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text())
                self.current_county = data.get("current_county")
                self.history = data.get("history", [])
                self.undo_stack = data.get("undo_stack", [])
            except (json.JSONDecodeError, OSError):
                pass

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "current_county": self.current_county,
            "history": self.history[-100:],  # Keep last 100
            "undo_stack": self.undo_stack[-20:],
        }
        self.path.write_text(json.dumps(data, indent=2))

    def record(self, command: str, result: Any = None):
        entry = {
            "command": command,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "county": self.current_county,
            "result_summary": str(result)[:200] if result else None,
        }
        self.history.append(entry)
        self.undo_stack.append(entry)
        self.save()

    def undo(self) -> Optional[dict]:
        if self.undo_stack:
            return self.undo_stack.pop()
        return None

    def status(self) -> dict:
        return {
            "current_county": self.current_county,
            "history_count": len(self.history),
            "undo_available": len(self.undo_stack),
        }

    def clear(self):
        self.current_county = None
        self.history = []
        self.undo_stack = []
        self.save()
