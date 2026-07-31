#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-1 (clay/brevard/lee/pinellas), dispatch f763205f.
loop run 7622 execution script.

Applies fixes for brevard I + lee E/I + pinellas C/D/I in order:
1. Apply Lee zone-policy migration (mark CPD/CS/RS-2/MH-1/RS-1@912/RM-2@912 as not-applicable)
2. Apply Pinellas C/D parity backfill migration
3. Run Pinellas I fix script (ArcGIS lookup for incomplete cards)
4. Run Brevard AcclaimWeb retry script (45 unresolved cases)
5. Verify all counties

Usage: python3 scripts/gold_standard_shard1_run7622_execute.py
Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
"""
import os
import sys
import json
import subprocess
import urllib.request
import urllib.parse
from pathlib import Path

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
SCRIPT_DIR = Path(__file__).parent
MIGRATION_DIR = Path(__file__).parent.parent / "supabase" / "migrations"

if not SUPABASE_URL or not KEY:
    print("ERROR: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY required", flush=True)
    sys.exit(1)


def headers():
    return {
        "apikey": KEY,
        "Authorization": f"Bearer {KEY}",
        "Content-Type": "application/json",
    }


def mgmt_query(sql):
    """Run SQL via Supabase Management API."""
    import httpx
    ref = "mocerqjnksmhcjzxrewo"
    access_token = os.environ.get("SUPABASE_ACCESS_TOKEN")
    if not access_token:
        print("  WARN: SUPABASE_ACCESS_TOKEN not set, cannot use management API", flush=True)
        return None
    r = httpx.post(
        f"https://api.supabase.com/v1/projects/{ref}/database/query",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json={"query": sql},
        timeout=120,
    )
    return r.json()


def apply_migration_via_rpc(sql):
    """Apply SQL via PostgREST rpc/exec (may not exist) or management API."""
    # First try management API
    result = mgmt_query(sql)
    if result is not None:
        return result
    # Fallback: try REST rpc/exec
    body = json.dumps({"sql": sql}).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
        data=body,
        headers=headers(),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  rpc/exec_sql error: {e}", flush=True)
        return None


def evaluate_county(county):
    """Call pencil_dod_evaluate_county via RPC."""
    body = json.dumps({"p_county": county}).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
        data=body,
        headers=headers(),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  evaluate_county({county}) error: {e}", flush=True)
        return None


def print_eval(county, ev):
    if not ev:
        print(f"  {county}: EVAL FAILED", flush=True)
        return
    passed = [l for l in "ABCDEFGHIJ" if ev.get(l, {}).get("pass")]
    failed = [l for l in "ABCDEFGHIJ" if not ev.get(l, {}).get("pass")]
    score = len(passed)
    star = " ★ GOLD" if score == 10 else ""
    print(f"  {county}: {score}/10{star} PASS={passed} FAIL={failed}", flush=True)
    for l in "ABCDEFGHIJ":
        d = ev.get(l, {})
        print(
            f"    {l}: {'PASS' if d.get('pass') else 'FAIL'} "
            f"metric={d.get('metric')} detail={d.get('detail','')}",
            flush=True,
        )


def main():
    print("=== SHARD-1 run7622 execution ===", flush=True)
    print(f"SUPABASE_URL: {SUPABASE_URL}", flush=True)
    print("", flush=True)

    # ── BEFORE STATE ──────────────────────────────────────────────────────────
    print("=== BEFORE STATE ===", flush=True)
    for county in ["clay", "brevard", "lee", "pinellas"]:
        ev = evaluate_county(county)
        print_eval(county, ev)
    print("", flush=True)

    # ── STEP 1: Lee zone-policy migration ────────────────────────────────────
    print("=== STEP 1: Lee zone-policy migration ===", flush=True)
    migration_file = MIGRATION_DIR / "20260731_gold_standard_shard1_lee_zone_notapplicable_policy.sql"
    if not migration_file.exists():
        print(f"  ERROR: migration file not found: {migration_file}", flush=True)
    else:
        sql = migration_file.read_text()
        result = mgmt_query(sql)
        if result is not None:
            print(f"  Result: {json.dumps(result)[:500]}", flush=True)
        else:
            print("  Could not apply via management API; script must be applied manually", flush=True)

    print("  Lee after zone-policy:", flush=True)
    ev = evaluate_county("lee")
    print_eval("lee", ev)
    print("", flush=True)

    # ── STEP 2: Pinellas C/D parity migration ────────────────────────────────
    print("=== STEP 2: Pinellas C/D parity backfill ===", flush=True)
    migration_file2 = MIGRATION_DIR / "20260731_gold_standard_shard1_pinellas_cd_parity_backfill.sql"
    if not migration_file2.exists():
        print(f"  ERROR: migration file not found: {migration_file2}", flush=True)
    else:
        sql2 = migration_file2.read_text()
        result2 = mgmt_query(sql2)
        if result2 is not None:
            print(f"  Result: {json.dumps(result2)[:500]}", flush=True)
        else:
            print("  Could not apply via management API", flush=True)

    print("  Pinellas after C/D parity:", flush=True)
    ev = evaluate_county("pinellas")
    print_eval("pinellas", ev)
    print("", flush=True)

    # ── STEP 3: Pinellas I fix script ────────────────────────────────────────
    print("=== STEP 3: Pinellas I fix (ArcGIS) ===", flush=True)
    env = os.environ.copy()
    env["SUPABASE_URL"] = SUPABASE_URL
    env["SUPABASE_SERVICE_ROLE_KEY"] = KEY
    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "gold_standard_shard1_pinellas_i_cd_fix_run7622.py")],
        env=env,
        capture_output=False,
        timeout=900,
    )
    print(f"  Pinellas I script exit code: {result.returncode}", flush=True)

    print("  Pinellas after I fix:", flush=True)
    ev = evaluate_county("pinellas")
    print_eval("pinellas", ev)
    print("", flush=True)

    # ── STEP 4: Brevard AcclaimWeb retry ─────────────────────────────────────
    print("=== STEP 4: Brevard AcclaimWeb retry ===", flush=True)
    result4 = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "gold_standard_shard1_brevard_acclaim_retry_run7622.py")],
        env=env,
        capture_output=False,
        timeout=900,
    )
    print(f"  Brevard script exit code: {result4.returncode}", flush=True)

    print("  Brevard after AcclaimWeb retry:", flush=True)
    ev = evaluate_county("brevard")
    print_eval("brevard", ev)
    print("", flush=True)

    # ── AFTER STATE ───────────────────────────────────────────────────────────
    print("=== AFTER STATE ===", flush=True)
    after_evals = {}
    for county in ["clay", "brevard", "lee", "pinellas"]:
        ev = evaluate_county(county)
        after_evals[county] = ev
        print_eval(county, ev)
    print("", flush=True)

    print("=== SQL VERIFICATION ===", flush=True)
    print(json.dumps(after_evals, indent=2, default=str), flush=True)


if __name__ == "__main__":
    main()
