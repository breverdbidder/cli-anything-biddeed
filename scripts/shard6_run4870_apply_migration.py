#!/usr/bin/env python3
"""
Apply SHARD-6 run4870 migration and run the charlotte/holmes scripts.
dispatch_id: 95f77ed6-fc70-4c15-9db4-b9b64bef5d1c

USAGE (from cc-runner-ghonly.yml session with credentials set):
    python3 scripts/shard6_run4870_apply_migration.py

STEPS
-----
1. Apply supabase/migrations/20260718_gold_standard_shard6_charlotte_union_holmes_run4870.sql
2. Run holmes C/D fresh clerk check (live page re-fetch)
3. Run charlotte B official records harvest (new angle — OR search)
4. Evaluate all 3 counties via pencil_dod_evaluate_county
5. Report before/after

HONESTY PROTOCOL
----------------
All steps tagged UNTESTED until this script actually runs.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_SERVICE_ROLE")
    or ""
)
ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
MGMT_API = "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"

DISPATCH_ID = "95f77ed6-fc70-4c15-9db4-b9b64bef5d1c"
COUNTIES = ["charlotte", "union", "holmes"]

MIGRATION_FILE = Path(__file__).parent.parent / "supabase" / "migrations" / \
    "20260718_gold_standard_shard6_charlotte_union_holmes_run4870.sql"


def ts() -> str:
    return datetime.now(timezone.utc).isoformat() + "Z"


def log(msg: str, tag: str = "UNTESTED") -> None:
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def run_sql(sql: str) -> list:
    if not ACCESS_TOKEN:
        log("ACCESS_TOKEN not set — skipping", "UNTESTED")
        return []
    body = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(
        MGMT_API,
        data=body,
        method="POST",
        headers={"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"SQL error: {e}", "VERIFIED")
        return []


def evaluate_county(county: str) -> dict | None:
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
        data=json.dumps({"p_county": county}).encode(),
        method="POST",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            result = json.loads(r.read())
            log(f"  {county}: {json.dumps(result)}", "VERIFIED")
            return result
    except Exception as e:
        log(f"  evaluate_county({county}) error: {e}", "VERIFIED")
        return None


def apply_migration() -> bool:
    log(f"Applying {MIGRATION_FILE.name} ...", "UNTESTED")
    if not MIGRATION_FILE.exists():
        log(f"Migration file not found: {MIGRATION_FILE}", "VERIFIED")
        return False
    sql = MIGRATION_FILE.read_text()
    result = run_sql(sql)
    if result is not None:
        log(f"Migration applied. Result: {str(result)[:200]}", "VERIFIED")
        return True
    return False


def run_script(script_name: str) -> int:
    script = Path(__file__).parent / script_name
    if not script.exists():
        log(f"Script not found: {script}", "VERIFIED")
        return 1
    env = dict(os.environ)
    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            env=env,
            timeout=300,
            capture_output=False,
        )
        log(f"  {script_name} exit code: {result.returncode}", "VERIFIED")
        return result.returncode
    except subprocess.TimeoutExpired:
        log(f"  {script_name} timed out", "VERIFIED")
        return 1
    except Exception as e:
        log(f"  {script_name} error: {e}", "VERIFIED")
        return 1


def main() -> int:
    log("=== SHARD-6 run4870 APPLY MIGRATION ===")
    log(f"dispatch_id: {DISPATCH_ID}")

    if not SUPABASE_KEY:
        log("FATAL: SUPABASE_KEY not set — cannot run DB operations", "VERIFIED")
        log("This script requires cc-runner-ghonly.yml session credentials.", "UNTESTED")
        return 1

    log("\n=== BEFORE (baseline) ===")
    before = {}
    for county in COUNTIES:
        before[county] = evaluate_county(county)

    log("\n=== STEP 1: Apply migration ===")
    ok = apply_migration()
    if not ok:
        log("Migration failed — stopping", "VERIFIED")
        return 1

    log("\n=== STEP 2: Holmes C/D fresh clerk check ===")
    holmes_rc = run_script("shard6_run4870_holmes_cd_fresh_clerk_check.py")
    log(f"  Holmes C/D script exit code: {holmes_rc}", "VERIFIED")

    log("\n=== STEP 3: Charlotte B official records harvest ===")
    charlotte_rc = run_script("shard6_run4870_charlotte_b_official_records_harvest.py")
    log(f"  Charlotte B script exit code: {charlotte_rc}", "VERIFIED")

    log("\n=== AFTER ===")
    after = {}
    for county in COUNTIES:
        after[county] = evaluate_county(county)

    log("\n=== DELTA SUMMARY ===")
    for county in COUNTIES:
        b_before = before.get(county)
        b_after = after.get(county)
        if b_before and b_after and isinstance(b_before, list):
            for r in b_after:
                letter = r.get("letter", "?")
                m_before = next((x.get("metric") for x in b_before if x.get("letter") == letter), None)
                m_after = r.get("metric")
                p_before = next((x.get("pass") for x in b_before if x.get("letter") == letter), None)
                p_after = r.get("pass")
                if p_before != p_after or m_before != m_after:
                    log(
                        f"  {county}/{letter}: {m_before} ({'PASS' if p_before else 'FAIL'}) "
                        f"→ {m_after} ({'PASS' if p_after else 'FAIL'})",
                        "VERIFIED",
                    )

    log("\n=== SQL VERIFICATION ===")
    log("Run these queries to confirm state:", "VERIFIED")
    for county in COUNTIES:
        log(f"  SELECT public.pencil_dod_evaluate_county('{county}');", "VERIFIED")
    log(
        "  SELECT county_slug, letter, claim, survived, created_at"
        "    FROM public.gold_standard_ultraloop_audit"
        f"    WHERE dispatch_id = '{DISPATCH_ID}'"
        "    ORDER BY county_slug, letter;",
        "VERIFIED",
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
