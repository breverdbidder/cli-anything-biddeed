"""
UTCC Registry — Supabase CRUD for task_registry and task_logs.
"""

import os
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx


SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")


def _headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskRegistry:
    """CRUD interface for task_registry and task_logs in Supabase."""

    def __init__(
        self,
        supabase_url: str = SUPABASE_URL,
        supabase_key: str = SUPABASE_KEY,
        timeout: float = 15.0,
    ):
        self.base = supabase_url.rstrip("/")
        self.key = supabase_key
        self.timeout = timeout

    def _hdrs(self) -> dict:
        return {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    # ------------------------------------------------------------------ #
    # task_registry                                                        #
    # ------------------------------------------------------------------ #

    def enqueue(
        self,
        task: str,
        task_type: str,
        platform: str = "hetzner",
        triggered_by: str = "manual",
        description: Optional[str] = None,
        batch_id: Optional[str] = None,
        batch_index: Optional[int] = None,
    ) -> dict:
        """Insert a new task into the registry with status=queued."""
        task_id = f"task-{uuid.uuid4().hex[:12]}"
        payload = {
            "task_id": task_id,
            "description": description or task[:200],
            "task_type": task_type,
            "platform": platform,
            "triggered_by": triggered_by,
            "status": "queued",
            "created_at": _now(),
        }
        if batch_id:
            payload["batch_id"] = batch_id
        if batch_index is not None:
            payload["batch_index"] = batch_index

        r = httpx.post(
            f"{self.base}/rest/v1/task_registry",
            headers=self._hdrs(),
            json=payload,
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()[0] if r.json() else payload

    def mark_running(self, task_id: str, gha_run_id: int = None, gha_run_url: str = None) -> None:
        """Update task status to running and record GHA run info."""
        data = {"status": "running", "dispatched_at": _now()}
        if gha_run_id:
            data["gha_run_id"] = gha_run_id
        if gha_run_url:
            data["gha_run_url"] = gha_run_url
        self._patch(task_id, data)

    def mark_completed(
        self,
        task_id: str,
        result_summary: str = None,
        tokens_used: int = 0,
        cost_usd: float = 0.0,
    ) -> None:
        """Update task status to completed."""
        self._patch(task_id, {
            "status": "completed",
            "completed_at": _now(),
            "result_summary": result_summary,
            "tokens_used": tokens_used,
            "cost_usd": cost_usd,
        })

    def mark_failed(self, task_id: str, error_message: str = None) -> None:
        """Update task status to failed."""
        self._patch(task_id, {
            "status": "failed",
            "completed_at": _now(),
            "error_message": error_message,
        })

    def get_task(self, task_id: str) -> Optional[dict]:
        """Fetch a single task by task_id."""
        r = httpx.get(
            f"{self.base}/rest/v1/task_registry",
            headers=self._hdrs(),
            params={"task_id": f"eq.{task_id}", "limit": "1"},
            timeout=self.timeout,
        )
        r.raise_for_status()
        rows = r.json()
        return rows[0] if rows else None

    def get_batch(self, batch_id: str) -> list[dict]:
        """Fetch all tasks belonging to a batch."""
        r = httpx.get(
            f"{self.base}/rest/v1/task_registry",
            headers=self._hdrs(),
            params={"batch_id": f"eq.{batch_id}", "order": "batch_index.asc"},
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    def list_queued(self, platform: str = None) -> list[dict]:
        """Return all queued tasks, optionally filtered by platform."""
        params = {"status": "eq.queued", "order": "created_at.asc"}
        if platform:
            params["platform"] = f"eq.{platform}"
        r = httpx.get(
            f"{self.base}/rest/v1/task_registry",
            headers=self._hdrs(),
            params=params,
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    def _patch(self, task_id: str, data: dict) -> None:
        hdrs = self._hdrs()
        hdrs["Prefer"] = "return=minimal"
        r = httpx.patch(
            f"{self.base}/rest/v1/task_registry",
            headers=hdrs,
            params={"task_id": f"eq.{task_id}"},
            json=data,
            timeout=self.timeout,
        )
        r.raise_for_status()

    # ------------------------------------------------------------------ #
    # task_logs                                                           #
    # ------------------------------------------------------------------ #

    def log(
        self,
        task_id: str,
        message: str,
        level: str = "info",
        metadata: Optional[dict] = None,
    ) -> None:
        """Append a log entry for a task."""
        payload = {
            "task_id": task_id,
            "timestamp": _now(),
            "level": level,
            "message": message,
        }
        if metadata:
            payload["metadata"] = metadata

        hdrs = self._hdrs()
        hdrs["Prefer"] = "return=minimal"
        httpx.post(
            f"{self.base}/rest/v1/task_logs",
            headers=hdrs,
            json=payload,
            timeout=self.timeout,
        )  # fire-and-forget; don't raise on log failure

    def get_logs(self, task_id: str, limit: int = 100) -> list[dict]:
        """Fetch logs for a task in chronological order."""
        r = httpx.get(
            f"{self.base}/rest/v1/task_logs",
            headers=self._hdrs(),
            params={
                "task_id": f"eq.{task_id}",
                "order": "timestamp.asc",
                "limit": str(limit),
            },
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()


# ------------------------------------------------------------------ #
# Module-level helpers using env credentials                          #
# ------------------------------------------------------------------ #

def _default_registry() -> TaskRegistry:
    return TaskRegistry()


def enqueue(task: str, task_type: str, **kwargs) -> dict:
    return _default_registry().enqueue(task, task_type, **kwargs)


def mark_completed(task_id: str, **kwargs) -> None:
    _default_registry().mark_completed(task_id, **kwargs)


def mark_failed(task_id: str, error_message: str = None) -> None:
    _default_registry().mark_failed(task_id, error_message)
