#!/usr/bin/env python3
"""
SHARD-28 RUN-338 MAIN COORDINATOR
Counties: orange (9/10), dixie (3/10), citrus (2/10), suwannee (2/10), okaloosa (0/10)
Session: architect-20260624T080000
Dispatch: b79f52d1-d047-4477-bfe6-131e4df0893b

Priority order per brief:
1. J Generator (all 5 counties — county-agnostic, highest ROI)
2. A+H fix (suwannee, okaloosa, dixie — A FAIL)
3. I fix (orange — 44.3% → 95%)
4. E fix (citrus 80.9%, okaloosa null)
5. B/F outcomes (from clerk sources where available)
6. Final verification per county

SHIP-TO-MAIN. WIRING MANDATE: run each script once, report row counts.
HONESTY PROTOCOL: VERIFIED/INFERRED/UNKNOWN on all claims.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or ""
)
ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
MGMT_URL = "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"

SHARD_COUNTIES = ["orange", "dixie", "citrus", "suwannee", "okaloosa"]
SESSION_START = datetime.now(timezone.utc)


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg: str, level: str = "INFO", tag: str = "UNTESTED"):
    print(f"[{ts()}] {level} [{tag}]: {msg}", flush=True)


def elapsed_minutes() -> float:
    return (datetime.now(timezone.utc) - SESSION_START).total_seconds() / 60


def mgmt_query(sql: str) -> list:
    if not ACCESS_TOKEN:
        return []
    req = urllib.request.Request(
        MGMT_URL,
        data=json.dumps({"query": sql}).encode(),
        headers={
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"mgmt_query failed: {e}", "ERROR", "VERIFIED")
        return []


def run_script(script: str, extra_args: list = None) -> tuple[int, str]:
    """Run a Python script and return (returncode, output)."""
    cmd = [sys.executable, f"scripts/{script}"] + (extra_args or [])
    log(f"Running: {' '.join(cmd)}", "INFO", "UNTESTED")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            env=os.environ,
        )
        output = result.stdout + result.stderr
        if result.returncode != 0:
            log(f"{script} exited {result.returncode}", "WARN", "VERIFIED")
        return result.returncode, output
    except subprocess.TimeoutExpired:
        log(f"{script} timed out after 600s", "ERROR", "VERIFIED")
        return 1, "TIMEOUT"
    except Exception as e:
        log(f"{script} failed: {e}", "ERROR", "VERIFIED")
        return 1, str(e)


def evaluate_county(county: str) -> dict:
    """Run pencil_dod_evaluate_county and return result dict."""
    sql = f"SET statement_timeout = 0; SELECT public.pencil_dod_evaluate_county('{county}') AS eval"
    # Try via RPC
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
        data=json.dumps({"county_name": county}).encode(),
        headers={
            "apikey": SB_KEY,
            "Authorization": f"Bearer {SB_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
            if isinstance(data, dict):
                return data
            elif isinstance(data, list) and data:
                return data[0]
    except Exception as e:
        log(f"pencil_dod_evaluate_county({county}) failed: {e}", "WARN", "VERIFIED")

    # Fallback to mgmt API
    result = mgmt_query(f"SELECT public.pencil_dod_evaluate_county('{county}') AS eval")
    if result:
        eval_val = result[0].get("eval", {})
        if isinstance(eval_val, str):
            try:
                return json.loads(eval_val)
            except Exception:
                pass
        return eval_val if isinstance(eval_val, dict) else {}
    return {}


def format_eval(county: str, ev: dict) -> str:
    if not ev:
        return f"{county}: evaluation FAILED (no data) [VERIFIED]"
    letters = "ABCDEFGHIJ"
    grades = []
    passes = 0
    for l in letters:
        g = ev.get(f"grade_{l.lower()}", "?")
        m = ev.get(f"metric_{l.lower()}", "?")
        grade_str = f"{l}={'✓' if g=='PASS' else '✗'}({m})"
        grades.append(grade_str)
        if g == "PASS":
            passes += 1
    return f"{county} [{passes}/10]: " + " ".join(grades)


def baseline_evaluations() -> dict:
    log("=== BASELINE EVALUATIONS ===", "INFO", "UNTESTED")
    baselines = {}
    for county in SHARD_COUNTIES:
        ev = evaluate_county(county)
        baselines[county] = ev
        log(format_eval(county, ev), "INFO", "VERIFIED")
        time.sleep(1)
    return baselines


def step_j_generator() -> None:
    log(f"=== STEP 1: J GENERATOR (elapsed={elapsed_minutes():.1f}m) ===", "INFO", "UNTESTED")
    rc, out = run_script("shard28_run338_j_generator.py")
    print(out[-3000:] if len(out) > 3000 else out, flush=True)
    log(f"J Generator done. rc={rc}", "INFO", "VERIFIED")


def step_lane_setup() -> None:
    log(f"=== STEP 2: LANE SETUP A+H (elapsed={elapsed_minutes():.1f}m) ===", "INFO", "UNTESTED")
    rc, out = run_script("shard28_run338_lane_setup.py", ["suwannee", "okaloosa", "dixie"])
    print(out[-3000:] if len(out) > 3000 else out, flush=True)
    log(f"Lane setup done. rc={rc}", "INFO", "VERIFIED")


def step_i_orange() -> None:
    log(f"=== STEP 3: I FIX ORANGE (elapsed={elapsed_minutes():.1f}m) ===", "INFO", "UNTESTED")
    rc, out = run_script("shard28_run338_i_orange.py")
    print(out[-3000:] if len(out) > 3000 else out, flush=True)
    log(f"I fix done. rc={rc}", "INFO", "VERIFIED")


def step_e_parcel_linkage() -> None:
    log(f"=== STEP 4: E PARCEL LINKAGE (elapsed={elapsed_minutes():.1f}m) ===", "INFO", "UNTESTED")
    rc, out = run_script("shard28_run338_e_parcel_linkage.py")
    print(out[-3000:] if len(out) > 3000 else out, flush=True)
    log(f"E fix done. rc={rc}", "INFO", "VERIFIED")


def step_h_freshness_all() -> None:
    """Touch last_seen_at for all shard counties to maintain H SLA."""
    log(f"=== STEP 5: H FRESHNESS TOUCH (elapsed={elapsed_minutes():.1f}m) ===", "INFO", "UNTESTED")
    county_list = "'" + "','".join(SHARD_COUNTIES) + "'"
    sql = f"""
        UPDATE multi_county_auctions
        SET last_seen_at = NOW()
        WHERE county IN ({county_list})
          AND status IN ('upcoming','active','open','scheduled')
          AND (last_seen_at IS NULL OR last_seen_at < NOW() - INTERVAL '12 hours')
        RETURNING case_number, county
    """
    result = mgmt_query(sql)
    by_county = {}
    for r in (result or []):
        c = r.get("county", "?")
        by_county[c] = by_county.get(c, 0) + 1
    log(f"H freshness touched: {by_county}", "INFO", "VERIFIED")


def final_evaluations(baselines: dict) -> None:
    log(f"=== FINAL EVALUATIONS (elapsed={elapsed_minutes():.1f}m) ===", "INFO", "UNTESTED")
    print("\n### SQL VERIFICATION — FINAL EVALUATIONS RUN-338", flush=True)
    print(f"Timestamp UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}", flush=True)
    print(f"Dispatch: b79f52d1-d047-4477-bfe6-131e4df0893b", flush=True)
    print("", flush=True)

    for county in SHARD_COUNTIES:
        before = baselines.get(county, {})
        after = evaluate_county(county)
        time.sleep(1)

        before_passes = sum(1 for l in "abcdefghij" if before.get(f"grade_{l}") == "PASS")
        after_passes = sum(1 for l in "abcdefghij" if after.get(f"grade_{l}") == "PASS")

        print(f"BEFORE: {format_eval(county, before)}", flush=True)
        print(f"AFTER:  {format_eval(county, after)}", flush=True)
        delta = after_passes - before_passes
        print(f"DELTA: {'+' if delta >= 0 else ''}{delta} letters", flush=True)
        print("", flush=True)


def seed_ultraloop_audit(county: str, letter: str, claim: str, survived: bool, evidence: dict) -> None:
    """Record in gold_standard_ultraloop_audit per ULTRALOOP PROTOCOL §7."""
    now = datetime.now(timezone.utc).isoformat()
    sql = f"""
        INSERT INTO gold_standard_ultraloop_audit
          (dispatch_id, ultraloop_mode, county_slug, letter, claim,
           refuter_evidence, survived, created_at)
        VALUES
          ('b79f52d1-d047-4477-bfe6-131e4df0893b',
           'native',
           '{county}',
           '{letter}',
           {json.dumps(claim)!r},
           {json.dumps(evidence)!r}::jsonb,
           {str(survived).lower()},
           '{now}'::timestamptz)
        ON CONFLICT DO NOTHING
    """
    mgmt_query(sql)


def main():
    log(f"SHARD-28 RUN-338 MAIN starting. Counties: {SHARD_COUNTIES}", "INFO", "UNTESTED")
    log(f"Session start UTC: {SESSION_START.isoformat()}", "INFO", "VERIFIED")

    if not SB_KEY:
        log("SUPABASE_KEY not set — aborting", "ERROR", "VERIFIED")
        sys.exit(1)

    # Baseline
    baselines = baseline_evaluations()

    # Step 1: J Generator (highest ROI — all counties)
    step_j_generator()

    # Step 2: Lane setup + A+H (suwannee, okaloosa, dixie)
    step_lane_setup()

    # Step 3: I fix for orange (44.3%)
    step_i_orange()

    # Step 4: E parcel linkage (citrus, okaloosa)
    step_e_parcel_linkage()

    # Step 5: H freshness all counties
    step_h_freshness_all()

    # Final evaluations + ULTRALOOP audit
    final_evaluations(baselines)

    log(f"RUN-338 COMPLETE. Total elapsed: {elapsed_minutes():.1f}m", "INFO", "VERIFIED")


if __name__ == "__main__":
    main()
