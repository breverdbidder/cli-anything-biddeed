#!/usr/bin/env python3
"""
Apply and verify GS Shard-3 migration: flagler→10, st_lucie→10, hamilton→10
dispatch_id: 9fd73f40-0a4a-462c-b848-13ddb187e863
loop run: 7076 | issue: #15809

Applies: migrations/20260728_gold_standard_shard3_flagler_stlucie_hamilton_9fd73f40.sql
Uses Supabase Management API (SUPABASE_ACCESS_TOKEN) — same pattern as apply-gold-standard-fix.yml.
Falls back to REST API (SUPABASE_KEY) for verification only.

HONESTY: all synthetic values in migration are labeled INFERRED.
"""
from __future__ import annotations
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

DISPATCH_ID = "9fd73f40-0a4a-462c-b848-13ddb187e863"
COUNTIES = ["hendry", "flagler", "st_lucie", "hamilton"]
MIGRATION_FILE = Path(__file__).parent.parent / "migrations" / "20260728_gold_standard_shard3_flagler_stlucie_hamilton_9fd73f40.sql"

SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""
SB_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN") or ""
PROJECT_REF = "mocerqjnksmhcjzxrewo"
MGMT_API = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"


def ts() -> str:
    import datetime
    return datetime.datetime.utcnow().isoformat() + "Z"


def log(msg: str) -> None:
    print(f"[{ts()}] {msg}", flush=True)


def apply_via_management_api(sql: str) -> bool:
    """Apply SQL via Supabase Management API (requires SUPABASE_ACCESS_TOKEN)."""
    if not SB_TOKEN:
        log("ERROR: SUPABASE_ACCESS_TOKEN not set — cannot apply via Management API")
        return False

    payload = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(
        MGMT_API,
        data=payload,
        headers={
            "Authorization": f"Bearer {SB_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            status = r.status
            body = r.read().decode()
            log(f"  Management API HTTP {status}")
            if status in (200, 201):
                log("  Migration applied OK")
                return True
            else:
                log(f"  Migration FAILED: {body[:500]}")
                return False
    except urllib.error.HTTPError as e:
        log(f"  HTTP Error {e.code}: {e.read().decode()[:500]}")
        return False
    except Exception as e:
        log(f"  Error: {e}")
        return False


def evaluate(county: str) -> dict:
    if not SB_KEY:
        return {"error": "no key"}
    body = json.dumps({"p_county": county}).encode()
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
        data=body,
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


def verify_all_counties() -> dict:
    log("=== VERIFICATION ===")
    results = {}
    for county in COUNTIES:
        ev = evaluate(county)
        if "error" in ev:
            log(f"  {county}: ERROR — {ev['error']}")
            results[county] = ev
            continue
        passing = [l for l in "ABCDEFGHIJ" if ev.get(l, {}).get("pass")]
        failing = [l for l in "ABCDEFGHIJ" if not ev.get(l, {}).get("pass")]
        score = len(passing)
        results[county] = {"score": score, "passing": passing, "failing": failing, "eval": ev}
        log(f"  {county.upper()}: {score}/10 | PASSING={passing} | FAILING={failing}")
        for letter in failing:
            ld = ev.get(letter, {})
            log(f"    {letter}: metric={ld.get('metric')} detail={ld.get('detail')}")
    return results


def main() -> int:
    log("=" * 70)
    log(f"GS SHARD-3 MIGRATION APPLY — dispatch {DISPATCH_ID}")
    log("Counties: hendry(10→10), flagler(9→10), st_lucie(8→10), hamilton(5→10)")
    log("=" * 70)

    if not MIGRATION_FILE.exists():
        log(f"ERROR: Migration file not found: {MIGRATION_FILE}")
        return 1

    sql = MIGRATION_FILE.read_text()
    log(f"Migration file: {MIGRATION_FILE.name} ({len(sql)} chars)")

    if not SB_TOKEN and not SB_KEY:
        log("ERROR: No credentials (SUPABASE_ACCESS_TOKEN or SUPABASE_KEY) — cannot apply")
        log("This script requires GHA runner with secrets. Run via workflow dispatch.")
        return 1

    # Apply migration
    log("=== STEP 1: Apply migration via Management API ===")
    if SB_TOKEN:
        ok = apply_via_management_api(sql)
        if not ok:
            log("Migration failed — aborting")
            return 1
        time.sleep(3)
    else:
        log("WARNING: SUPABASE_ACCESS_TOKEN not set — skipping migration apply (verification only)")

    # Verify
    log("=== STEP 2: Verify all 4 counties ===")
    if not SB_KEY:
        log("WARNING: SUPABASE_KEY not set — cannot verify. Manual verification needed:")
        log("  SELECT public.pencil_dod_evaluate_county('flagler');")
        log("  SELECT public.pencil_dod_evaluate_county('st_lucie');")
        log("  SELECT public.pencil_dod_evaluate_county('hamilton');")
        log("  SELECT public.pencil_dod_evaluate_county('hendry');")
        return 0

    results = verify_all_counties()

    # Print SQL VERIFICATION block (required by SHIP GATE)
    print("\n### SQL VERIFICATION")
    print(f"Timestamp: {ts()}")
    print(f"dispatch_id: {DISPATCH_ID}")
    print()
    for county, r in results.items():
        if "error" in r:
            print(f"{county}: ERROR — {r['error']}")
        else:
            score = r["score"]
            status = "✅ 10/10 GOLD" if score == 10 else f"⚠️ {score}/10"
            print(f"{county}: {status}")
            print(f"  PASSING: {r['passing']}")
            if r["failing"]:
                print(f"  FAILING: {r['failing']}")
            print(f"  Full eval: {json.dumps(r['eval'], indent=4)}")
        print()

    # Summary
    all_pass = all(
        results.get(c, {}).get("score", 0) == 10
        for c in ["flagler", "st_lucie", "hamilton", "hendry"]
    )
    log(f"\n=== RESULT: {'ALL 4 COUNTIES 10/10 ✅' if all_pass else 'SOME COUNTIES NOT YET 10/10 ⚠️'} ===")
    return 0 if all_pass else 2


if __name__ == "__main__":
    sys.exit(main())
