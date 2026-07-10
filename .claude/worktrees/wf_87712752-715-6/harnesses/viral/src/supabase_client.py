"""
Supabase client for viral pipeline — replaces JSONL file persistence.
Uses REST API directly (no SDK dependency).
"""

import json
import os
import urllib.request

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def _request(method: str, table: str, data=None, params="") -> dict:
    """Generic Supabase REST request."""
    url = f"{SUPABASE_URL}/rest/v1/{table}{params}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        return {"error": f"HTTP {e.code}", "detail": error_body}
    except Exception as e:
        return {"error": str(e)}


def upsert(table: str, data: dict) -> dict:
    """Insert or update a row."""
    return _request("POST", table, data, "?on_conflict=id")


def select(table: str, params: str = "") -> list:
    """Select rows."""
    result = _request("GET", table, params=f"?select=*{params}")
    return result if isinstance(result, list) else []


def get_brain() -> dict:
    """Get the agent brain (singleton)."""
    rows = select("viral_agent_brain", "&limit=1&order=created_at.desc")
    return rows[0] if rows else {}


def save_brain(brain: dict) -> dict:
    """Save agent brain."""
    return upsert("viral_agent_brain", brain)


def save_topic(topic: dict) -> dict:
    return upsert("viral_topics", topic)


def save_angle(angle: dict) -> dict:
    return upsert("viral_angles", angle)


def save_hook(hook: dict) -> dict:
    return upsert("viral_hooks", hook)


def save_script(script: dict) -> dict:
    return upsert("viral_scripts", script)


def save_analytics(entry: dict) -> dict:
    return upsert("viral_analytics", entry)


def get_analytics(params: str = "") -> list:
    return select("viral_analytics", params)


def get_winners() -> list:
    return select("viral_analytics", "&is_winner=eq.true&order=created_at.desc")
