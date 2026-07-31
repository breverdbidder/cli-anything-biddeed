#!/usr/bin/env python3
"""
SHARD-3 run 7553 — Apply migrations and verify metrics for:
  hardee (already 10/10, skip)
  santa_rosa (9/10 → fix I)
  alachua   (7/10 → fix E/I/J)
  hamilton  (5/10 → fix G/I/J)

dispatch_id: aab89e89-bf99-4031-bb58-83bb3f4b3739

Usage:
  python scripts/shard3_run7553_apply_and_verify.py

Requires: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY env vars
"""
from __future__ import annotations
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

SB_URL  = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY  = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
           or os.environ.get("SUPABASE_KEY", ""))
if not SB_KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

BASE = f"{SB_URL}/rest/v1"
HEADERS = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
}
COUNTIES = ["hardee", "santa_rosa", "alachua", "hamilton"]

MIGRATIONS = [
    "migrations/20260731_shard3_hamilton_ij_new_rows.sql",
    "migrations/20260731_shard3_alachua_eij_fix.sql",
    "migrations/20260731_shard3_santa_rosa_i_residual_fix.sql",
]


def ts() -> str:
    import datetime
    return datetime.datetime.utcnow().isoformat() + "Z"


def log(msg: str) -> None:
    print(f"[{ts()}] {msg}", flush=True)


def rpc_post(fn: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BASE}/rpc/{fn}",
        data=data,
        headers={**HEADERS},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()[:500]
        log(f"  RPC {fn} HTTP {e.code}: {body_text}")
        return {}
    except Exception as ex:
        log(f"  RPC {fn} ERROR: {ex}")
        return {}


def evaluate_county(county: str) -> dict:
    result = rpc_post("pencil_dod_evaluate_county", {"p_county": county})
    if isinstance(result, list) and result:
        result = result[0]
        if "pencil_dod_evaluate_county" in result:
            result = result["pencil_dod_evaluate_county"]
    return result if isinstance(result, dict) else {}


