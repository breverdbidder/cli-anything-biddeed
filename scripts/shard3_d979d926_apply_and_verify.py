#!/usr/bin/env python3
"""
shard3_d979d926_apply_and_verify.py
Apply the shard-3 migration and verify results for all 5 counties.
Runs pencil_dod_evaluate_county before and after.

Usage:
  SUPABASE_KEY=... SUPABASE_MGMT_TOKEN=... python3 scripts/shard3_d979d926_apply_and_verify.py
"""

import os
import sys
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_SERVICE_ROLE")
    or os.environ.get("SUPABASE_KEY")
    or ""
)
SUPABASE_MGMT_TOKEN = os.environ.get("SUPABASE_MGMT_TOKEN", "")
DISPATCH_ID = "d979d926-2a6f-426c-b21a-23a40181c505"
COUNTIES = ["marion", "hamilton", "union", "columbia", "taylor"]

if not SUPABASE_KEY:
    print("ERROR: SUPABASE_KEY required", file=sys.stderr)
    sys.exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}
MGMT_URL = "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"
MGMT_HEADERS = {
    "Authorization": f"Bearer {SUPABASE_MGMT_TOKEN}",
    "Content-Type": "application/json",
}

NOW = datetime.now(timezone.utc)


def log(msg, level="INFO"):
    print(f"[{NOW.isoformat()}] {level}: {msg}", flush=True)


def evaluate_county(county):
    r = httpx.post(
        f"{BASE}/rpc/pencil_dod_evaluate_county",
        headers=HEADERS,
        json={"p_county": county},
        timeout=60,
    )
    if r.status_code == 200:
        result = r.json()
        if isinstance(result, list) and result:
            result = result[0]
        return result
    log(f"pencil_dod_evaluate_county('{county}'): HTTP {r.status_code}", "ERROR")
    return {}


def apply_migration(sql_path):
    """Apply a SQL migration file via Management API."""
    if not SUPABASE_MGMT_TOKEN:
        log("SUPABASE_MGMT_TOKEN not set — cannot apply migration via Management API", "WARN")
        log("To apply manually: run the SQL in migrations/20260802_gold_standard_shard3_d979d926_*.sql", "WARN")
        return False

    sql = Path(sql_path).read_text()
    log(f"Applying migration: {sql_path} ({len(sql)} chars)")

    # Split on semicolons and run each statement
    statements = [s.strip() for s in sql.split(";") if s.strip() and not s.strip().startswith("--")]
    log(f"Running {len(statements)} SQL statements")

    for i, stmt in enumerate(statements):
        if not stmt:
            continue
        r = httpx.post(
            MGMT_URL,
            headers=MGMT_HEADERS,
            json={"query": stmt + ";"},
            timeout=120,
        )
        if r.status_code in (200, 201):
            pass
        else:
            log(f"Statement {i+1} error: HTTP {r.status_code}: {r.text[:200]}", "WARN")
        time.sleep(0.1)

    log(f"Migration applied: {sql_path}")
    return True


def print_evaluation(county, result, label=""):
    if not result:
        log(f"{county} {label}: no result", "WARN")
        return
    pass_count = sum(1 for L in "ABCDEFGHIJ" if result.get(L, {}).get("pass", False))
    pass_letters = [L for L in "ABCDEFGHIJ" if result.get(L, {}).get("pass", False)]
    fail_letters = [L for L in "ABCDEFGHIJ" if not result.get(L, {}).get("pass", False)]
    total = result.get("auctions_total", "?")
    log(f"{county} {label}: {pass_count}/10 (total={total}) PASS={pass_letters} FAIL={fail_letters}")
    for L in "ABCDEFGHIJ":
        item = result.get(L, {})
        log(f"  {L}: {'PASS' if item.get('pass') else 'FAIL'} metric={item.get('metric')} ({item.get('detail','')})")


def main():
    log("=" * 60)
    log(f"SHARD-3 APPLY+VERIFY — dispatch {DISPATCH_ID}")
    log("=" * 60)

    # BEFORE
    log("\n--- BEFORE STATE ---")
    before = {}
    for county in COUNTIES:
        before[county] = evaluate_county(county)
        print_evaluation(county, before[county], "BEFORE")
        time.sleep(0.5)

    # Apply migration
    migration_path = Path(__file__).parent.parent / "migrations" / "20260802_gold_standard_shard3_d979d926_marion_hamilton_union_columbia_taylor.sql"
    if migration_path.exists():
        apply_migration(str(migration_path))
    else:
        log(f"Migration not found: {migration_path}", "ERROR")

    time.sleep(2)

    # AFTER
    log("\n--- AFTER STATE ---")
    after = {}
    for county in COUNTIES:
        after[county] = evaluate_county(county)
        print_evaluation(county, after[county], "AFTER")
        time.sleep(0.5)

    # Summary
    log("\n=== SESSION SUMMARY ===")
    for county in COUNTIES:
        b = before.get(county, {})
        a = after.get(county, {})
        b_pass = sum(1 for L in "ABCDEFGHIJ" if b.get(L, {}).get("pass", False))
        a_pass = sum(1 for L in "ABCDEFGHIJ" if a.get(L, {}).get("pass", False))
        moved = [
            L for L in "ABCDEFGHIJ"
            if not b.get(L, {}).get("pass", False) and a.get(L, {}).get("pass", False)
        ]
        log(f"  {county}: {b_pass}/10 → {a_pass}/10" + (f" (NEW PASS: {moved})" if moved else " (no change)"))

    log("\n### SQL VERIFICATION")
    log("Before:")
    for county in COUNTIES:
        log(f"  {county}: {json.dumps(before.get(county, {}))}")
    log("After:")
    for county in COUNTIES:
        log(f"  {county}: {json.dumps(after.get(county, {}))}")


if __name__ == "__main__":
    main()
