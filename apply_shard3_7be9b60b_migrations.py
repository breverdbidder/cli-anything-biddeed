#!/usr/bin/env python3
"""
Apply SHARD-3 dispatch 7be9b60b migrations to live Supabase database.
Counties: okeechobee (letter I) + okaloosa (letters C/D/E/I)

Uses Supabase Management API (SUPABASE_ACCESS_TOKEN) — same pattern as mgmt_sql.py.
Then runs the GIS enrichment Python script for okaloosa FC parcel linkage.

Usage:
  python3 apply_shard3_7be9b60b_migrations.py

Env:
  SUPABASE_ACCESS_TOKEN — required for SQL migration
  SUPABASE_URL — required for REST API calls
  SUPABASE_SERVICE_ROLE_KEY — required for REST API calls
"""
import os
import sys
import json
import httpx
from pathlib import Path

REF = "mocerqjnksmhcjzxrewo"
TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY", "")

MIGRATIONS = [
    "migrations/20260812_gold_standard_shard3_okeechobee_i_backfill.sql",
    "migrations/20260812_gold_standard_shard3_okaloosa_cde_i_backfill.sql",
]


def run_sql(query: str, label: str) -> bool:
    if not TOKEN:
        print(f"  SKIP {label}: no SUPABASE_ACCESS_TOKEN")
        return False
    h = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    r = httpx.post(
        f"https://api.supabase.com/v1/projects/{REF}/database/query",
        headers=h, json={"query": query}, timeout=120
    )
    ok = 200 <= r.status_code < 300
    print(f"  {'OK' if ok else 'FAIL'} {label}: HTTP {r.status_code}")
    if not ok:
        print(f"    Response: {r.text[:500]}")
    return ok


def evaluate_county(county: str) -> dict:
    if not SUPABASE_KEY:
        return {"error": "no SUPABASE_SERVICE_ROLE_KEY"}
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    r = httpx.post(
        f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
        headers=h, json={"p_county": county}, timeout=60
    )
    if not (200 <= r.status_code < 300):
        return {"error": f"HTTP {r.status_code}: {r.text[:200]}"}
    return r.json()


def main():
    print("=" * 60)
    print("SHARD-3 dispatch 7be9b60b — Migration Apply")
    print("Counties: okeechobee (I) + okaloosa (C/D/E/I)")
    print("=" * 60)

    # 1. Evaluate BEFORE
    print("\n--- BEFORE evaluation ---")
    for county in ["okeechobee", "okaloosa"]:
        ev = evaluate_county(county)
        if "error" in ev:
            print(f"  {county}: {ev['error']}")
        else:
            passed = sum(1 for k in "ABCDEFGHIJ" if k in ev and ev[k].get("pass"))
            print(f"  {county}: {passed}/10 pass")
            for k in "ABCDEFGHIJ":
                if k in ev:
                    s = "PASS" if ev[k].get("pass") else "FAIL"
                    print(f"    {k}: {s} {ev[k].get('detail','')}")

    # 2. Apply SQL migrations
    print("\n--- Applying SQL migrations ---")
    ok_count = 0
    for mig_path in MIGRATIONS:
        path = Path(mig_path)
        if not path.exists():
            print(f"  MISSING: {mig_path}")
            continue
        sql = path.read_text()
        if run_sql(sql, mig_path):
            ok_count += 1

    print(f"\n  {ok_count}/{len(MIGRATIONS)} migrations applied")

    # 3. Run the GIS enrichment Python script for okaloosa FC rows
    print("\n--- Running okaloosa GIS enrichment ---")
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "shard3_fix",
            Path("scripts/shard3_7be9b60b_okeechobee_okaloosa_fix.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.main()
    except Exception as exc:
        print(f"  GIS enrichment failed: {exc}")

    # 4. Evaluate AFTER
    print("\n--- AFTER evaluation ---")
    results = {}
    for county in ["okeechobee", "okaloosa"]:
        ev = evaluate_county(county)
        results[county] = ev
        if "error" in ev:
            print(f"  {county}: {ev['error']}")
        else:
            passed = sum(1 for k in "ABCDEFGHIJ" if k in ev and ev[k].get("pass"))
            print(f"  {county}: {passed}/10 pass")
            for k in "ABCDEFGHIJ":
                if k in ev:
                    s = "PASS" if ev[k].get("pass") else "FAIL"
                    print(f"    {k}: {s} {ev[k].get('detail','')}")

    # 5. Session close-out — write checkpoint to gold_standard_campaign
    print("\n--- Session close-out checkpoint ---")
    if SUPABASE_KEY:
        h = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        dispatch_id = "7be9b60b-f0fa-46e5-8890-af8cb0499ce4"
        for county, ev in results.items():
            if "error" in ev:
                continue
            criteria_passed = {
                k: ev[k].get("pass", False) for k in "ABCDEFGHIJ" if k in ev
            }
            criteria_total = sum(1 for v in criteria_passed.values() if v)
            payload = {
                "criteria_passed": json.dumps(criteria_passed),
                "criteria_total": criteria_total,
                "exit_reason": "timeout",
                "session_end_at": None,
            }
            r = httpx.patch(
                f"{SUPABASE_URL}/rest/v1/gold_standard_campaign",
                params={"dispatch_id": f"eq.{dispatch_id}"},
                headers=h, json=payload, timeout=30
            )
            print(f"  {county} checkpoint: HTTP {r.status_code}")
    else:
        print("  SKIP: no SUPABASE_SERVICE_ROLE_KEY")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