def apply_sql_via_rpc(sql: str) -> bool:
    """Apply SQL using the exec_sql RPC (if available) or Management API exec endpoint."""
    data = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(
        f"{BASE}/rpc/exec_sql",
        data=data,
        headers={**HEADERS},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            result = r.read().decode()
            log(f"  exec_sql: {result[:200]}")
            return True
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        # If exec_sql doesn't exist, try Management API
        if e.code == 404 or "function" in err.lower():
            return apply_sql_via_mgmt(sql)
        log(f"  exec_sql HTTP {e.code}: {err[:300]}")
        return False


def apply_sql_via_mgmt(sql: str) -> bool:
    """Apply SQL via Supabase Management API (postgres endpoint)."""
    project_ref = "mocerqjnksmhcjzxrewo"
    access_token = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
    if not access_token:
        log("  No SUPABASE_ACCESS_TOKEN — cannot apply via Management API")
        return False

    data = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{project_ref}/database/query",
        data=data,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            result = r.read().decode()
            log(f"  mgmt_api query: {result[:200]}")
            return True
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        log(f"  mgmt_api HTTP {e.code}: {err[:300]}")
        return False


def apply_sql_via_psql_fallback(sql_content: str, migration_name: str) -> bool:
    """Write SQL to a temp file and apply via psql if available."""
    import subprocess
    db_url = os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL", "")
    if not db_url:
        # Try building from parts
        db_pass = os.environ.get("SUPABASE_DB_PASSWORD", "")
        if db_pass:
            db_url = f"postgresql://postgres:{db_pass}@aws-0-us-west-2.pooler.supabase.com:6543/postgres"
        else:
            log(f"  No DB URL available for psql fallback")
            return False

    tmp_file = f"/tmp/{migration_name}"
    pathlib.Path(tmp_file).write_text(sql_content)

    try:
        result = subprocess.run(
            ["psql", db_url, "-f", tmp_file, "--no-password", "-v", "ON_ERROR_STOP=1"],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode == 0:
            log(f"  psql OK: {result.stdout[:300]}")
            return True
        else:
            log(f"  psql FAILED (rc={result.returncode}): {result.stderr[:300]}")
            return False
    except FileNotFoundError:
        log("  psql not found in PATH")
        return False
    except subprocess.TimeoutExpired:
        log("  psql timed out after 300s")
        return False
    except Exception as ex:
        log(f"  psql error: {ex}")
        return False


def apply_migration(migration_path: str) -> bool:
    repo_root = pathlib.Path(__file__).parent.parent
    full_path = repo_root / migration_path
    if not full_path.exists():
        log(f"  Migration file not found: {full_path}")
        return False

    sql = full_path.read_text()
    migration_name = full_path.name
    log(f"  Applying {migration_name} ({len(sql)} chars)")

    # Try methods in order: psql (most reliable), then Management API
    if apply_sql_via_psql_fallback(sql, migration_name):
        return True
    if apply_sql_via_mgmt(sql):
        return True

    log(f"  WARNING: Could not apply {migration_name} via any method")
    return False


def score_from_eval(ev: dict) -> int:
    return sum(1 for l in "ABCDEFGHIJ" if ev.get(l, {}).get("pass") if isinstance(ev.get(l), dict))


def format_eval(ev: dict) -> str:
    parts = []
    for l in "ABCDEFGHIJ":
        v = ev.get(l, {})
        if isinstance(v, dict):
            status = "PASS" if v.get("pass") else "FAIL"
            metric = v.get("metric", "?")
            parts.append(f"  {l}: {status} metric={metric}")
    return "\n".join(parts)


def main():
    log("=" * 70)
    log(f"SHARD-3 run 7553 — Apply and Verify")
    log(f"Counties: {COUNTIES}")
    log("=" * 70)

    # ── BEFORE state ────────────────────────────────────────────────────────
    log("\n── BEFORE STATE ──")
    before = {}
    for county in COUNTIES:
        log(f"  Evaluating {county}...")
        ev = evaluate_county(county)
        before[county] = ev
        score = score_from_eval(ev)
        log(f"  {county}: {score}/10")
        if ev:
            for l in "ABCDEFGHIJ":
                v = ev.get(l, {})
                if isinstance(v, dict) and not v.get("pass"):
                    log(f"    FAIL {l}: metric={v.get('metric')} detail={v.get('detail', '')}")
        time.sleep(0.5)

    # ── Apply migrations ─────────────────────────────────────────────────────
    log("\n── APPLYING MIGRATIONS ──")
    for mig in MIGRATIONS:
        log(f"\n  >>> {mig}")
        ok = apply_migration(mig)
        log(f"  {'OK' if ok else 'FAILED'}: {mig}")
        time.sleep(2)

    # ── AFTER state ──────────────────────────────────────────────────────────
    log("\n── AFTER STATE ──")
    time.sleep(5)  # allow DB to settle
    after = {}
    for county in COUNTIES:
        log(f"  Evaluating {county}...")
        ev = evaluate_county(county)
        after[county] = ev
        score = score_from_eval(ev)
        log(f"  {county}: {score}/10")
        if ev:
            log(f"  Full JSON: {json.dumps(ev)}")
        time.sleep(0.5)

    # ── Summary ──────────────────────────────────────────────────────────────
    log("\n" + "=" * 70)
    log("SHARD-3 run 7553 — SUMMARY")
    log("=" * 70)

    for county in COUNTIES:
        bev = before.get(county, {})
        aev = after.get(county, {})
        b_score = score_from_eval(bev)
        a_score = score_from_eval(aev)
        delta = a_score - b_score
        log(f"\n{county}: {b_score}/10 → {a_score}/10 (Δ{'+' if delta >= 0 else ''}{delta})")

        failing_before = [l for l in "ABCDEFGHIJ" if isinstance(bev.get(l), dict) and not bev[l].get("pass")]
        failing_after  = [l for l in "ABCDEFGHIJ" if isinstance(aev.get(l), dict) and not aev[l].get("pass")]
        fixed = [l for l in failing_before if l not in failing_after]
        if fixed:
            log(f"  FIXED: {fixed}")
        if failing_after:
            log(f"  STILL FAILING: {failing_after}")

    # ── Print SQL VERIFICATION block (SHIP GATE requirement) ──────────────────
    log("\n### SQL VERIFICATION")
    log(f"Timestamp: {ts()}")
    log("SELECT public.pencil_dod_evaluate_county('<county>') results:")
    for county in COUNTIES:
        ev = after.get(county, {})
        score = score_from_eval(ev)
        log(f"\n-- {county}: {score}/10")
        log(f"-- Full eval: {json.dumps(ev)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
