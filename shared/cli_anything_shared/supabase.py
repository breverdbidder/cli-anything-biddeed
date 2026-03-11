"""Supabase client and persistence utilities for CLI-Anything BidDeed tools.

Provides connection management, CRUD operations, and health checks.
"""

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Optional

from .config import get_config

_client = None


def get_client(cli_name: str = "shared"):
    """Get or create Supabase client. Raises RuntimeError if not configured."""
    global _client
    if _client is not None:
        return _client

    url = get_config(cli_name, "supabase_url", env_var="SUPABASE_URL")
    key = get_config(cli_name, "supabase_key", env_var="SUPABASE_KEY")

    if not url or not key:
        raise RuntimeError(
            "Supabase not configured. Set credentials with:\n"
            "  export SUPABASE_URL=https://xxx.supabase.co\n"
            "  export SUPABASE_KEY=xxx\n"
            f"  # or: cli-anything-{cli_name} config set supabase_url <url>"
        )

    try:
        from supabase import create_client
        _client = create_client(url, key)
        return _client
    except ImportError:
        raise RuntimeError(
            "supabase package not installed. Install with:\n"
            "  pip install supabase"
        )


def persist_result(table: str, data: dict, cli_name: str = "shared") -> dict:
    """Insert a row into Supabase. Returns the inserted row with ID."""
    client = get_client(cli_name)
    data["created_at"] = datetime.now(timezone.utc).isoformat()
    result = client.table(table).insert(data).execute()
    if result.data:
        return result.data[0]
    return {"error": "Insert returned no data", "table": table}


def read_result(table: str, id_value: Any, id_column: str = "id", cli_name: str = "shared") -> Optional[dict]:
    """Fetch a single row by ID."""
    client = get_client(cli_name)
    result = client.table(table).select("*").eq(id_column, id_value).limit(1).execute()
    if result.data:
        return result.data[0]
    return None


def upsert_rows(table: str, data: list[dict], cli_name: str = "shared") -> int:
    """Upsert multiple rows. Returns count of affected rows."""
    client = get_client(cli_name)
    result = client.table(table).upsert(data).execute()
    return len(result.data) if result.data else 0


def query_table(table: str, filters: Optional[dict] = None, limit: int = 100, cli_name: str = "shared") -> list[dict]:
    """Query a table with optional filters."""
    client = get_client(cli_name)
    q = client.table(table).select("*")
    if filters:
        for key, value in filters.items():
            q = q.eq(key, value)
    result = q.limit(limit).execute()
    return result.data or []


def health_check(cli_name: str = "shared") -> bool:
    """Verify Supabase connectivity. Returns True or raises."""
    try:
        client = get_client(cli_name)
        # Simple query to verify connection
        client.table("audit_log").select("id").limit(1).execute()
        return True
    except Exception as e:
        raise RuntimeError(f"Supabase health check failed: {e}")


def reset_client():
    """Reset cached client (for testing)."""
    global _client
    _client = None
