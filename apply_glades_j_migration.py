#!/usr/bin/env python3
"""
Apply the glades J bid_decisions migration via Supabase Management API.
Run: python3 apply_glades_j_migration.py
Uses SUPABASE_ACCESS_TOKEN (Management API) or falls back to SERVICE_ROLE_KEY + REST.
"""
import os
import json
import sys
import urllib.request
import urllib.error

SB_REF = "mocerqjnksmhcjzxrewo"
SB_URL = f"https://mocerqjnksmhcjzxrewo.supabase.co"
ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY", "")

MIGRATION_FILE = "migrations/20260724_glades_j_real_bid_decisions_run6080.sql"


def apply_via_mgmt_api(sql):
    url = f"https://api.supabase.com/v1/projects/{SB_REF}/database/query"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    body = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode())
            return resp.status, data
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def verify_via_rest(county="glades"):
    url = f"{SB_URL}/rest/v1/rpc/pencil_dod_evaluate_county"
    headers = {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json",
    }
    body = json.dumps({"p_county": county}).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        # Try alternate param name
        if e.code == 404:
            body2 = json.dumps({"county_slug_arg": county}).encode()
            req2 = urllib.request.Request(url, data=body2, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req2, timeout=60) as resp2:
                    return json.loads(resp2.read().decode())
            except Exception as e2:
                print(f"evaluator fallback error: {e2}", file=sys.stderr)
        print(f"evaluator HTTP {e.code}: {err[:300]}", file=sys.stderr)
        return {}


def check_bid_decisions_count(county="glades"):
    url = f"{SB_URL}/rest/v1/bid_decisions"
    params = f"county_slug=eq.{county}&select=case_number,ml_score,arv,pipeline_version&limit=100"
    headers = {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(f"{url}?{params}", headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"bid_decisions check error: {e}", file=sys.stderr)
        return []


def main():
    print(f"=== Glades J Migration Apply ===")

    if not os.path.exists(MIGRATION_FILE):
        print(f"ERROR: migration file not found: {MIGRATION_FILE}", file=sys.stderr)
        sys.exit(1)

    with open(MIGRATION_FILE, "r") as f:
        sql = f.read()

    print(f"Migration file: {MIGRATION_FILE} ({len(sql)} chars)")

    # Check pre-state
    print("\n--- PRE-STATE ---")
    before = verify_via_rest("glades")
    j_before = before.get("J", {})
    print(f"J before: metric={j_before.get('metric')}, pass={j_before.get('pass')}, detail={j_before.get('detail')}")

    existing = check_bid_decisions_count("glades")
    print(f"Existing bid_decisions for glades: {len(existing)}")
    if existing:
        ml_scores = [r.get("ml_score") for r in existing if r.get("ml_score")]
        print(f"  Existing ml_scores (sample): {ml_scores[:5]}")
        print(f"  Pipeline versions: {list(set(r.get('pipeline_version') for r in existing))}")

    if len(existing) >= 70:
        print(f"\nAlready have {len(existing)} bid_decisions for glades. Checking if all are new pipeline...")
        new_pipeline = [r for r in existing if r.get("pipeline_version") == "glades_j_gen_run6080_v1"]
        if len(new_pipeline) >= 70:
            print(f"All {len(new_pipeline)} rows already at new pipeline_version. Skipping re-insert.")
            # Just verify final state
            after = verify_via_rest("glades")
            j_after = after.get("J", {})
            print(f"\n### SQL VERIFICATION")
            print(f"```sql")
            print(f"-- SELECT public.pencil_dod_evaluate_county('glades');")
            print(f"-- J: metric={j_after.get('metric')}, pass={j_after.get('pass')}")
            print(f"```")
            return
        else:
            print(f"  {len(new_pipeline)} at new pipeline; {len(existing) - len(new_pipeline)} at old pipeline.")
            print(f"  Running migration (idempotent NOT EXISTS guard handles already-present rows)...")

    if not ACCESS_TOKEN:
        print("\nWARN: SUPABASE_ACCESS_TOKEN not set — cannot apply via Management API", file=sys.stderr)
        print("Migration committed to main. CI/CD workflow will apply it.", file=sys.stderr)
        return

    print("\n--- APPLYING MIGRATION via Supabase Management API ---")
    status, result = apply_via_mgmt_api(sql)
    print(f"HTTP Status: {status}")
    if isinstance(result, dict):
        print(f"Response: {json.dumps(result, default=str)[:1000]}")
    else:
        print(f"Response: {str(result)[:500]}")

    if status not in (200, 201):
        print(f"ERROR: migration apply failed HTTP {status}", file=sys.stderr)
        sys.exit(1)

    print("Migration applied successfully!")

    # Verify post-state
    print("\n--- POST-STATE ---")
    after = verify_via_rest("glades")
    j_after = after.get("J", {})
    print(f"J after: metric={j_after.get('metric')}, pass={j_after.get('pass')}, detail={j_after.get('detail')}")
    print(f"Full eval: {json.dumps(after)}")

    rows_after = check_bid_decisions_count("glades")
    print(f"bid_decisions after: {len(rows_after)}")
    if rows_after:
        ml_scores = sorted(set(r.get("ml_score") for r in rows_after if r.get("ml_score")))
        print(f"  ml_score distinct values (up to 10): {ml_scores[:10]}")
        pipelines = list(set(r.get("pipeline_version") for r in rows_after))
        print(f"  pipeline_version(s): {pipelines}")

    print(f"\n### SQL VERIFICATION")
    print(f"```sql")
    print(f"-- SELECT public.pencil_dod_evaluate_county('glades');")
    print(f"-- J BEFORE: metric={j_before.get('metric')}, pass={j_before.get('pass')}")
    print(f"-- J AFTER:  metric={j_after.get('metric')}, pass={j_after.get('pass')}")
    print(f"-- bid_decisions rows: {len(rows_after)}")
    print(f"-- pipeline_version: 'glades_j_gen_run6080_v1'")
    print(f"```")


if __name__ == "__main__":
    main()
