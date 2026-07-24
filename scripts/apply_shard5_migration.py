#!/usr/bin/env python3
"""
Apply shard5 run6148 migration via Supabase Management API.
Reads SUPABASE_ACCESS_TOKEN from env.
"""
import os
import sys
import json
import urllib.request
import urllib.error

PROJECT_REF = "mocerqjnksmhcjzxrewo"
TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY", "")
SQL_API_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
BASE = f"{SUPABASE_URL}/rest/v1"

MIGRATION_PATH = "supabase/migrations/20260724t_gold_standard_shard5_pinellas_madison_hamilton_run6148.sql"


def run_sql(sql, label="query"):
    if not TOKEN:
        print(f"  [{label}] SUPABASE_ACCESS_TOKEN not set — skipping", file=sys.stderr)
        return None
    body = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(SQL_API_URL, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            result = json.loads(r.read())
            print(f"  [{label}] OK: {json.dumps(result)[:300]}")
            return result
    except urllib.error.HTTPError as e:
        body_err = e.read().decode("utf-8", errors="replace")
        print(f"  [{label}] HTTP {e.code}: {body_err[:400]}", file=sys.stderr)
        return None


def sb_rpc(fn, payload):
    url = f"{BASE}/rpc/{fn}"
    data = json.dumps(payload).encode()
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  RPC {fn} error: {e}", file=sys.stderr)
        return {}


def main():
    print("=== Shard-5 run6148: Apply migration + evaluate ===")

    if not TOKEN and not SUPABASE_KEY:
        print("ERROR: No credentials available (SUPABASE_ACCESS_TOKEN or SUPABASE_SERVICE_ROLE_KEY)", file=sys.stderr)
        sys.exit(1)

    # BEFORE evaluations
    print("\n--- BEFORE ---")
    for county in ["pinellas", "madison", "hamilton"]:
        result = sb_rpc("pencil_dod_evaluate_county", {"p_county": county})
        print(f"{county}: {json.dumps(result)}")

    # Apply migration
    print(f"\n--- Applying migration: {MIGRATION_PATH} ---")
    with open(MIGRATION_PATH) as f:
        sql = f.read()

    result = run_sql(sql, label="migration")
    if result is None and TOKEN:
        print("Migration apply FAILED", file=sys.stderr)
        sys.exit(1)
    elif result is None:
        print("Skipped (no access token) — applying via REST API not possible for DDL", file=sys.stderr)

    # AFTER evaluations
    print("\n--- AFTER ---")
    for county in ["pinellas", "madison", "hamilton"]:
        result = sb_rpc("pencil_dod_evaluate_county", {"p_county": county})
        print(f"{county}: {json.dumps(result)}")

    print("\n=== Done ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
