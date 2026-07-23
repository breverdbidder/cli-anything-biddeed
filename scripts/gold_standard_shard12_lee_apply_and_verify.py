#!/usr/bin/env python3
"""SHARD-12 lee apply-and-verify script.

Applies the SQL migration via the Supabase Management API and then runs the
E/I ArcGIS backfill script, followed by a live pencil_dod_evaluate_county('lee')
call to confirm metric movement.

Usage:
  SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... SUPABASE_ACCESS_TOKEN=... \
    python3 scripts/gold_standard_shard12_lee_apply_and_verify.py
"""
import json
import os
import subprocess
import sys
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
PROJECT_REF = SUPABASE_URL.replace("https://", "").split(".supabase.co")[0]

MIGRATION_FILE = "supabase/migrations/20260723_shard12_lee_g_mdp3_i_zoning_districts.sql"
BACKFILL_SCRIPT = "scripts/gold_standard_shard12_lee_ei_arcgis_backfill_run6046.py"


def sb_rpc(fn, args=None):
    body = json.dumps(args or {}).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{fn}",
        data=body,
        headers={
            "apikey": KEY,
            "Authorization": f"Bearer {KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def sb_sql(sql):
    """Execute SQL via Supabase REST API using a dummy RPC call pattern."""
    body = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
        data=body,
        headers={
            "apikey": KEY,
            "Authorization": f"Bearer {KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def apply_migration_via_mgmt_api(sql_content):
    """Apply SQL via Supabase Management API /query endpoint."""
    access_token = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
    if not access_token:
        print("WARNING: SUPABASE_ACCESS_TOKEN not set, trying direct REST approach", flush=True)
        return False

    body = json.dumps({"query": sql_content}).encode()
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query",
        data=body,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            resp = json.loads(r.read())
            print(f"  Migration applied via Management API: {r.status}", flush=True)
            return True
    except urllib.error.HTTPError as e:
        print(f"  Management API error: {e.code} {e.read().decode()[:300]}", flush=True)
        return False


def apply_migration_statements(sql_content):
    """Apply SQL by splitting into statements and executing via PostgREST."""
    import re
    statements = [s.strip() for s in re.split(r";\s*\n", sql_content) if s.strip() and not s.strip().startswith("--")]
    print(f"  Applying {len(statements)} SQL statements via REST...", flush=True)
    success = 0
    for i, stmt in enumerate(statements):
        if stmt.upper().startswith("SELECT "):
            continue
        status, resp = sb_rpc("exec_sql", {"query": stmt + ";"})
        if status in (200, 201, 204):
            success += 1
        else:
            print(f"  statement {i}: status={status} err={str(resp)[:200]}", flush=True)
    print(f"  {success}/{len(statements)} statements succeeded", flush=True)
    return success > 0


def evaluate_county(county_slug):
    """Call pencil_dod_evaluate_county and return JSON."""
    status, result = sb_rpc("pencil_dod_evaluate_county", {"p_county_slug": county_slug})
    if status in (200, 201):
        return result
    return {"error": f"status={status} {str(result)[:200]}"}


def main():
    print("=== SHARD-12 Lee County Apply & Verify ===", flush=True)

    # Step 1: Get BEFORE state
    print("\n--- BEFORE: pencil_dod_evaluate_county('lee') ---", flush=True)
    before = evaluate_county("lee")
    print(json.dumps(before, indent=2), flush=True)

    # Step 2: Apply migration
    print(f"\n--- Applying migration: {MIGRATION_FILE} ---", flush=True)
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    migration_path = os.path.join(repo_root, MIGRATION_FILE)

    with open(migration_path) as f:
        sql_content = f.read()

    applied = apply_migration_via_mgmt_api(sql_content)
    if not applied:
        print("  Falling back to statement-by-statement REST application...", flush=True)
        applied = apply_migration_statements(sql_content)

    if not applied:
        print("ERROR: Migration application failed", flush=True)
        sys.exit(1)

    # Step 3: Run E/I backfill
    print(f"\n--- Running E/I backfill: {BACKFILL_SCRIPT} ---", flush=True)
    backfill_path = os.path.join(repo_root, BACKFILL_SCRIPT)
    result = subprocess.run(
        [sys.executable, backfill_path],
        env=os.environ,
        capture_output=False,
    )
    if result.returncode != 0:
        print(f"WARNING: Backfill script exited with code {result.returncode}", flush=True)

    # Step 4: Get AFTER state
    print("\n--- AFTER: pencil_dod_evaluate_county('lee') ---", flush=True)
    after = evaluate_county("lee")
    print(json.dumps(after, indent=2), flush=True)

    # Step 5: Compare
    print("\n--- Before/After comparison ---", flush=True)
    for letter in "ABCDEFGHIJ":
        b = before.get(letter, {})
        a = after.get(letter, {})
        b_metric = b.get("metric", "?")
        a_metric = a.get("metric", "?")
        b_pass = "PASS" if b.get("pass") else "FAIL"
        a_pass = "PASS" if a.get("pass") else "FAIL"
        changed = " *** CHANGED" if (b_metric != a_metric or b_pass != a_pass) else ""
        print(f"  {letter}: {b_pass}/{b_metric} -> {a_pass}/{a_metric}{changed}", flush=True)

    print("\n=== DONE ===", flush=True)


if __name__ == "__main__":
    main()
