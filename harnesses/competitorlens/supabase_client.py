"""
CompetitorLens — Supabase Client
Handles competitor_analyses and ux_pattern_library tables.
Uses REST API directly (no SDK dependency).
"""

import json
import os
import urllib.request
import urllib.error

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", os.environ.get("SUPABASE_SERVICE_ROLE_KEY", ""))


def _request(method: str, table: str, data=None, params: str = "") -> dict | list:
    """Generic Supabase REST request."""
    if not SUPABASE_KEY:
        return {"error": "SUPABASE_SERVICE_KEY not set"}

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


def save_analysis(record: dict) -> dict:
    """
    Insert a new competitor analysis record.
    Required fields: competitor_name, source_url, component_type
    """
    result = _request("POST", "competitor_analyses", record)
    if isinstance(result, list) and result:
        return result[0]
    return result


def update_analysis(analysis_id: str, updates: dict) -> dict:
    """Update an existing analysis by ID."""
    result = _request(
        "PATCH", "competitor_analyses", updates,
        f"?id=eq.{analysis_id}"
    )
    if isinstance(result, list) and result:
        return result[0]
    return result


def get_analysis(analysis_id: str) -> dict:
    """Fetch a single analysis by ID."""
    result = _request("GET", "competitor_analyses", params=f"?id=eq.{analysis_id}&select=*")
    if isinstance(result, list) and result:
        return result[0]
    return {"error": "Not found"}


def list_analyses(competitor: str = None, limit: int = 20) -> list:
    """List analyses, optionally filtered by competitor."""
    params = f"?select=*&order=created_at.desc&limit={limit}"
    if competitor:
        params += f"&competitor_name=eq.{urllib.parse.quote(competitor)}"
    result = _request("GET", "competitor_analyses", params=params)
    return result if isinstance(result, list) else []


def save_ux_pattern(pattern: dict) -> dict:
    """
    Save a UX pattern to the library.
    Required fields: pattern_name, source_competitor, description
    """
    result = _request("POST", "ux_pattern_library", pattern)
    if isinstance(result, list) and result:
        return result[0]
    return result


def get_pattern_library(limit: int = 50) -> list:
    """Get all patterns from the UX library."""
    result = _request(
        "GET", "ux_pattern_library",
        params=f"?select=*&order=reuse_count.desc&limit={limit}"
    )
    return result if isinstance(result, list) else []


def increment_pattern_reuse(pattern_id: str) -> dict:
    """Increment reuse_count for a pattern."""
    # Fetch current count first
    current = _request("GET", "ux_pattern_library", params=f"?id=eq.{pattern_id}&select=reuse_count")
    if isinstance(current, list) and current:
        new_count = (current[0].get("reuse_count") or 0) + 1
        return _request("PATCH", "ux_pattern_library", {"reuse_count": new_count}, f"?id=eq.{pattern_id}")
    return {"error": "Pattern not found"}


# Import urllib.parse for list_analyses
import urllib.parse
