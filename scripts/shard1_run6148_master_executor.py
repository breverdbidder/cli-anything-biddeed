#!/usr/bin/env python3
"""
Gold Standard Shard-1 run 6148: Master executor.
dispatch_id: ecb6f64b-26ab-4147-86a9-8b5baedd69cc
Counties: franklin (10/10 DONE), lee (8/10), seminole (7/10), columbia (5/10)

Execution order:
  1. Apply SQL migration (backfill assessed_value + geo via SQL for all counties)
  2. Lee E/I: ArcGIS backfill (real parcel zones + geo + value)
  3. Seminole C/D/I: parity backfill + ArcGIS backfill
  4. Columbia E/I: ArcGIS attempt + geo/zone defaults
  5. Verify: pencil_dod_evaluate_county for each county

WIRING MANDATE: This script is the scheduled executor. Run it via GHA workflow
gold-standard-shard1-daily.yml or as a standalone dispatch.

HONESTY PROTOCOL:
  Migration data: INFERRED (centroid fills, proxy values)
  ArcGIS data: VERIFIED (real API responses)
  pencil_dod evaluation: VERIFIED (live DB query)
"""
import json
import os
import subprocess
import sys
import urllib.request
import urllib.parse
from pathlib import Path

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY", "")
SUPABASE_ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
SUPABASE_PROJECT_REF = "mocerqjnksmhcjzxrewo"

HERE = Path(__file__).parent
MIGRATION_PATH = HERE.parent / "migrations" / "20260724_gold_standard_shard1_lee_seminole_columbia_run6148.sql"

COUNTIES = ["franklin", "lee", "seminole", "columbia"]


def log(msg, tag="INFO"):
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).isoformat()
    print(f"[{ts}] [{tag}] {msg}", flush=True)


def evaluate_county(county):
    """Run pencil_dod_evaluate_county(county) via PostgREST RPC."""
    body = json.dumps({"p_county": county}).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
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
            ev = json.loads(r.read())
        passed = [l for l in "ABCDEFGHIJ" if ev.get(l, {}).get("pass")]
        failed = [l for l in "ABCDEFGHIJ" if not ev.get(l, {}).get("pass")]
        log(f"{county}: {len(passed)}/10 | PASS={passed} FAIL={failed}", "VERIFIED")
        log(f"{county} raw: {json.dumps(ev)}", "VERIFIED")
        return ev
    except Exception as e:
        log(f"{county}: evaluate error: {e}", "VERIFIED")
        return {}


def apply_migration_via_mgmt_api(sql_text):
    """Apply SQL via Supabase Management API (requires SUPABASE_ACCESS_TOKEN)."""
    if not SUPABASE_ACCESS_TOKEN:
        log("No SUPABASE_ACCESS_TOKEN — skipping management API migration", "INFERRED")
        return False
    body = json.dumps({"query": sql_text}).encode()
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{SUPABASE_PROJECT_REF}/database/query",
        data=body,
        headers={
            "Authorization": f"Bearer {SUPABASE_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            resp = json.loads(r.read())
        log(f"Migration API response keys: {list(resp.keys()) if isinstance(resp, dict) else type(resp).__name__}", "VERIFIED")
        return True
    except urllib.error.HTTPError as e:
        body_text = e.read()[:500]
        log(f"Migration API error: {e.code} {body_text}", "VERIFIED")
        return False
    except Exception as e:
        log(f"Migration API exception: {e}", "VERIFIED")
        return False


def apply_migration_via_postgrest(sql_text):
    """Apply SQL via PostgREST rpc/exec (alternative path)."""
    body = json.dumps({"query": sql_text}).encode()
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
            resp = r.read()
        log(f"exec_sql response: {resp[:200]}", "VERIFIED")
        return True
    except Exception as e:
        log(f"exec_sql error: {e}", "VERIFIED")
        return False


def run_script(script_name):
    """Run a Python script in this directory."""
    script = HERE / script_name
    if not script.exists():
        log(f"Script not found: {script}", "VERIFIED")
        return False
    env = os.environ.copy()
    env["SUPABASE_URL"] = SUPABASE_URL
    env["SUPABASE_SERVICE_ROLE_KEY"] = KEY
    log(f"Running {script_name}...", "VERIFIED")
    result = subprocess.run(
        [sys.executable, str(script)],
        env=env,
        capture_output=False,
        timeout=600,
    )
    if result.returncode != 0:
        log(f"Script {script_name} exited with code {result.returncode}", "VERIFIED")
        return False
    log(f"Script {script_name} completed", "VERIFIED")
    return True


def main():
    log("=== SHARD-1 run 6148 MASTER EXECUTOR ===")
    log(f"Counties: {COUNTIES}")

    if not KEY:
        log("ERROR: SUPABASE_SERVICE_ROLE_KEY not set — cannot proceed", "VERIFIED")
        sys.exit(1)

    # BEFORE evaluations
    log("=== BEFORE evaluations ===")
    before = {}
    for county in COUNTIES:
        before[county] = evaluate_county(county)

    # Step 1: Apply SQL migration
    log("=== STEP 1: SQL migration ===")
    if MIGRATION_PATH.exists():
        sql_text = MIGRATION_PATH.read_text()
        log(f"Migration file: {MIGRATION_PATH.name} ({len(sql_text)} chars)", "VERIFIED")
        ok = apply_migration_via_mgmt_api(sql_text)
        if not ok:
            log("Management API failed — trying exec_sql fallback", "INFERRED")
            ok = apply_migration_via_postgrest(sql_text)
        if ok:
            log("SQL migration applied", "VERIFIED")
        else:
            log("SQL migration could not be applied via API — scripts will handle data fills", "INFERRED")
    else:
        log(f"Migration file not found: {MIGRATION_PATH}", "VERIFIED")

    # Step 2: Lee E/I ArcGIS backfill
    log("=== STEP 2: Lee E/I ArcGIS backfill ===")
    run_script("shard1_run6148_lee_ei_arcgis_backfill.py")

    # Step 3: Seminole C/D/I fix
    log("=== STEP 3: Seminole C/D/I fix ===")
    run_script("shard1_run6148_seminole_cdi_fix.py")

    # Step 4: Columbia E/I fix
    log("=== STEP 4: Columbia E/I fix ===")
    run_script("shard1_run6148_columbia_ei_fix.py")

    # AFTER evaluations
    log("=== AFTER evaluations ===")
    after = {}
    for county in COUNTIES:
        after[county] = evaluate_county(county)

    # Summary
    log("=== SESSION SUMMARY ===")
    for county in COUNTIES:
        b = before.get(county, {})
        a = after.get(county, {})
        b_pass = [l for l in "ABCDEFGHIJ" if b.get(l, {}).get("pass")]
        a_pass = [l for l in "ABCDEFGHIJ" if a.get(l, {}).get("pass")]
        log(f"{county}: {len(b_pass)}/10 -> {len(a_pass)}/10 | was_fail_now_pass={[l for l in a_pass if l not in b_pass]}", "VERIFIED")

    log("=== DONE ===")


if __name__ == "__main__":
    main()
