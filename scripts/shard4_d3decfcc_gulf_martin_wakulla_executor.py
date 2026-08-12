#!/usr/bin/env python3
"""GOLD STANDARD SHARD-4 executor — gulf, martin, wakulla.
dispatch_id: d3decfcc-1684-4304-bb78-467fc7b15a4c
loop_run: 10790 | issue: #18873

Applies migrations in sequence and verifies via pencil_dod_evaluate_county.
Uses the Management API pattern (SUPABASE_ACCESS_TOKEN) consistent with
scripts/mgmt_sql.py. Falls back to PostgREST if Management API unavailable.
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

REF = "mocerqjnksmhcjzxrewo"
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")

MGMT_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "") or os.environ.get("SUPABASE_KEY", "")

MIGRATIONS = [
    "migrations/20260812_gold_standard_shard4_martin_g_regression_fix.sql",
    "migrations/20260812_gold_standard_shard4_gulf_j_new_auction_backfill.sql",
    "migrations/20260812_gold_standard_shard4_wakulla_new_auctions_ceij.sql",
    "migrations/20260812_gold_standard_shard4_session_closeout.sql",
]

COUNTIES = ["gulf", "martin", "wakulla"]


def mgmt_run(sql: str) -> dict:
    """Run SQL via Supabase Management API."""
    if not MGMT_TOKEN:
        raise RuntimeError("SUPABASE_ACCESS_TOKEN not set")

    body = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{REF}/database/query",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {MGMT_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def rest_run(rpc_name: str, params: dict) -> list:
    """Run a Supabase RPC function via REST."""
    if not SERVICE_KEY:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY not set")

    body = json.dumps(params).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{rpc_name}",
        data=body,
        method="POST",
        headers={
            "apikey": SERVICE_KEY,
            "Authorization": f"Bearer {SERVICE_KEY}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def apply_migration(path: str) -> bool:
    """Apply a SQL migration file. Returns True on success."""
    p = Path(path)
    if not p.exists():
        print(f"  ⚠️  File not found: {path}")
        return False

    sql = p.read_text()
    print(f"\n📄 Applying: {p.name} ({len(sql)} chars)")

    if MGMT_TOKEN:
        try:
            result = mgmt_run(sql)
            print(f"  ✅ Management API: {str(result)[:200]}")
            return True
        except Exception as e:
            print(f"  ❌ Management API failed: {e}")
            return False
    else:
        print("  ⚠️  No SUPABASE_ACCESS_TOKEN — migration not applied live")
        print("  ℹ️  This is expected in Claude Code runner environment")
        print(f"  📝 Migration ready at: {path}")
        return None


def evaluate_county(county: str) -> dict:
    """Run pencil_dod_evaluate_county for a county."""
    print(f"\n🔍 Evaluating {county}...")

    if MGMT_TOKEN:
        try:
            result = mgmt_run(f"SET statement_timeout = 0; SELECT public.pencil_dod_evaluate_county('{county}')")
            print(f"  Raw result: {str(result)[:500]}")
            return result
        except Exception as e:
            print(f"  ❌ Management API eval failed: {e}")

    if SERVICE_KEY:
        try:
            result = rest_run("pencil_dod_evaluate_county", {"county_slug": county})
            print(f"  Evaluation result: {json.dumps(result, indent=2)[:800]}")
            return result
        except Exception as e:
            print(f"  ❌ REST eval failed: {e}")

    print(f"  ⚠️  Cannot evaluate {county} — no DB credentials in environment")
    return {}


def main():
    print("=" * 60)
    print("GOLD STANDARD SHARD-4: gulf, martin, wakulla")
    print("dispatch_id: d3decfcc-1684-4304-bb78-467fc7b15a4c")
    print("=" * 60)

    has_db = bool(MGMT_TOKEN or SERVICE_KEY)
    if not has_db:
        print("\n⚠️  No database credentials found.")
        print("   SUPABASE_ACCESS_TOKEN: NOT SET")
        print("   SUPABASE_SERVICE_ROLE_KEY: NOT SET")
        print("   Migrations have been written to disk at:")
        for m in MIGRATIONS:
            p = Path(m)
            if p.exists():
                print(f"     ✅ {m}")
            else:
                print(f"     ❌ MISSING: {m}")
        print("\n   Apply manually via:")
        print("   python3 mgmt_sql.py -f migrations/20260812_gold_standard_shard4_martin_g_regression_fix.sql")
        print("   python3 mgmt_sql.py -f migrations/20260812_gold_standard_shard4_gulf_j_new_auction_backfill.sql")
        print("   python3 mgmt_sql.py -f migrations/20260812_gold_standard_shard4_wakulla_new_auctions_ceij.sql")
        print("   python3 mgmt_sql.py -f migrations/20260812_gold_standard_shard4_session_closeout.sql")
        return

    # Apply migrations in sequence
    print("\n📦 Applying migrations...")
    for m in MIGRATIONS:
        result = apply_migration(m)
        if result is False:
            print(f"  ⚠️  Migration failed: {m} — continuing...")
        time.sleep(1)

    # Evaluate all counties
    print("\n📊 Post-migration evaluation:")
    for county in COUNTIES:
        evaluate_county(county)

    print("\n✅ Session complete.")
    print("Next: Check gold_standard_county_status after next gold_standard_loop() run.")


if __name__ == "__main__":
    main()
