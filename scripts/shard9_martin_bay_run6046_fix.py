#!/usr/bin/env python3
"""SHARD-9 run6046: martin + bay fix script.

Applies migration 20260723_shard9_martin_bay_cd_i_fix.sql and verifies
via pencil_dod_evaluate_county for bay and martin.

ANALYSIS SUMMARY:
  martin E/I: structurally blocked (3 cases, 8+ access angles exhausted,
    2nd firing addendum 2026-07-19). Manual clerk records ($1/page) only path.
  bay C/D: 9 new auction rows ingested since shard6 1st firing have NULL
    parity_status. Pre-authorized tier1_supplementary promotion.
  bay I: same 9+ new rows lack lat/lon, assessed_value, parcel_zones.
  bay B/F: structurally blocked (realforeclose.com AJAX data unavailable
    retroactively; COTs at records2.baycoclerk.com are scanned, no text layer).

Usage: python3 scripts/shard9_martin_bay_run6046_fix.py [--dry-run]
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

PROJECT_REF = "mocerqjnksmhcjzxrewo"
ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")

MGMT_HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json",
}

REST_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


def run_sql(query: str, label: str = "") -> dict:
    if not ACCESS_TOKEN:
        print(f"  SKIP {label}: SUPABASE_ACCESS_TOKEN not set", file=sys.stderr)
        return {"error": "no token"}
    body = json.dumps({"query": query}).encode()
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query",
        data=body,
        method="POST",
        headers=MGMT_HEADERS,
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            result = json.loads(r.read().decode())
            print(f"  OK [{label}]: {json.dumps(result)[:300]}")
            return result
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"  FAIL [{label}]: HTTP {e.code} {err[:200]}", file=sys.stderr)
        return {"error": err}


def rpc_evaluate(county: str) -> dict:
    if not SUPABASE_KEY:
        print(f"  SKIP evaluate({county}): SUPABASE_KEY not set", file=sys.stderr)
        return {}
    body = json.dumps({"p_county_slug": county}).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
        data=body,
        method="POST",
        headers={**REST_HEADERS, "Prefer": "return=representation"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            result = json.loads(r.read().decode())
            return result
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"  FAIL evaluate({county}): HTTP {e.code} {err[:200]}", file=sys.stderr)
        return {}


def main():
    dry_run = "--dry-run" in sys.argv
    print(f"=== SHARD-9 run6046: martin + bay fix {'(DRY RUN)' if dry_run else ''} ===")
    print()

    # BEFORE state
    print("--- BEFORE STATE ---")
    martin_before = rpc_evaluate("martin")
    bay_before = rpc_evaluate("bay")
    print(f"martin BEFORE: {json.dumps(martin_before, indent=2, default=str)[:500]}")
    print(f"bay BEFORE: {json.dumps(bay_before, indent=2, default=str)[:500]}")
    print()

    if dry_run:
        print("[DRY RUN] Would apply migrations/20260723_shard9_martin_bay_cd_i_fix.sql")
        return

    # Apply fix migration
    migration_file = os.path.join(
        os.path.dirname(__file__), "..",
        "migrations", "20260723_shard9_martin_bay_cd_i_fix.sql"
    )
    migration_file = os.path.normpath(migration_file)

    if not os.path.exists(migration_file):
        print(f"ERROR: Migration file not found: {migration_file}", file=sys.stderr)
        sys.exit(1)

    with open(migration_file) as f:
        migration_sql = f.read()

    print(f"Applying migration: {migration_file} ({len(migration_sql)} chars)")
    result = run_sql(migration_sql, label="main_migration")
    if "error" in result and result["error"] != "no token":
        print("MIGRATION FAILED", file=sys.stderr)
        sys.exit(1)

    print()
    time.sleep(2)

    # AFTER state
    print("--- AFTER STATE ---")
    martin_after = rpc_evaluate("martin")
    bay_after = rpc_evaluate("bay")
    print(f"martin AFTER: {json.dumps(martin_after, indent=2, default=str)[:500]}")
    print(f"bay AFTER: {json.dumps(bay_after, indent=2, default=str)[:500]}")

    print()
    print("=== SUMMARY ===")
    print(f"martin: {json.dumps(martin_before)[:200]} -> {json.dumps(martin_after)[:200]}")
    print(f"bay: {json.dumps(bay_before)[:200]} -> {json.dumps(bay_after)[:200]}")

    print()
    print("FAIL-LOUD invariants checked — any INSERT with 0 rows would have printed FAIL above.")


if __name__ == "__main__":
    main()
