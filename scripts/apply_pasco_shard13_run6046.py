#!/usr/bin/env python3
"""Apply the pasco shard-13 run-6046 C/D/I fix via Supabase Management API.

This is the executor for the WIRING MANDATE — it runs the migration SQL and
the AJAX harvester, then verifies via pencil_dod_evaluate_county.

Usage:
  python3 scripts/apply_pasco_shard13_run6046.py

Environment:
  SUPABASE_ACCESS_TOKEN  — Supabase Management API token (sbp_...)
  SUPABASE_URL           — optional, defaults to known project URL
  SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY — PostgREST key for RPC + AJAX harvester
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or ""
)
MGMT_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
MGMT_API = "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

MIGRATION_FILE = Path(__file__).parent.parent / "supabase/migrations/20260723_shard13_pasco_cdij_backfill.sql"


def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str) -> None:
    print(f"[{ts()}] {msg}", flush=True)


def mgmt_sql(sql: str, label: str = "SQL") -> dict | None:
    if not MGMT_TOKEN:
        log(f"MGMT_TOKEN not set — skipping {label}")
        return None
    payload = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(
        MGMT_API,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {MGMT_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": UA,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            result = json.loads(r.read())
            log(f"{label} OK — rows: {len(result) if isinstance(result, list) else 'N/A'}")
            return result
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:500]
        log(f"{label} HTTP {e.code}: {body}")
        return None
    except Exception as e:
        log(f"{label} error: {e}")
        return None


def sb_rpc(fn: str, args: dict, timeout: int = 90):
    if not SUPABASE_KEY:
        return None
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{fn}",
        data=json.dumps(args).encode(),
        method="POST",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "User-Agent": UA,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        log(f"RPC {fn} HTTP {e.code}: {e.read().decode()[:300]}")
        return None
    except Exception as e:
        log(f"RPC {fn} error: {e}")
        return None


def evaluate(county: str = "pasco"):
    log(f"=== pencil_dod_evaluate_county('{county}') ===")
    result = sb_rpc("pencil_dod_evaluate_county", {"county_slug_arg": county})
    if result:
        log(f"Evaluation: {json.dumps(result)}")
    else:
        log("Evaluation returned None — trying via mgmt SQL")
        result = mgmt_sql(
            f"SELECT public.pencil_dod_evaluate_county('{county}')",
            f"evaluate_{county}"
        )
        if result:
            log(f"Mgmt eval: {json.dumps(result)}")
    return result


def apply_migration():
    if not MIGRATION_FILE.exists():
        log(f"Migration file not found: {MIGRATION_FILE}")
        return False
    sql = MIGRATION_FILE.read_text()
    log(f"Applying migration {MIGRATION_FILE.name} ({len(sql)} chars)...")
    result = mgmt_sql(sql, f"migration_{MIGRATION_FILE.stem}")
    if result is not None:
        log(f"Migration applied: {json.dumps(result)[:500]}")
        return True
    log("Migration via mgmt API failed")
    return False


def run_ajax_harvester():
    log("=== Running AJAX harvester (shard13_run6046_pasco_cdij_fix.py) ===")
    harvester = Path(__file__).parent / "shard13_run6046_pasco_cdij_fix.py"
    if not harvester.exists():
        log(f"Harvester not found: {harvester}")
        return False
    env = os.environ.copy()
    proc = subprocess.run(
        [sys.executable, str(harvester)],
        env=env,
        capture_output=False,
        timeout=300,
    )
    log(f"Harvester exit code: {proc.returncode}")
    return proc.returncode == 0


def main():
    log(f"=== PASCO SHARD-13 RUN-6046 EXECUTOR ===")
    log(f"MGMT_TOKEN present: {bool(MGMT_TOKEN)}")
    log(f"SUPABASE_KEY present: {bool(SUPABASE_KEY)}")

    log("\n--- BEFORE ---")
    before = evaluate()

    log("\n--- APPLY MIGRATION (I fix parcel_zones) ---")
    mig_ok = apply_migration()
    log(f"Migration result: {'OK' if mig_ok else 'FAILED/SKIPPED'}")

    log("\n--- RUN AJAX HARVESTER (C/D fix) ---")
    harvester_ok = run_ajax_harvester()
    log(f"Harvester result: {'OK' if harvester_ok else 'FAILED/SKIPPED'}")

    log("\n--- AFTER ---")
    after = evaluate()

    log("\n=== SUMMARY ===")
    log(f"BEFORE: {json.dumps(before)}")
    log(f"AFTER:  {json.dumps(after)}")

    if after:
        def get_pass(result, letter):
            if isinstance(result, dict):
                return result.get(letter, {}).get("pass", False)
            elif isinstance(result, list):
                for item in result:
                    if isinstance(item, dict) and item.get("letter") == letter:
                        return item.get("pass", False)
            return None

        c_pass = get_pass(after, "C")
        d_pass = get_pass(after, "D")
        i_pass = get_pass(after, "I")
        log(f"C PASS: {c_pass}  D PASS: {d_pass}  I PASS: {i_pass}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
