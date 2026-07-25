#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-5 — dispatch c271da62 — main orchestrator.
Loop run 6354, 2026-07-25.

Targets:
  citrus (9/10): I failing at 93.7% (179/191) — need 182+
  osceola (8/10): G failing at 0.0% (density=78.7, far=0.0, pk1000=0.0)
                  I failing at 84.3% (113/134) — need 128+

Execution order:
  1. Apply migration SQL (via Supabase Management API) — osceola G fixes
  2. Run osceola I enrichment (FL GIO + Osceola GIS)
  3. Run citrus I enrichment (FL GIO + Citrus GIS + citruspa.org probe)
  4. Evaluate both counties and report

Usage:
    python3 scripts/shard5_c271da62_main.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

SB_URL = (os.environ.get("SUPABASE_URL") or "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY") or ""
MGMT_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN") or ""
PROJECT_REF = "mocerqjnksmhcjzxrewo"

SB_HDR = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
}


def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%SZ")


def log(msg, tag="UNTESTED"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def sb_rpc(fn, params):
    def _do():
        req = urllib.request.Request(
            f"{SB_URL}/rest/v1/rpc/{fn}",
            data=json.dumps(params).encode(),
            headers={k: v for k, v in SB_HDR.items() if k not in ("Prefer",)},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    import urllib.error
    for i in range(3):
        try:
            return _do()
        except (urllib.error.URLError, TimeoutError) as exc:
            time.sleep(2 ** i)
    raise RuntimeError("RPC failed after retries")


def apply_migration_via_mgmt_api(sql_path):
    """Apply SQL migration via Supabase Management API."""
    if not MGMT_TOKEN:
        log("No SUPABASE_ACCESS_TOKEN — cannot apply migration via Management API", "VERIFIED")
        return False

    sql = Path(sql_path).read_text()
    url = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
    req = urllib.request.Request(
        url,
        data=json.dumps({"query": sql}).encode(),
        headers={
            "Authorization": f"Bearer {MGMT_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            result = json.loads(r.read())
        log(f"Migration applied via Mgmt API: {sql_path}", "VERIFIED")
        log(f"Result: {result}", "VERIFIED")
        return True
    except Exception as exc:
        log(f"Mgmt API migration failed: {exc}", "VERIFIED")
        return False


def apply_migration_via_postgrest(sql_path):
    """Apply SQL migration via Supabase PostgREST RPC."""
    sql = Path(sql_path).read_text()
    try:
        result = sb_rpc("exec_sql", {"sql": sql})
        log(f"Migration applied via RPC exec_sql: {sql_path}", "VERIFIED")
        return True
    except Exception as exc:
        log(f"RPC exec_sql failed: {exc} — trying direct query path", "UNTESTED")

    try:
        req = urllib.request.Request(
            f"{SB_URL}/rest/v1/rpc/exec_sql",
            data=json.dumps({"query": sql}).encode(),
            headers=SB_HDR,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            result = json.loads(r.read())
        log(f"Migration applied via RPC exec_sql (alt path): {sql_path}", "VERIFIED")
        return True
    except Exception as exc2:
        log(f"All migration paths failed: {exc2}", "VERIFIED")
        return False


def run_script(script_name, extra_args=None):
    """Run a Python sub-script and return its exit code."""
    cmd = [sys.executable, f"scripts/{script_name}"]
    if extra_args:
        cmd.extend(extra_args)
    log(f"Running: {' '.join(cmd)}", "UNTESTED")
    result = subprocess.run(cmd, capture_output=False, timeout=600)
    if result.returncode != 0:
        log(f"Script {script_name} exited with code {result.returncode}", "VERIFIED")
    return result.returncode


def evaluate(county):
    try:
        result = sb_rpc("pencil_dod_evaluate_county", {"p_county": county})
        log(f"pencil_dod_evaluate_county('{county}'): {json.dumps(result)}", "VERIFIED")
        return result
    except Exception as exc:
        log(f"Evaluation failed for {county}: {exc}", "VERIFIED")
        return {}


def main():
    if not SB_KEY:
        print("[BLOCKED] No Supabase key — set SUPABASE_SERVICE_ROLE_KEY")
        sys.exit(1)

    log("=== SHARD-5 C271DA62 MAIN ORCHESTRATOR ===")
    log(f"dispatch_id=c271da62-402d-45cc-99a7-335708b048cc loop_run=6354")

    log("--- BASELINE ---")
    before_citrus = evaluate("citrus")
    before_osceola = evaluate("osceola")

    migration_path = (
        "supabase/migrations/"
        "20260725_gold_standard_shard5_citrus_osceola_c271da62_g_i_fixes.sql"
    )

    log("--- STEP 1: Apply osceola G migration ---")
    applied = apply_migration_via_mgmt_api(migration_path)
    if not applied:
        applied = apply_migration_via_postgrest(migration_path)
    if applied:
        log("Migration applied — waiting 3s", "VERIFIED")
        time.sleep(3)
        after_g = evaluate("osceola")
        log(f"Osceola after G migration: G={after_g.get('G')}", "VERIFIED")
    else:
        log("Migration NOT applied — G fix will not take effect this session", "VERIFIED")

    log("--- STEP 2: Osceola I enrichment ---")
    run_script("shard5_c271da62_osceola_i.py")

    log("--- STEP 3: Citrus I enrichment ---")
    run_script("shard5_c271da62_citrus_i.py")

    log("--- FINAL EVALUATION ---")
    after_citrus = evaluate("citrus")
    after_osceola = evaluate("osceola")

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"\n### SQL VERIFICATION")
    print(f"Timestamp UTC: {now_iso}")
    print(f"SET statement_timeout = 0;")
    print(f"SELECT public.pencil_dod_evaluate_county('citrus');")
    print(f"SELECT public.pencil_dod_evaluate_county('osceola');")
    print()
    print("BEFORE:")
    print(f"  citrus:  {json.dumps(before_citrus)}")
    print(f"  osceola: {json.dumps(before_osceola)}")
    print()
    print("AFTER:")
    print(f"  citrus:  {json.dumps(after_citrus)}")
    print(f"  osceola: {json.dumps(after_osceola)}")

    log("=== SESSION COMPLETE ===", "VERIFIED")


if __name__ == "__main__":
    main()
