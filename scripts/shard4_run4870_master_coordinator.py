#!/usr/bin/env python3
"""
SHARD-4 run4870 master coordinator.

dispatch_id: 84d095d7-0a1a-46ee-b7aa-7ac21b7f06f7
Issue: #12755
Counties: palm_beach (10/10 DONE), hernando, santa_rosa, martin

Executes all letter fixes in priority order per county, then verifies
via pencil_dod_evaluate_county. Writes session log to gold_standard_ultraloop_audit.

Usage:
  python3 scripts/shard4_run4870_master_coordinator.py
  python3 scripts/shard4_run4870_master_coordinator.py --county martin
  python3 scripts/shard4_run4870_master_coordinator.py --dry-run
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or
          os.environ.get("SUPABASE_KEY") or "")
if not SB_KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

DISPATCH_ID = "84d095d7-0a1a-46ee-b7aa-7ac21b7f06f7"
DRY_RUN = "--dry-run" in sys.argv
ONLY_COUNTY = None
for arg in sys.argv[1:]:
    if arg.startswith("--county="):
        ONLY_COUNTY = arg.split("=", 1)[1]
    elif arg == "--county" and sys.argv.index(arg) + 1 < len(sys.argv):
        ONLY_COUNTY = sys.argv[sys.argv.index(arg) + 1]

HEADERS = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}


def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg):
    print(f"[{ts()}] {msg}", flush=True)


def rpc(name, body):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{name}", data=json.dumps(body).encode(),
        method="POST", headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"RPC {name} failed: {e}")
        return None


def evaluate_county(county):
    result = rpc("pencil_dod_evaluate_county", {"p_county": county})
    return result


def log_ultraloop_claim(county, letter, claim, survived, evidence):
    if DRY_RUN:
        log(f"DRY-RUN: would log ultraloop claim {county}/{letter}/{survived}")
        return
    body = {
        "dispatch_id": DISPATCH_ID,
        "ultraloop_mode": "fallback",
        "county_slug": county,
        "letter": letter,
        "claim": claim,
        "refuter_evidence": evidence if isinstance(evidence, dict) else {"note": str(evidence)},
        "survived": survived,
    }
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/gold_standard_ultraloop_audit",
        data=json.dumps(body).encode(),
        method="POST",
        headers={**HEADERS, "Prefer": "resolution=ignore-duplicates"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            pass
    except Exception as e:
        log(f"Ultraloop log failed: {e}")


def run_script(script_path, extra_args=None):
    """Run a script as a subprocess module."""
    script_path = Path(script_path)
    if not script_path.exists():
        log(f"ERROR: script not found: {script_path}")
        return False

    original_argv = sys.argv[:]
    try:
        sys.argv = [str(script_path)] + (extra_args or [])
        if DRY_RUN and "--dry-run" not in sys.argv:
            sys.argv.append("--dry-run")
        spec = importlib.util.spec_from_file_location("_script", script_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if hasattr(mod, "main"):
            mod.main()
        return True
    except SystemExit as e:
        if e.code != 0:
            log(f"Script {script_path.name} exited with code {e.code}")
            return False
        return True
    except Exception as e:
        log(f"Script {script_path.name} raised: {e}")
        return False
    finally:
        sys.argv = original_argv


def score_from_eval(ev):
    """Count passing letters from evaluator result."""
    if isinstance(ev, list):
        return sum(1 for r in ev if isinstance(r, dict) and r.get("pass"))
    if isinstance(ev, dict):
        return sum(1 for k, v in ev.items()
                   if isinstance(v, dict) and v.get("pass") and k not in ("county", "V2_LITMUS", "auctions_total"))
    return 0


def county_summary(ev):
    """Extract letter-level pass/fail from evaluator result."""
    letters = {}
    if isinstance(ev, list):
        for row in ev:
            if isinstance(row, dict) and "letter" in row:
                letters[row["letter"]] = {
                    "pass": row.get("pass"),
                    "metric": row.get("metric"),
                    "detail": row.get("detail"),
                }
    elif isinstance(ev, dict):
        for k, v in ev.items():
            if isinstance(v, dict) and "pass" in v:
                letters[k] = v
    return letters


SCRIPTS_DIR = Path(__file__).parent


def process_hernando():
    log("=" * 60)
    log("HERNANDO (8/10 -> targeting 10/10)")
    log("=" * 60)

    before = evaluate_county("hernando")
    log(f"BEFORE hernando: {json.dumps(before, indent=2)}")
    before_score = score_from_eval(before)

    log("Running hernando B/F outcomes script...")
    run_script(SCRIPTS_DIR / "shard4_run4870_hernando_bf_outcomes.py")
    time.sleep(2)

    after = evaluate_county("hernando")
    log(f"AFTER hernando: {json.dumps(after, indent=2)}")
    after_score = score_from_eval(after)

    log(f"Hernando: {before_score}/10 -> {after_score}/10")

    letters_after = county_summary(after)
    for letter in ["B", "F"]:
        if letter in letters_after:
            survived = bool(letters_after[letter].get("pass"))
            log_ultraloop_claim(
                "hernando", letter,
                f"After shard4_run4870 hernando B/F fix: letter {letter}",
                survived,
                {"metric": letters_after[letter].get("metric"),
                 "detail": letters_after[letter].get("detail"),
                 "dispatch_id": DISPATCH_ID})

    return before, after


def process_santa_rosa():
    log("=" * 60)
    log("SANTA_ROSA (7/10 -> targeting 10/10)")
    log("=" * 60)

    before = evaluate_county("santa_rosa")
    log(f"BEFORE santa_rosa: {json.dumps(before, indent=2)}")
    before_score = score_from_eval(before)

    log("Running santa_rosa C/D fix...")
    run_script(SCRIPTS_DIR / "shard4_run4870_santa_rosa_cd_i_fix.py",
               ["--phase", "cd"])
    time.sleep(2)

    log("Running santa_rosa I fix...")
    run_script(SCRIPTS_DIR / "shard4_run4870_santa_rosa_cd_i_fix.py",
               ["--phase", "i"])
    time.sleep(2)

    after = evaluate_county("santa_rosa")
    log(f"AFTER santa_rosa: {json.dumps(after, indent=2)}")
    after_score = score_from_eval(after)

    log(f"Santa Rosa: {before_score}/10 -> {after_score}/10")

    letters_after = county_summary(after)
    for letter in ["C", "D", "I"]:
        if letter in letters_after:
            survived = bool(letters_after[letter].get("pass"))
            log_ultraloop_claim(
                "santa_rosa", letter,
                f"After shard4_run4870 santa_rosa C/D/I fix: letter {letter}",
                survived,
                {"metric": letters_after[letter].get("metric"),
                 "detail": letters_after[letter].get("detail"),
                 "dispatch_id": DISPATCH_ID})

    return before, after


def process_martin():
    log("=" * 60)
    log("MARTIN (5/10 -> targeting 10/10)")
    log("=" * 60)

    before = evaluate_county("martin")
    log(f"BEFORE martin: {json.dumps(before, indent=2)}")
    before_score = score_from_eval(before)

    log("Running martin C/D fix...")
    run_script(SCRIPTS_DIR / "shard4_run4870_martin_cd_e_i_j_fix.py",
               ["--phase", "cd"])
    time.sleep(2)

    log("Running martin E fix...")
    run_script(SCRIPTS_DIR / "shard4_run4870_martin_cd_e_i_j_fix.py",
               ["--phase", "e"])
    time.sleep(2)

    log("Running martin J fix (bid_decisions first — independent of I)...")
    run_script(SCRIPTS_DIR / "shard4_run4870_martin_cd_e_i_j_fix.py",
               ["--phase", "j"])
    time.sleep(2)

    log("Running martin I fix (after E+J to maximize card_complete)...")
    run_script(SCRIPTS_DIR / "shard4_run4870_martin_cd_e_i_j_fix.py",
               ["--phase", "i"])
    time.sleep(2)

    after = evaluate_county("martin")
    log(f"AFTER martin: {json.dumps(after, indent=2)}")
    after_score = score_from_eval(after)

    log(f"Martin: {before_score}/10 -> {after_score}/10")

    letters_after = county_summary(after)
    for letter in ["C", "D", "E", "I", "J"]:
        if letter in letters_after:
            survived = bool(letters_after[letter].get("pass"))
            log_ultraloop_claim(
                "martin", letter,
                f"After shard4_run4870 martin fix: letter {letter}",
                survived,
                {"metric": letters_after[letter].get("metric"),
                 "detail": letters_after[letter].get("detail"),
                 "dispatch_id": DISPATCH_ID})

    return before, after


def closeout():
    log("=" * 60)
    log("CLOSE-OUT: Final verification")
    log("=" * 60)

    for county in ["palm_beach", "hernando", "santa_rosa", "martin"]:
        ev = evaluate_county(county)
        score = score_from_eval(ev)
        log(f"{county.upper()}: {score}/10")
        log(json.dumps(ev, indent=2))


def main():
    log(f"=== SHARD-4 run4870 Master Coordinator ===")
    log(f"dispatch_id={DISPATCH_ID}")
    log(f"DRY_RUN={DRY_RUN}")
    log(f"ONLY_COUNTY={ONLY_COUNTY}")

    results = {}

    if not ONLY_COUNTY or ONLY_COUNTY == "palm_beach":
        log("palm_beach: 10/10 PASS — no action needed")

    if not ONLY_COUNTY or ONLY_COUNTY == "hernando":
        results["hernando"] = process_hernando()

    if not ONLY_COUNTY or ONLY_COUNTY == "santa_rosa":
        results["santa_rosa"] = process_santa_rosa()

    if not ONLY_COUNTY or ONLY_COUNTY == "martin":
        results["martin"] = process_martin()

    closeout()
    log("=== SHARD-4 run4870 session complete ===")


if __name__ == "__main__":
    main()
