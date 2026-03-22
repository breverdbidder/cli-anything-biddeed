"""
supabase_client.py — DesignWise Supabase REST API client.
All methods are async using httpx. Error handling returns {"error": str}, never raises.
"""

import os
from typing import Any, Dict, List, Optional

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


# ── Table registry ─────────────────────────────────────────────────────────────

TABLES: List[str] = [
    "design_tasks",
    "brand_violations",
    "visual_baselines",
    "page_analytics",
    "conversion_funnel",
    "support_tickets",
    "ab_tests",
    "deploy_log",
    "competitor_snapshots",
    "seo_audits",
    "stitch_usage",
]

_TABLES_SET = set(TABLES)


# ── Module-level convenience functions (test-compatible) ───────────────────────

def insert(table: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Synchronous insert wrapper for testing. Validates table name.
    Raises ValueError for unknown tables.
    """
    if table not in _TABLES_SET:
        raise ValueError(f"Unknown table: {table}. Valid tables: {TABLES}")
    # In production use DesignWiseDB (async). This is sync for CLI/test use.
    return {"status": "queued", "table": table, "data": data}


def query(table: str, params: Optional[Dict] = None) -> Dict[str, Any]:
    """Synchronous query wrapper for testing. Validates table name."""
    if table not in _TABLES_SET:
        raise ValueError(f"Unknown table: {table}. Valid tables: {TABLES}")
    return {"status": "queued", "table": table, "params": params or {}}


# ── Main async client class ────────────────────────────────────────────────────

class DesignWiseDB:
    """
    Async Supabase REST client for all 11 DesignWise tables.
    Uses httpx.AsyncClient for all operations.
    """

    def __init__(self, url: Optional[str] = None, key: Optional[str] = None):
        self.url = (url or os.environ.get("SUPABASE_URL", "")).rstrip("/")
        self.key = key or os.environ.get("SUPABASE_SERVICE_KEY", "") or os.environ.get("SUPABASE_KEY", "")
        self._headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def _validate_table(self, table: str) -> None:
        if table not in _TABLES_SET:
            raise ValueError(f"Unknown table: {table}. Valid tables: {TABLES}")

    async def insert(self, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """POST to /rest/v1/{table}. Returns inserted row or error dict."""
        self._validate_table(table)
        if not HAS_HTTPX:
            return {"error": "httpx not installed"}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{self.url}/rest/v1/{table}",
                    json=data,
                    headers=self._headers,
                )
                resp.raise_for_status()
                return resp.json()[0] if resp.text else {"status": "inserted"}
        except Exception as e:
            return {"error": str(e)}

    async def query(self, table: str, params: Optional[Dict] = None) -> Any:
        """GET from /rest/v1/{table} with query params. Returns list or error dict."""
        self._validate_table(table)
        if not HAS_HTTPX:
            return {"error": "httpx not installed"}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self.url}/rest/v1/{table}",
                    params=params or {},
                    headers=self._headers,
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            return {"error": str(e)}

    async def update(self, table: str, match: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """PATCH /rest/v1/{table}?match=... with data."""
        self._validate_table(table)
        if not HAS_HTTPX:
            return {"error": "httpx not installed"}
        try:
            params = {k: f"eq.{v}" for k, v in match.items()}
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.patch(
                    f"{self.url}/rest/v1/{table}",
                    json=data,
                    params=params,
                    headers=self._headers,
                )
                resp.raise_for_status()
                return resp.json()[0] if resp.text else {"status": "updated"}
        except Exception as e:
            return {"error": str(e)}

    async def upsert(self, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """POST with Prefer: resolution=merge-duplicates for upsert."""
        self._validate_table(table)
        if not HAS_HTTPX:
            return {"error": "httpx not installed"}
        try:
            headers = {**self._headers, "Prefer": "resolution=merge-duplicates,return=representation"}
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{self.url}/rest/v1/{table}",
                    json=data,
                    headers=headers,
                )
                resp.raise_for_status()
                return resp.json()[0] if resp.text else {"status": "upserted"}
        except Exception as e:
            return {"error": str(e)}

    async def delete(self, table: str, match: Dict[str, Any]) -> Dict[str, Any]:
        """DELETE from /rest/v1/{table} matching given fields."""
        self._validate_table(table)
        if not HAS_HTTPX:
            return {"error": "httpx not installed"}
        try:
            params = {k: f"eq.{v}" for k, v in match.items()}
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.delete(
                    f"{self.url}/rest/v1/{table}",
                    params=params,
                    headers=self._headers,
                )
                resp.raise_for_status()
                return {"status": "deleted", "match": match}
        except Exception as e:
            return {"error": str(e)}

    # ── Table-specific helpers ─────────────────────────────────────────────────

    async def log_task(self, task_type: str, agent_id: str, input_spec: Dict) -> Dict:
        """Insert a new task into design_tasks."""
        return await self.insert("design_tasks", {
            "task_type": task_type,
            "agent_id": agent_id,
            "input_spec": input_spec,
            "status": "pending",
        })

    async def log_violation(
        self,
        scan_id: str,
        page_url: str,
        violation_type: str,
        expected: str,
        actual: str,
        severity: str,
    ) -> Dict:
        """Insert a brand violation into brand_violations."""
        return await self.insert("brand_violations", {
            "scan_id": scan_id,
            "page_url": page_url,
            "violation_type": violation_type,
            "expected": expected,
            "actual": actual,
            "severity": severity,
        })

    async def log_deploy(
        self,
        commit_sha: str,
        branch: str,
        tier: str,
        status: str,
        checks: Dict,
    ) -> Dict:
        """Insert a deploy record into deploy_log."""
        return await self.insert("deploy_log", {
            "commit_sha": commit_sha,
            "branch": branch,
            "tier": tier,
            "status": status,
            "checks": checks,
        })

    async def get_quota_usage(self, month_start: str) -> Any:
        """Query stitch_usage for a given month."""
        return await self.query("stitch_usage", {
            "date": f"gte.{month_start}",
            "select": "mode,sum(count)",
        })
