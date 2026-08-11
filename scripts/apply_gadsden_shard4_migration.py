#!/usr/bin/env python3
"""
Apply the gadsden shard-4 E/C/I/J migration via Supabase Management API.
dispatch_id: cefc3fb1-5729-4e6e-9bcd-1eb696cdc9d3
loop_run: 10589 | issue: #18818

Usage:
  python3 scripts/apply_gadsden_shard4_migration.py
  python3 scripts/apply_gadsden_shard4_migration.py --dry-run
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

DISPATCH_ID = "cefc3fb1-5729-4e6e-9bcd-1eb696cdc9d3"
MIGRATION_FILE = "migrations/20260811_gold_standard_shard4_gadsden_cefc3fb1_ecij_fix.sql"
REF = "mocerqjnksmhcjzxrewo"
COUNTY = "gadsden"

DRY_RUN = "--dry-run" in sys.argv


def mgmt_sql(sql: str, token: str, timeout: int = 300) -> tuple[int, object]:
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{REF}/database/query",
        data=json.dumps({"query": sql}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read())


def evaluate_county(token: str) -> dict:
    sql = f"SELECT public.pencil_dod_evaluate_county('{COUNTY}');"
    try:
        status, result = mgmt_sql(sql, token)
        if status == 200 and result:
            # Result is [{pencil_dod_evaluate_county: {...}}]
            row = result[0]
            ev_str = list(row.values())[0]
            if isinstance(ev_str, str):
                return json.loads(ev_str)
            elif isinstance(ev_str, dict):
                return ev_str
    except Exception as exc:
        print(f"[WARN] evaluate failed: {exc}")
    return {}


def print_eval(ev: dict, label: str) -> None:
    passed = [l for l in "ABCDEFGHIJ" if ev.get(l, {}).get("pass")]
    failed = [l for l in "ABCDEFGHIJ" if not ev.get(l, {}).get("pass")]
    score = len(passed)
    print(f"\n### {label}")
    print(f"  {COUNTY.upper()}: {score}/10  PASS={passed}  FAIL={failed}")
    for l in "ABCDEFGHIJ":
        ld = ev.get(l, {})
        status = "PASS ✅" if ld.get("pass") else "FAIL ❌"
        print(f"  {l}: {status} metric={ld.get('metric')} | {ld.get('detail', '')}")
    print(f"\n  JSON: {json.dumps(ev, default=str)}")


def main():
    token = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
    if not token:
        print("ERROR: SUPABASE_ACCESS_TOKEN not set")
        sys.exit(1)

    # Read migration file
    migration_path = Path(__file__).parent.parent / MIGRATION_FILE
    if not migration_path.exists():
        print(f"ERROR: Migration file not found: {migration_path}")
        sys.exit(1)

    migration_sql = migration_path.read_text()
    print(f"Migration file: {migration_path.name} ({len(migration_sql)} chars)")

    # BEFORE evaluation
    print("\n[1/4] Getting BEFORE evaluation...")
    ev_before = evaluate_county(token)
    print_eval(ev_before, "BEFORE (pre-migration)")

    if DRY_RUN:
        print("\n[DRY RUN] Skipping migration apply.")
        return

    # Apply migration
    print("\n[2/4] Applying migration...")
    print(f"  dispatch_id: {DISPATCH_ID}")
    try:
        status, result = mgmt_sql(migration_sql, token, timeout=300)
        print(f"  Migration HTTP {status}")
        if status != 200:
            print(f"  ERROR: {json.dumps(result, default=str)[:500]}")
            sys.exit(1)
        print(f"  Migration OK: {json.dumps(result, default=str)[:300]}")
    except Exception as exc:
        print(f"  FAIL-LOUD: migration failed: {exc}")
        sys.exit(1)

    # AFTER evaluation
    print("\n[3/4] Getting AFTER evaluation...")
    ev_after = evaluate_county(token)
    print_eval(ev_after, "AFTER (post-migration)")

    # Summary
    print("\n[4/4] Summary")
    before_score = sum(1 for l in "ABCDEFGHIJ" if ev_before.get(l, {}).get("pass"))
    after_score = sum(1 for l in "ABCDEFGHIJ" if ev_after.get(l, {}).get("pass"))
    print(f"  Score: {before_score}/10 → {after_score}/10")

    for letter in ["C", "E", "I", "J"]:
        bm = ev_before.get(letter, {}).get("metric")
        am = ev_after.get(letter, {}).get("metric")
        bp = ev_before.get(letter, {}).get("pass")
        ap = ev_after.get(letter, {}).get("pass")
        moved = "✅ MOVED" if am != bm else "⚠️  UNCHANGED"
        print(f"  {letter}: {bm} → {am} (pass: {bp} → {ap}) {moved}")

    print(f"\n### SQL VERIFICATION")
    print(f"```sql")
    print(f"SELECT public.pencil_dod_evaluate_county('gadsden');")
    print(f"-- BEFORE: {json.dumps(ev_before, default=str)}")
    print(f"-- AFTER:  {json.dumps(ev_after, default=str)}")
    print(f"```")
    print(f"\ndispatch_id: {DISPATCH_ID}")


if __name__ == "__main__":
    main()
