#!/usr/bin/env python3
"""Apply clay C/D/I migration and run evaluator verification.
dispatch_id: 9787c8ea-bb47-465b-bebc-0eb7f4fc3f05
loop_run: 6046

Usage:
  python3 scripts/apply_shard11_run6046_clay_migration.py

Environment:
  SUPABASE_ACCESS_TOKEN  (Supabase Management API token)
  SUPABASE_URL           (optional, for evaluator RPC)
  SUPABASE_KEY / SUPABASE_SERVICE_ROLE_KEY  (for evaluator RPC)
"""
from __future__ import annotations
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

MGMT_API = "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"
MIGRATION_FILE = Path(__file__).parent.parent / "migrations" / "20260723_gold_standard_shard11_clay_cdi_backfill.sql"

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY") or ""
MGMT_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN") or ""


def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str) -> None:
    print(f"[{ts()}] {msg}", flush=True)


def run_sql(sql: str) -> object:
    if not MGMT_TOKEN:
        log("ERROR: SUPABASE_ACCESS_TOKEN not set")
        sys.exit(1)
    body = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(
        MGMT_API, data=body, method="POST",
        headers={
            "Authorization": f"Bearer {MGMT_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read() or b"[]")
    except urllib.error.HTTPError as e:
        body_resp = e.read().decode()
        log(f"  SQL HTTP {e.code}: {body_resp[:500]}")
        raise


def evaluate(county: str) -> dict:
    if not SUPABASE_KEY:
        return {}
    url = f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county"
    body = json.dumps({"p_county": county}).encode()
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"  evaluate({county}) ERROR: {e}")
        return {}


def score(ev: dict) -> int:
    if not isinstance(ev, dict):
        return 0
    return sum(1 for v in ev.values() if isinstance(v, dict) and v.get("pass"))


log("=== BASELINE EVALUATION ===")
clay_before = evaluate("clay")
before_score = score(clay_before)
log(f"clay BEFORE: {json.dumps(clay_before)}")
log(f"clay: {before_score}/10")

log("\n=== APPLYING MIGRATION ===")
sql = MIGRATION_FILE.read_text()
log(f"  Migration file: {MIGRATION_FILE.name}")
log(f"  SQL length: {len(sql)} chars")

try:
    result = run_sql(sql)
    log(f"  Migration result (first 2000 chars): {json.dumps(result)[:2000]}")
except Exception as e:
    log(f"  Migration FAILED: {e}")
    sys.exit(1)

log("\n=== POST-FIX EVALUATION ===")
clay_after = evaluate("clay")
after_score = score(clay_after)
log(f"clay AFTER: {json.dumps(clay_after)}")
log(f"clay: {before_score}/10 -> {after_score}/10")

print("\n### SQL VERIFICATION")
print(f"Timestamp: {ts()}")
print(f"dispatch_id: 9787c8ea-bb47-465b-bebc-0eb7f4fc3f05")
print(f"\nclay BEFORE: {json.dumps(clay_before)}")
print(f"clay AFTER:  {json.dumps(clay_after)}")
print(f"clay: {before_score}/10 -> {after_score}/10")

if after_score >= 10:
    print("\nclay: 10/10 GOLD STANDARD ACHIEVED")
elif after_score > before_score:
    print(f"\nclay: IMPROVED {before_score}/10 -> {after_score}/10")
else:
    print(f"\nclay: NO CHANGE (diagnostics needed)")
