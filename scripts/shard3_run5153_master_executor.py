#!/usr/bin/env python3
"""
SHARD-3 LOOP-5153 Master Executor
dispatch_id: c366ee22-d3b0-463b-a846-62ee258772f2
Session: architect-20260719T160000

Assigned counties: orange (10/10 ✅), hernando (8/10), miami_dade (7/10), okaloosa (4/10)

Execution order:
  1. miami_dade C/D residual + G pk1000 fix (scripts/shard3_miami_dade_cd_g_residual_fix.py)
  2. okaloosa comprehensive C/D/E/I fix (scripts/shard3_okaloosa_comprehensive_fix.py)
  3. hernando B/F historical harvest attempt (scripts/shard3_hernando_bf_historical_harvest.py)
  4. Final verification of all 4 counties

Usage:
  python3 scripts/shard3_run5153_master_executor.py

Requirements:
  SUPABASE_URL and SUPABASE_KEY (or SUPABASE_SERVICE_ROLE_KEY) env vars
"""
from __future__ import annotations
import json, os, sys, subprocess, time, urllib.request, urllib.error
from datetime import datetime, timezone

SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = (os.environ.get("SUPABASE_KEY") or
          os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "")
if not SB_KEY:
    print("ERROR: SUPABASE_KEY not set", file=sys.stderr)
    sys.exit(1)

BASE = f"{SB_URL}/rest/v1"
HEADERS = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
}

ASSIGNED_COUNTIES = ["orange", "hernando", "miami_dade", "okaloosa"]

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))


def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def evaluate_county(county: str) -> dict:
    url = f"{BASE}/rpc/pencil_dod_evaluate_county"
    body = json.dumps({"p_county": county}).encode()
    req = urllib.request.Request(url, data=body, headers=HEADERS, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  evaluate({county}) ERROR: {e}")
        return {}


def print_county_summary(county: str, ev: dict):
    passing = [k for k, v in ev.items() if isinstance(v, dict) and v.get("pass")]
    failing = [k for k, v in ev.items() if isinstance(v, dict) and not v.get("pass")]
    print(f"\n  === {county.upper()} {len(passing)}/10 ===")
    for letter in "ABCDEFGHIJ":
        ld = ev.get(letter, {})
        status = "PASS" if ld.get("pass") else "FAIL"
        metric = ld.get("metric")
        detail = ld.get("detail", {})
        if detail:
            detail_str = " ".join(f"{k}={v}" for k, v in detail.items() if v is not None)
        else:
            detail_str = ""
        print(f"    {letter} {status} metric={metric} [{detail_str}]")


def run_script(script_name: str, env_extra: dict = None) -> int:
    """Run a script with the current environment."""
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    if not os.path.exists(script_path):
        print(f"  SKIP: {script_path} not found")
        return -1

    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    env["SUPABASE_URL"] = SB_URL
    env["SUPABASE_KEY"] = SB_KEY
    env["SUPABASE_SERVICE_ROLE_KEY"] = SB_KEY

    print(f"\n[{ts()}] Running {script_name}...")
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            env=env,
            timeout=600,
            capture_output=False,
        )
        return result.returncode
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT: {script_name} exceeded 600s")
        return -1
    except Exception as e:
        print(f"  ERROR running {script_name}: {e}")
        return -1


def main():
    print(f"[{ts()}] SHARD-3 LOOP-5153 MASTER EXECUTOR")
    print(f"  dispatch_id: c366ee22-d3b0-463b-a846-62ee258772f2")
    print(f"  Counties: {ASSIGNED_COUNTIES}")

    # ── BEFORE state ─────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"BEFORE STATE")
    print(f"{'='*60}")
    before_states = {}
    for county in ASSIGNED_COUNTIES:
        ev = evaluate_county(county)
        before_states[county] = ev
        print_county_summary(county, ev)

    # ── orange is already 10/10, just verify ────────────────────────────────
    orange_ev = before_states.get("orange", {})
    orange_passing = [k for k, v in orange_ev.items() if isinstance(v, dict) and v.get("pass")]
    if len(orange_passing) >= 10:
        print(f"\n[{ts()}] orange: 10/10 CONFIRMED — no action needed")
    else:
        print(f"\n[{ts()}] orange: {len(orange_passing)}/10 — unexpected regression, investigate")

    # ── miami_dade C/D + G fix ───────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"STEP 1: miami_dade C/D residual + G pk1000 fix")
    print(f"{'='*60}")
    rc = run_script("shard3_miami_dade_cd_g_residual_fix.py")
    print(f"  miami_dade fix exit code: {rc}")
    time.sleep(3)

    miami_after = evaluate_county("miami_dade")
    miami_passing = [k for k, v in miami_after.items() if isinstance(v, dict) and v.get("pass")]
    print(f"\n  miami_dade AFTER: {len(miami_passing)}/10 passing: {miami_passing}")

    # ── okaloosa comprehensive fix ───────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"STEP 2: okaloosa comprehensive C/D/E/I fix")
    print(f"{'='*60}")
    rc = run_script("shard3_okaloosa_comprehensive_fix.py")
    print(f"  okaloosa fix exit code: {rc}")
    time.sleep(3)

    okaloosa_after = evaluate_county("okaloosa")
    okaloosa_passing = [k for k, v in okaloosa_after.items() if isinstance(v, dict) and v.get("pass")]
    print(f"\n  okaloosa AFTER: {len(okaloosa_passing)}/10 passing: {okaloosa_passing}")

    # ── hernando B/F historical harvest ─────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"STEP 3: hernando B/F historical harvest")
    print(f"{'='*60}")
    rc = run_script("shard3_hernando_bf_historical_harvest.py")
    print(f"  hernando fix exit code: {rc}")
    time.sleep(3)

    hernando_after = evaluate_county("hernando")
    hernando_passing = [k for k, v in hernando_after.items() if isinstance(v, dict) and v.get("pass")]
    print(f"\n  hernando AFTER: {len(hernando_passing)}/10 passing: {hernando_passing}")

    # ── FINAL state ──────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"FINAL STATE")
    print(f"{'='*60}")
    final_states = {
        "orange": before_states.get("orange", {}),
        "hernando": hernando_after,
        "miami_dade": miami_after,
        "okaloosa": okaloosa_after,
    }
    for county in ASSIGNED_COUNTIES:
        ev = final_states.get(county, {})
        print_county_summary(county, ev)

    # ── Summary ──────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"SUMMARY (BEFORE → AFTER)")
    print(f"{'='*60}")
    for county in ASSIGNED_COUNTIES:
        before_ev = before_states.get(county, {})
        after_ev = final_states.get(county, {})
        before_pass = sum(1 for k, v in before_ev.items() if isinstance(v, dict) and v.get("pass"))
        after_pass = sum(1 for k, v in after_ev.items() if isinstance(v, dict) and v.get("pass"))
        arrow = "→"
        print(f"  {county}: {before_pass}/10 {arrow} {after_pass}/10")

    # Full JSON for issue comment verification
    print(f"\n### VERIFICATION JSON (paste into issue comment)")
    print(f"```json")
    verification = {}
    for county in ASSIGNED_COUNTIES:
        verification[county] = final_states.get(county, {})
    print(json.dumps(verification, indent=2))
    print(f"```")


if __name__ == "__main__":
    main()
