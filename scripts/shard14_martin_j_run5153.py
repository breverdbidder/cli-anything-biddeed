#!/usr/bin/env python3
"""SHARD-14 martin, dispatch 9d22d82f-cbfe-4f01-a459-b5259d8d08df, loop run 5153.

Letter J executor: apply the J bid_decisions migration + verify via
pencil_dod_evaluate_county('martin').

Uses the Supabase Management API (SUPABASE_ACCESS_TOKEN + project ref) to
execute the SQL -- the same pattern confirmed working across every prior
session (direct psql/pooler auth remains unavailable in this environment).

Usage:
  python3 scripts/shard14_martin_j_run5153.py [--dry-run]

Environment:
  SUPABASE_URL             https://mocerqjnksmhcjzxrewo.supabase.co
  SUPABASE_SERVICE_ROLE_KEY  service-role JWT
  SUPABASE_ACCESS_TOKEN    sbp_... (for Management API, required if PostgREST RPC
                           pencil_dod_evaluate_county isn't available)
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DRY_RUN = "--dry-run" in sys.argv

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
PROJECT_REF = "mocerqjnksmhcjzxrewo"

REST_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

MGMT_HEADERS = {
    "Authorization": f"Bearer {SUPABASE_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}


def rest_post(path, body=None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        data=data,
        method="POST",
        headers={**REST_HEADERS, "Prefer": "return=representation"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read()), r.status


def rest_rpc(fn, params):
    data = json.dumps(params).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{fn}",
        data=data,
        method="POST",
        headers=REST_HEADERS,
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read()), r.status


def mgmt_query(sql):
    data = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query",
        data=data,
        method="POST",
        headers=MGMT_HEADERS,
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read()), r.status


def get_martin_gap():
    """Count martin MCA rows not yet in bid_decisions."""
    sql = """
    SELECT COUNT(*) AS gap
    FROM multi_county_auctions mca
    WHERE mca.county = 'martin'
      AND mca.case_number IS NOT NULL
      AND (mca.data_source IS DISTINCT FROM 'propertyonion' OR mca.tier1_authoritative = true)
      AND NOT EXISTS (
          SELECT 1 FROM bid_decisions bd WHERE bd.case_number = mca.case_number
      )
    """
    result, status = mgmt_query(sql)
    if isinstance(result, list) and result:
        return result[0].get("gap", "?")
    return result


def get_martin_bid_decisions_count():
    """Count complete martin bid_decisions."""
    sql = """
    SELECT COUNT(*) AS n
    FROM bid_decisions
    WHERE county_slug = 'martin'
      AND arv IS NOT NULL
      AND max_bid IS NOT NULL
      AND ml_score IS NOT NULL
      AND factors ? 'distress_location'
      AND factors ? 'distress_property'
      AND factors ? 'distress_owner'
      AND factors ? 'cma_distressed'
      AND factors ? 'cma_resale'
    """
    result, status = mgmt_query(sql)
    if isinstance(result, list) and result:
        return result[0].get("n", "?")
    return result


def evaluate_county():
    """Run pencil_dod_evaluate_county('martin') via PostgREST RPC."""
    try:
        result, status = rest_rpc("pencil_dod_evaluate_county", {"county_slug_arg": "martin"})
        return result
    except Exception as e:
        print(f"  RPC failed ({e}), trying management API...")
        sql = "SELECT public.pencil_dod_evaluate_county('martin')"
        result, status = mgmt_query(sql)
        return result


def apply_migration_sql():
    """Apply the J migration SQL via Management API."""
    migration_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "supabase",
        "migrations",
        "20260719_gold_standard_shard14_martin_j_bid_decisions_run5153.sql",
    )
    with open(migration_path) as f:
        sql = f.read()

    # Strip the final verification comments (start at the last non-comment line)
    # Actually just run it all -- the verification selects at the end are commented out
    print(f"  SQL length: {len(sql)} chars")
    if DRY_RUN:
        print("  [DRY RUN] Would apply migration -- not executing")
        return True

    result, status = mgmt_query(sql)
    print(f"  Management API response (HTTP {status}): {json.dumps(result)[:500]}")
    return status in (200, 201)


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("FATAL: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set")
        sys.exit(1)
    if not SUPABASE_ACCESS_TOKEN:
        print("WARNING: SUPABASE_ACCESS_TOKEN not set — Management API calls will fail")

    print("=== SHARD-14 martin J executor (run5153) ===")

    # 1. Baseline
    print("\n[1/4] Baseline evaluation...")
    before_eval = evaluate_county()
    print(f"  Before: {json.dumps(before_eval)}")

    # 2. Gap check
    print("\n[2/4] Gap check...")
    gap = get_martin_gap()
    print(f"  martin MCA rows missing bid_decisions: {gap}")
    if gap == 0:
        print("  Gap is 0 — J already at 100%, nothing to do.")
        return

    # 3. Apply migration
    print("\n[3/4] Applying J migration...")
    ok = apply_migration_sql()
    if not ok and not DRY_RUN:
        print("  FAIL-LOUD: migration did not succeed. See above for details.")
        sys.exit(1)

    if not DRY_RUN:
        time.sleep(2)

    # 4. Verify
    print("\n[4/4] Post-migration verification...")
    complete = get_martin_bid_decisions_count()
    print(f"  Complete martin bid_decisions: {complete}")

    after_eval = evaluate_county()
    print(f"\n=== AFTER ===")
    print(json.dumps(after_eval, indent=2))

    # Extract J metric
    if isinstance(after_eval, list):
        j_row = next((r for r in after_eval if isinstance(r, dict) and r.get("letter") == "J"), None)
        if j_row:
            print(f"\n### SQL VERIFICATION (2026-07-19)")
            print(f"martin J: pass={j_row.get('pass')} metric={j_row.get('metric')} detail={j_row.get('detail')}")
    elif isinstance(after_eval, dict):
        j = after_eval.get("J", {})
        print(f"\n### SQL VERIFICATION (2026-07-19)")
        print(f"martin J: pass={j.get('pass')} metric={j.get('metric')} detail={j.get('detail')}")


if __name__ == "__main__":
    main()
