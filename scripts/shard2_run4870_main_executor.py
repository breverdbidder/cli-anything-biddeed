#!/usr/bin/env python3
"""
SHARD-2 RUN 4870 MAIN EXECUTOR
dispatch_id: bca41e8b-a306-444b-a860-b0f5c34e605a
Counties: jackson (10/10), citrus (8/10), clay (7/10), gadsden (6/10), hamilton (4/10)

Runs all county fix scripts in sequence:
1. gadsden: H+I+G (H=164h critical, I=0%, G=null)
2. hamilton: C+D+I (C/D=43.8%, I=6.3%)
3. citrus: E+I (E=76.2%, I=74.1%)
4. clay: C+D+I (C=92.1%, D=92.1%, I=92.1%)
5. jackson: already 10/10, run evaluation to confirm no regression
"""
import json
import os
import subprocess
import sys
from typing import Dict

SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or ""
)

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))


def ts():
    import datetime
    return datetime.datetime.utcnow().isoformat() + "Z"


def log(msg):
    print(f"[{ts()}] {msg}", flush=True)


def run_script(script_name: str) -> int:
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    log(f"\n{'='*60}")
    log(f"RUNNING: {script_name}")
    log(f"{'='*60}")
    result = subprocess.run(
        [sys.executable, script_path],
        env=os.environ,
        capture_output=False,
    )
    return result.returncode


def sb_rpc(func: str, params: Dict) -> Dict:
    import urllib.request
    import urllib.error
    body = json.dumps(params).encode()
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{func}", data=body,
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"  RPC {func} ERROR: {e}")
        return {}


def evaluate_county(county: str) -> Dict:
    return sb_rpc("pencil_dod_evaluate_county", {"p_county": county})


log("=" * 70)
log(f"SHARD-2 RUN 4870 MAIN EXECUTOR — {ts()}")
log("Counties: jackson, citrus, clay, gadsden, hamilton")
log("dispatch_id: bca41e8b-a306-444b-a860-b0f5c34e605a")
log("=" * 70)

COUNTIES = ["jackson", "citrus", "clay", "gadsden", "hamilton"]

# ── BEFORE snapshot ──────────────────────────────────────────────────────────
log("\n=== BEFORE SNAPSHOT ===")
before = {}
for county in COUNTIES:
    ev = evaluate_county(county)
    passing = [l for l in "ABCDEFGHIJ" if ev.get(l, {}).get("pass")]
    before[county] = {"score": len(passing), "passing": passing, "eval": ev}
    log(f"  {county}: {len(passing)}/10 — {passing}")

# ── FIX SCRIPTS ──────────────────────────────────────────────────────────────
scripts = [
    ("shard2_run4870_gadsden_h_i_g_fix.py", "gadsden H/I/G"),
    ("shard2_run4870_hamilton_c_d_i_fix.py", "hamilton C/D/I"),
    ("shard2_run4870_citrus_e_i_fix.py", "citrus E/I"),
    ("shard2_run4870_clay_c_d_i_fix.py", "clay C/D/I"),
]

script_results = {}
for script, label in scripts:
    rc = run_script(script)
    script_results[label] = "OK" if rc == 0 else f"FAIL rc={rc}"
    log(f"  {label}: {script_results[label]}")

# ── AFTER snapshot ───────────────────────────────────────────────────────────
log("\n=== AFTER SNAPSHOT ===")
after = {}
for county in COUNTIES:
    ev = evaluate_county(county)
    passing = [l for l in "ABCDEFGHIJ" if ev.get(l, {}).get("pass")]
    after[county] = {"score": len(passing), "passing": passing, "eval": ev}
    log(f"  {county}: {len(passing)}/10 — {passing}")

# ── SUMMARY ──────────────────────────────────────────────────────────────────
log("\n=== SESSION SUMMARY ===")
print("\n### SQL VERIFICATION — ALL SHARD-2 COUNTIES")
print(f"  Timestamp: {ts()}")
print(f"  dispatch_id: bca41e8b-a306-444b-a860-b0f5c34e605a")
print("")
print(f"  {'County':<12} {'Before':>8} {'After':>8} {'Delta':>8}")
print(f"  {'-'*12} {'-'*8} {'-'*8} {'-'*8}")
for county in COUNTIES:
    b = before[county]["score"]
    a = after[county]["score"]
    delta = f"+{a-b}" if a > b else (str(a-b) if a < b else "0")
    print(f"  {county:<12} {b:>7}/10 {a:>7}/10 {delta:>8}")

print("")
print("  Per-county evaluations AFTER fixes:")
for county in COUNTIES:
    print(f"\n  --- {county.upper()} ({after[county]['score']}/10) ---")
    print(f"  {json.dumps(after[county]['eval'], indent=4)}")

print("")
print("  Script results:")
for label, res in script_results.items():
    print(f"    {label}: {res}")

log("\nSHARD-2 RUN 4870 COMPLETE")
sys.exit(0)
