"""Observability for CLI-Anything BidDeed agents.

Structured logging, metrics counters, Supabase tracking, Telegram alerting.
Fixes Sprint 1 Eval gap: Observability was 5/10.
"""

import json
import logging
import os
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


# --- Structured Logger ---

def get_logger(agent_name: str, level: int = logging.INFO) -> logging.Logger:
    """Get a structured logger for an agent."""
    logger = logging.getLogger(f"cli_anything.{agent_name}")
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            json.dumps({
                "ts": "%(asctime)s",
                "agent": agent_name,
                "level": "%(levelname)s",
                "msg": "%(message)s",
            })
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


# --- Metrics Counters ---

@dataclass
class AgentMetrics:
    """In-memory metrics counters for an agent session."""
    agent_name: str
    tool_calls: Counter = field(default_factory=Counter)
    tool_errors: Counter = field(default_factory=Counter)
    permission_denials: Counter = field(default_factory=Counter)
    tool_latency_ms: dict = field(default_factory=dict)  # tool_name -> [latencies]
    compaction_count: int = 0
    tokens_saved_by_compaction: int = 0
    session_start: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def record_call(self, tool_name: str, latency_ms: float, success: bool, error: Optional[str] = None):
        """Record a tool execution."""
        self.tool_calls[tool_name] += 1
        if not success:
            self.tool_errors[tool_name] += 1
        if tool_name not in self.tool_latency_ms:
            self.tool_latency_ms[tool_name] = []
        self.tool_latency_ms[tool_name].append(latency_ms)

    def record_denial(self, tool_name: str):
        """Record a permission denial."""
        self.permission_denials[tool_name] += 1

    def record_compaction(self, tokens_before: int, tokens_after: int):
        """Record a compaction event."""
        self.compaction_count += 1
        self.tokens_saved_by_compaction += (tokens_before - tokens_after)

    def summary(self) -> dict:
        """Export metrics as structured dict."""
        total_calls = sum(self.tool_calls.values())
        total_errors = sum(self.tool_errors.values())
        total_denials = sum(self.permission_denials.values())
        avg_latency = {}
        for name, latencies in self.tool_latency_ms.items():
            if latencies:
                avg_latency[name] = round(sum(latencies) / len(latencies), 1)
        return {
            "agent": self.agent_name,
            "session_start": self.session_start,
            "total_calls": total_calls,
            "total_errors": total_errors,
            "error_rate": round(total_errors / max(total_calls, 1) * 100, 1),
            "total_denials": total_denials,
            "calls_by_tool": dict(self.tool_calls),
            "errors_by_tool": dict(self.tool_errors),
            "denials_by_tool": dict(self.permission_denials),
            "avg_latency_ms": avg_latency,
            "compaction_count": self.compaction_count,
            "tokens_saved": self.tokens_saved_by_compaction,
        }


# --- Supabase Tracking ---

def log_to_supabase(metrics: AgentMetrics, table: str = "tool_executions") -> Optional[dict]:
    """Push metrics summary to Supabase. Returns insert result or None on failure."""
    try:
        from .supabase import get_client
        client = get_client("shared")
        data = metrics.summary()
        data["logged_at"] = datetime.now(timezone.utc).isoformat()
        result = client.table(table).insert(data).execute()
        return {"status": "logged", "count": len(result.data) if result.data else 0}
    except Exception as e:
        return {"status": "failed", "error": str(e)}


# --- Telegram Alerting ---

def send_alert(message: str, level: str = "info") -> bool:
    """Send alert to Telegram if configured. Returns True if sent."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        return False
    try:
        import urllib.request
        emoji = {"info": "ℹ️", "warn": "⚠️", "error": "🚨", "denied": "🔒"}.get(level, "📌")
        payload = json.dumps({
            "chat_id": chat_id,
            "text": f"{emoji} <b>CLI-Anything</b>\n{message}",
            "parse_mode": "HTML",
        })
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data=payload.encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
        return True
    except Exception:
        return False


# --- Execution Timer ---

class ToolTimer:
    """Context manager for timing tool execution."""

    def __init__(self):
        self.start_ns: int = 0
        self.elapsed_ms: float = 0.0

    def __enter__(self):
        self.start_ns = time.monotonic_ns()
        return self

    def __exit__(self, *args):
        self.elapsed_ms = (time.monotonic_ns() - self.start_ns) / 1_000_000
