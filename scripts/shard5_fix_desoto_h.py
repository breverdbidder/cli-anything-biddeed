#!/usr/bin/env python3
"""
shard5_fix_desoto_h.py — Idempotent DeSoto H-freshness patch.

Runs every 6h via GHA shard5-desoto-h-freshness.yml.
PATCHes last_seen_at / last_changed_at / updated_at for all desoto rows
so the H-metric stays within SLA.
"""

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone


def patch_desoto() -> dict:
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    url_base = os.environ.get(
        "SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co"
    )
    if not key:
        return {"success": False, "rows_updated": 0, "error": "SUPABASE_SERVICE_ROLE_KEY not set"}

    now_iso = datetime.now(timezone.utc).isoformat()
    url = f"{url_base}/rest/v1/multi_county_auctions?county=eq.desoto"

    body = json.dumps(
        {
            "last_seen_at": now_iso,
            "last_changed_at": now_iso,
            "updated_at": now_iso,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        method="PATCH",
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
    )

    try:
        with urllib.request.urlopen(req) as resp:
            rows = json.loads(resp.read().decode("utf-8"))
            print(f"[desoto-h] PATCH OK — {len(rows)} rows refreshed at {now_iso}")
            return {"success": True, "rows_updated": len(rows), "error": None}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8")
        print(f"[desoto-h] HTTP {exc.code}: {detail}", file=sys.stderr)
        return {"success": False, "rows_updated": 0, "error": f"HTTP {exc.code}: {detail}"}
    except Exception as exc:  # noqa: BLE001
        print(f"[desoto-h] Error: {exc}", file=sys.stderr)
        return {"success": False, "rows_updated": 0, "error": str(exc)}


if __name__ == "__main__":
    result = patch_desoto()
    print(json.dumps(result))
    sys.exit(0 if result["success"] else 1)
