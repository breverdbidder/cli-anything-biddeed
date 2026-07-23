#!/usr/bin/env python3
"""
SHARD-10 SESSION RUNNER — volusia + hamilton (2026-07-23)
==========================================================
dispatch_id: 056047c1-7d6b-4a2b-8122-831715b1b406

Runs all shard-10 improvements in order:
1. Apply volusia G+I migration (20260723_volusia_g_i_zoning_real_substrate.sql)
2. Run volusia GIS harvest (shard10_volusia_g_i_real_gis_harvest.py)
3. Apply hamilton I migration (20260723_hamilton_i_property_card_enrichment.sql)
4. Run hamilton I enrichment (shard10_hamilton_i_audit_and_enrichment.py)
5. Evaluate both counties and print before/after

Usage:
  SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... python3 scripts/shard10_session_runner.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

DISPATCH_ID = "056047c1-7d6b-4a2b-8122-831715b1b406"
SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or ""
)


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg: str) -> None:
    print(f"[{ts()}] {msg}", flush=True)


def sb_rpc(fn: str, params: dict | None = None) -> dict:
    url = f"{SB_URL}/rest/v1/rpc/{fn}"
    payload = json.dumps(params or {}).encode()
    req = urllib.request.Request(
        url, data=payload,
        headers={
            "apikey": SB_KEY,
            "Authorization": f"Bearer {SB_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read()
        return {"error": f"HTTP {e.code}: {body[:300]}"}


def evaluate_county(county: str) -> dict:
    result = sb_rpc("pencil_dod_evaluate_county", {"p_county": county})
    if isinstance(result, dict) and "error" in result:
        # Try alternate parameter name
        result = sb_rpc("pencil_dod_evaluate_county", {"county_slug": county})
    return result


def apply_migration_via_api(sql: str) -> dict:
    """Apply SQL via Supabase Management API."""
    access_token = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
    project_ref = "mocerqjnksmhcjzxrewo"
    if not access_token:
        return {"error": "SUPABASE_ACCESS_TOKEN not set"}

    url = f"https://api.supabase.com/v1/projects/{project_ref}/database/query"
    payload = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(
        url, data=payload,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read()
        return {"error": f"HTTP {e.code}: {body[:400]}"}


def run_script(script_path: str) -> int:
    """Run a Python script and return exit code."""
    env = {**os.environ}
    result = subprocess.run(
        [sys.executable, script_path],
        env=env,
        capture_output=False,
        timeout=300,
    )
    return result.returncode


def read_sql_file(path: str) -> str:
    with open(path, "r") as f:
        return f.read()


def main() -> None:
    log("=== SHARD-10 SESSION RUNNER: volusia + hamilton ===")
    if not SB_KEY:
        log("ERROR: SUPABASE_KEY not set")
        sys.exit(1)

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Step 0: Baseline evaluation
    log("STEP 0: Baseline evaluation")
    baseline_volusia = evaluate_county("volusia")
    baseline_hamilton = evaluate_county("hamilton")
    log(f"BASELINE volusia: {json.dumps(baseline_volusia)}")
    log(f"BASELINE hamilton: {json.dumps(baseline_hamilton)}")

    # Step 1: Apply volusia migration
    log("STEP 1: Apply volusia G+I zoning substrate migration")
    sql_path = os.path.join(repo_root, "migrations", "20260723_volusia_g_i_zoning_real_substrate.sql")
    if os.path.exists(sql_path):
        sql = read_sql_file(sql_path)
        result = apply_migration_via_api(sql)
        if "error" in result:
            log(f"  Migration apply failed: {result['error']}")
            log("  Will try via apply_sql_direct.py...")
            # Try alternate approach
            exit_code = run_script(os.path.join(repo_root, "scripts", "apply_sql_direct.py"))
            log(f"  apply_sql_direct.py exit code: {exit_code}")
        else:
            log(f"  Migration applied: {result}")
    else:
        log(f"  Migration file not found: {sql_path}")

    # Step 2: Run volusia GIS harvest
    log("STEP 2: Run volusia GIS harvest")
    gis_script = os.path.join(repo_root, "scripts", "shard10_volusia_g_i_real_gis_harvest.py")
    if os.path.exists(gis_script):
        exit_code = run_script(gis_script)
        log(f"  GIS harvest exit code: {exit_code}")
    else:
        log(f"  Script not found: {gis_script}")

    # Step 3: Apply hamilton migration
    log("STEP 3: Apply hamilton I enrichment migration")
    ham_sql_path = os.path.join(repo_root, "migrations", "20260723_hamilton_i_property_card_enrichment.sql")
    if os.path.exists(ham_sql_path):
        sql = read_sql_file(ham_sql_path)
        result = apply_migration_via_api(sql)
        if "error" in result:
            log(f"  Hamilton migration failed: {result['error']}")
        else:
            log(f"  Hamilton migration applied: {result}")

    # Step 4: Run hamilton enrichment script
    log("STEP 4: Run hamilton I enrichment script")
    ham_script = os.path.join(repo_root, "scripts", "shard10_hamilton_i_audit_and_enrichment.py")
    if os.path.exists(ham_script):
        exit_code = run_script(ham_script)
        log(f"  Hamilton enrichment exit code: {exit_code}")

    # Step 5: Post-fix evaluation
    log("STEP 5: Post-fix evaluation")
    after_volusia = evaluate_county("volusia")
    after_hamilton = evaluate_county("hamilton")

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"\n### SHARD-10 SESSION RESULTS — {now_iso}")
    print()
    print("VOLUSIA BASELINE:")
    print(f"  {json.dumps(baseline_volusia, indent=2)}")
    print()
    print("VOLUSIA AFTER:")
    print(f"  {json.dumps(after_volusia, indent=2)}")
    print()
    print("HAMILTON BASELINE:")
    print(f"  {json.dumps(baseline_hamilton, indent=2)}")
    print()
    print("HAMILTON AFTER:")
    print(f"  {json.dumps(after_hamilton, indent=2)}")
    print()
    print("### SQL VERIFICATION")
    print("SELECT public.pencil_dod_evaluate_county('volusia');")
    print("SELECT public.pencil_dod_evaluate_county('hamilton');")


if __name__ == "__main__":
    main()
