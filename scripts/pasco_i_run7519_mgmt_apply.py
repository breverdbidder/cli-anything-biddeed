#!/usr/bin/env python3
"""Apply pasco I batch6 migration via Supabase Management API.

Uses SUPABASE_ACCESS_TOKEN (not service role key) to run arbitrary SQL
via api.supabase.com/v1/projects/{ref}/database/query — same pattern
as mgmt_sql.py and apply-gold-standard-fix.yml.

dispatch: c72dbd55-f590-4c8d-bfbb-650b55a1ccb1
loop_run: 7519

Usage:
    python3 scripts/pasco_i_run7519_mgmt_apply.py

Requires: SUPABASE_ACCESS_TOKEN env var (or falls back to SUPABASE_SERVICE_ROLE_KEY)
"""
import os, sys, json, time, datetime
import urllib.request, urllib.parse, urllib.error
from pathlib import Path

REF = "mocerqjnksmhcjzxrewo"
MGMT_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN")
SERVICE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
)
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")

MIGRATION_FILE = (
    Path(__file__).parent.parent
    / "supabase/migrations/20260730_gold_standard_shard5_pasco_i_card_completeness_batch6.sql"
)


def mgmt_query(sql):
    """Run SQL via Management API."""
    if not MGMT_TOKEN:
        return None, "No SUPABASE_ACCESS_TOKEN"
    url = f"https://api.supabase.com/v1/projects/{REF}/database/query"
    body = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(url, data=body, method="POST",
        headers={"Authorization": f"Bearer {MGMT_TOKEN}",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", errors="replace")
        return e.code, text


def sb_rpc(fn, body=None):
    """Call Supabase RPC function."""
    if not SERVICE_KEY:
        return None
    url = f"{SUPABASE_URL}/rest/v1/rpc/{fn}"
    data = json.dumps(body or {}).encode()
    req = urllib.request.Request(url, data=data, method="POST",
        headers={"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            result = json.loads(r.read())
            if isinstance(result, list) and result:
                return result[0]
            return result
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", errors="replace")
        print(f"  [RPC ERROR] {fn}: HTTP {e.code}: {text[:300]}")
        return None


def main():
    print("=" * 70)
    print(f"PASCO I BATCH6 — MANAGEMENT API APPLY")
    print(f"Start: {datetime.datetime.utcnow().isoformat()}Z")
    print(f"MGMT_TOKEN present: {'YES' if MGMT_TOKEN else 'NO'}")
    print(f"SERVICE_KEY present: {'YES' if SERVICE_KEY else 'NO'}")
    print("=" * 70)

    # Read migration SQL
    if not MIGRATION_FILE.exists():
        print(f"[ERROR] Migration not found: {MIGRATION_FILE}")
        sys.exit(1)
    sql = MIGRATION_FILE.read_text()
    print(f"Migration: {MIGRATION_FILE.name} ({len(sql)} chars)")

    # Baseline evaluation
    print("\n--- BASELINE ---")
    baseline = sb_rpc("pencil_dod_evaluate_county", {"p_county": "pasco"})
    if baseline:
        i_data = baseline.get("I", {})
        total = sum(1 for k, v in baseline.items() if isinstance(v, dict) and v.get("pass"))
        print(f"BEFORE: I={i_data.get('detail')} pass={i_data.get('pass')} metric={i_data.get('metric')}")
        print(f"BEFORE: total score={total}/10")
        print(f"BEFORE full: {json.dumps(baseline)}")

    # Apply migration
    print("\n--- APPLYING MIGRATION ---")
    if not MGMT_TOKEN:
        print("[ERROR] No SUPABASE_ACCESS_TOKEN — cannot use Management API")
        print("[INFO] Trying REST API fallback via pasco_i_run7519_rest_apply.py...")
        # Import and run the REST-only approach
        import importlib.util
        rest_path = Path(__file__).parent / "pasco_i_run7519_rest_apply.py"
        if rest_path.exists():
            spec = importlib.util.spec_from_file_location("rest_apply", rest_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.main()
        else:
            print(f"[ERROR] REST apply script not found: {rest_path}")
        return

    status, result = mgmt_query(sql)
    print(f"Migration HTTP status: {status}")
    if isinstance(result, str):
        print(f"Response: {result[:500]}")
    else:
        print(f"Response: {json.dumps(result, default=str)[:500]}")

    if status not in (200, 201):
        print(f"[WARN] Migration may have failed (HTTP {status}) — checking result anyway")

    # Wait for DB to settle
    print("\nWaiting 5s for DB to settle...")
    time.sleep(5)

    # Count verification queries
    print("\n--- COUNT VERIFICATION ---")
    verif_queries = [
        ("parcel_zones inserted",
         f"SELECT COUNT(*) AS n FROM public.parcel_zones WHERE source LIKE '%shard5_run7519_pasco%'"),
        ("bid_decisions inserted",
         f"SELECT COUNT(*) AS n FROM public.bid_decisions WHERE pipeline_run_id LIKE '%shard5-c72dbd55-run7519-pasco%'"),
        ("fl_parcels geo updates",
         f"SELECT COUNT(*) AS n FROM public.multi_county_auctions WHERE lower(county)='pasco' AND assessed_value_source LIKE '%shard5_run7519%'"),
    ]
    for label, q in verif_queries:
        s2, r2 = mgmt_query(q)
        if s2 == 200 and isinstance(r2, list) and r2:
            print(f"  {label}: {r2[0].get('n', '?')}")
        else:
            print(f"  {label}: HTTP {s2} — {str(r2)[:100]}")

    # Post-fix evaluation
    print("\n--- POST-FIX EVALUATION ---")
    after = sb_rpc("pencil_dod_evaluate_county", {"p_county": "pasco"})
    if after:
        i_after = after.get("I", {})
        total_after = sum(1 for k, v in after.items() if isinstance(v, dict) and v.get("pass"))
        print(f"AFTER: I={i_after.get('detail')} pass={i_after.get('pass')} metric={i_after.get('metric')}")
        print(f"AFTER: total score={total_after}/10")
        print(f"AFTER full: {json.dumps(after)}")
        if i_after.get("pass"):
            print(f"\n  [PASS] pasco I NOW PASSING — {i_after.get('metric')}%")
            if total_after == 10:
                print(f"  [10/10] pasco IS GOLD STANDARD!")
        else:
            print(f"\n  [FAIL] pasco I still FAILING at {i_after.get('metric')}%")

    print("\n" + "=" * 70)
    print("COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
