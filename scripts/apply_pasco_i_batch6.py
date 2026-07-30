#!/usr/bin/env python3
"""Apply pasco I batch6 migration — dispatch c72dbd55, run7519.

Applies supabase/migrations/20260730_gold_standard_shard5_pasco_i_card_completeness_batch6.sql
to the live Supabase project, then verifies via pencil_dod_evaluate_county('pasco').

Usage:
    python3 scripts/apply_pasco_i_batch6.py

Requires:
    SUPABASE_URL + (SUPABASE_SERVICE_ROLE_KEY | SUPABASE_KEY | SUPABASE_SERVICE_KEY)
    or PGPASSWORD + DB_POOLER for direct psql connection
"""
import os
import sys
import json
import time
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
)

MIGRATION_FILE = Path(__file__).parent.parent / "supabase" / "migrations" / \
    "20260730_gold_standard_shard5_pasco_i_card_completeness_batch6.sql"

COUNTY = "pasco"


def rest_rpc(fn, body):
    url = f"{SUPABASE_URL}/rest/v1/rpc/{fn}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def evaluate_county():
    try:
        result = rest_rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
        if isinstance(result, list):
            result = result[0] if result else {}
        return result
    except Exception as e:
        print(f"[WARN] pencil_dod_evaluate_county failed: {e}")
        return None


def apply_via_rpc_exec(sql):
    """Apply SQL via Supabase RPC exec function (if available)."""
    try:
        result = rest_rpc("exec", {"query": sql})
        return True, result
    except Exception as e:
        return False, str(e)


def apply_via_management_api(sql):
    """Apply SQL via Supabase Management API (requires service role key)."""
    project_ref = "mocerqjnksmhcjzxrewo"
    url = f"https://api.supabase.com/v1/projects/{project_ref}/database/query"
    data = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return True, json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return False, f"HTTP {e.code}: {body[:500]}"
    except Exception as e:
        return False, str(e)


def apply_sql_statements_individually(sql):
    """Split SQL into statements and apply each via REST/RPC."""
    statements = [s.strip() for s in sql.split(";") if s.strip() and not s.strip().startswith("--")]
    print(f"  [{len(statements)} statements to apply]")
    results = []
    for i, stmt in enumerate(statements):
        if not stmt:
            continue
        try:
            ok, res = apply_via_rpc_exec(stmt + ";")
            results.append({"stmt_idx": i, "ok": ok, "result": str(res)[:200]})
            status = "OK" if ok else "FAIL"
            print(f"  Statement {i+1}/{len(statements)}: {status}")
        except Exception as e:
            results.append({"stmt_idx": i, "ok": False, "result": str(e)[:200]})
            print(f"  Statement {i+1}/{len(statements)}: ERROR: {e}")
        time.sleep(0.3)
    return results


def main():
    print("=" * 70)
    print(f"PASCO I BATCH6 — APPLY MIGRATION")
    print(f"Start: {datetime.utcnow().isoformat()}Z")
    print(f"Key present: {'YES' if SUPABASE_KEY else 'NO'}")
    print("=" * 70)

    if not SUPABASE_KEY:
        print("[ERROR] No Supabase key available. Set SUPABASE_SERVICE_ROLE_KEY.")
        print("[INFO] Migration file written to disk — will be applied by CI/CD pipeline.")
        print(f"[INFO] Migration: {MIGRATION_FILE}")
        sys.exit(0)

    # Read migration SQL
    if not MIGRATION_FILE.exists():
        print(f"[ERROR] Migration file not found: {MIGRATION_FILE}")
        sys.exit(1)

    sql = MIGRATION_FILE.read_text()
    print(f"\nMigration file: {MIGRATION_FILE.name}")
    print(f"Size: {len(sql)} chars")

    # Get baseline
    print("\n--- BASELINE EVALUATION ---")
    baseline = evaluate_county()
    if baseline:
        print(f"BEFORE: {json.dumps(baseline)}")
        i_data = baseline.get("I", {})
        print(f"  I: pass={i_data.get('pass')}, metric={i_data.get('metric')}, detail={i_data.get('detail')}")

    # Apply migration
    print("\n--- APPLYING MIGRATION ---")
    print("Attempting Management API...")
    ok, result = apply_via_management_api(sql)

    if ok:
        print(f"Management API: SUCCESS")
        print(f"Result: {str(result)[:300]}")
    else:
        print(f"Management API: FAILED — {result}")
        print("Falling back to individual statement execution...")
        results = apply_sql_statements_individually(sql)
        failed = [r for r in results if not r["ok"]]
        print(f"\nStatements: {len(results)} total, {len(failed)} failed")
        if failed:
            for f in failed[:5]:
                print(f"  FAILED stmt {f['stmt_idx']}: {f['result']}")

    # Wait for DB
    print("\nWaiting 5 seconds for DB to settle...")
    time.sleep(5)

    # Count verification
    print("\n--- COUNT VERIFICATION ---")
    try:
        zone_count_url = (f"{SUPABASE_URL}/rest/v1/parcel_zones"
                         f"?source=like.*shard5_run7519_pasco*&select=count")
        req = urllib.request.Request(
            zone_count_url,
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Prefer": "count=exact"
            }
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            count_header = r.headers.get("content-range", "?")
            print(f"  parcel_zones inserted (shard5_run7519_pasco): {count_header}")
    except Exception as e:
        print(f"  [WARN] zone count check failed: {e}")

    try:
        bd_count_url = (f"{SUPABASE_URL}/rest/v1/bid_decisions"
                       f"?pipeline_run_id=like.*shard5-c72dbd55-run7519-pasco*&select=count")
        req = urllib.request.Request(
            bd_count_url,
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Prefer": "count=exact"
            }
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            count_header = r.headers.get("content-range", "?")
            print(f"  bid_decisions inserted (shard5-c72dbd55-run7519-pasco): {count_header}")
    except Exception as e:
        print(f"  [WARN] bid_decisions count check failed: {e}")

    # Post-fix evaluation
    print("\n--- POST-FIX EVALUATION ---")
    after = evaluate_county()
    if after:
        print(f"AFTER: {json.dumps(after)}")
        i_after = after.get("I", {})
        print(f"  I: pass={i_after.get('pass')}, metric={i_after.get('metric')}, detail={i_after.get('detail')}")
        score = sum(1 for k, v in after.items() if isinstance(v, dict) and v.get("pass"))
        print(f"  Total score: {score}/10")
        if i_after.get("pass"):
            print(f"\n  [PASS] pasco I is now PASSING — metric={i_after.get('metric')}")
            if score == 10:
                print(f"  [10/10] pasco is GOLD STANDARD!")
        else:
            print(f"\n  [FAIL] pasco I still failing — metric={i_after.get('metric')}")
            print(f"  Remaining gap: need to investigate further")

    print("\n" + "=" * 70)
    print("EXECUTION COMPLETE")
    print(f"  BASELINE I: {baseline.get('I', {}).get('detail') if baseline else 'N/A'}")
    print(f"  AFTER I: {after.get('I', {}).get('detail') if after else 'N/A'}")
    print("=" * 70)

    return {"baseline": baseline, "after": after}


if __name__ == "__main__":
    main()
