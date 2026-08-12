#!/usr/bin/env python3
"""
Apply SHARD-3 migration for alachua/gadsden/sumter/holmes (dispatch b57474e3)
Uses Supabase Management API (SUPABASE_ACCESS_TOKEN) — same as mgmt_sql.py
"""
import os
import sys
import json
import time

try:
    import httpx
except ImportError:
    print("httpx not available, trying requests...")
    try:
        import requests as httpx_compat
        class httpx:
            @staticmethod
            def post(url, **kwargs):
                return httpx_compat.post(url, **kwargs)
    except ImportError:
        print("Neither httpx nor requests available.")
        sys.exit(1)

REF = "mocerqjnksmhcjzxrewo"
TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")

if not TOKEN:
    print("SUPABASE_ACCESS_TOKEN not set — cannot apply migration.")
    print("Migration file committed to repo: migrations/20260812_gold_standard_shard3_alachua_gadsden_sumter_holmes_eij_fix.sql")
    print("Apply manually: python3 mgmt_sql.py -f migrations/20260812_gold_standard_shard3_alachua_gadsden_sumter_holmes_eij_fix.sql")
    sys.exit(0)


def run_sql(query: str, label: str = ""):
    h = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    r = httpx.post(
        f"https://api.supabase.com/v1/projects/{REF}/database/query",
        headers=h,
        json={"query": query},
        timeout=300
    )
    status = r.status_code
    try:
        result = r.json()
    except Exception:
        result = r.text
    if label:
        print(f"\n=== {label} ===")
    print(f"STATUS {status}")
    if isinstance(result, list):
        print(f"Rows: {len(result)}")
        if result:
            print(json.dumps(result[:5], indent=2, default=str))
    else:
        print(json.dumps(result, indent=2, default=str)[:4000])
    return status, result


def main():
    migration_path = os.path.join(
        os.path.dirname(__file__),
        "migrations",
        "20260812_gold_standard_shard3_alachua_gadsden_sumter_holmes_eij_fix.sql"
    )

    with open(migration_path) as f:
        migration_sql = f.read()

    print(f"Migration size: {len(migration_sql)} chars")
    print("Applying migration in batches (split on semicolons)...")

    # Split into statements
    # The file has large multi-statement blocks — send it as one big query
    status, result = run_sql(migration_sql, "FULL MIGRATION")

    if status != 200:
        print("Migration failed — checking individual county evaluations")
    else:
        print("\nMigration applied. Running verification...")
        time.sleep(2)

    # Run per-county evaluations
    for county in ['alachua', 'gadsden', 'sumter', 'holmes']:
        status, result = run_sql(
            f"SELECT public.pencil_dod_evaluate_county('{county}');",
            f"EVALUATE {county.upper()}"
        )


if __name__ == "__main__":
    main()
