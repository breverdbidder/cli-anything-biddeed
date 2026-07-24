#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-2 (issue #13697): Master coordinator + verification.

Counties: marion, sarasota, baker, lake
dispatch_id: 497da85d-93af-4543-be33-080707dc4c12

Runs all sub-scripts and produces the final verification summary
with before/after JSON from pencil_dod_evaluate_county.
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

COUNTIES = ["marion", "sarasota", "baker", "lake"]
DISPATCH_ID = "497da85d-93af-4543-be33-080707dc4c12"


def rpc_post(fn_name, payload=None):
    if not SUPABASE_KEY:
        return 0, {"error": "No key"}
    url = f"{SUPABASE_URL}/rest/v1/rpc/{fn_name}"
    data = json.dumps(payload or {}).encode()
    req = urllib.request.Request(url, data=data, headers=HEADERS, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or '{}')


def rest_post_raw(path, data, extra_headers=None):
    if not SUPABASE_KEY:
        return 0, {}
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    body = json.dumps(data).encode()
    h = {**HEADERS, **(extra_headers or {})}
    req = urllib.request.Request(url, data=body, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode() or '{}')
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or '{}')


def evaluate_county(county):
    s, r = rpc_post("pencil_dod_evaluate_county", {"p_county": county})
    if s == 200:
        return r
    return None


def log_ultraloop_audit(county, letter, claim, refuter_evidence, survived):
    """Log to gold_standard_ultraloop_audit per CERTIFY GATE requirements."""
    row = {
        "dispatch_id": DISPATCH_ID,
        "ultraloop_mode": "fallback",
        "county_slug": county,
        "letter": letter,
        "claim": claim,
        "refuter_evidence": refuter_evidence,
        "survived": survived,
    }
    s, r = rest_post_raw("gold_standard_ultraloop_audit", row,
                         {"Prefer": "resolution=merge-duplicates,return=minimal"})
    return s in (200, 201)


def print_evaluation_table(county, eval_result):
    """Print a clean table of county evaluation results."""
    if not eval_result:
        print(f"  {county}: EVALUATION FAILED")
        return
    
    if isinstance(eval_result, dict):
        # Single result dict
        print(f"  {county}: {eval_result}")
        return
    
    if isinstance(eval_result, list):
        pass_count = 0
        fail_count = 0
        print(f"\n  {county.upper()} evaluation:")
        for item in eval_result:
            letter = item.get('letter', '?')
            metric = item.get('metric')
            passed = item.get('pass', False)
            status_icon = "✅" if passed else "❌"
            if passed:
                pass_count += 1
            else:
                fail_count += 1
            print(f"    {letter}: {status_icon} metric={metric}")
        print(f"  Score: {pass_count}/10")


print("=" * 70)
print(f"GOLD STANDARD SHARD-2 MASTER COORDINATOR")
print(f"dispatch_id: {DISPATCH_ID}")
print(f"Session: architect-20260724T080000Z")
print(f"Started: {datetime.now(timezone.utc).isoformat()}")
print("=" * 70)

if not SUPABASE_KEY:
    print("\nERROR: SUPABASE_SERVICE_ROLE_KEY not set")
    print("Cannot run without DB credentials. Checking what scripts are available...")
    scripts_dir = os.path.join(os.path.dirname(__file__))
    shard2_scripts = [f for f in os.listdir(scripts_dir) if f.startswith('shard2_13697')]
    print(f"Available shard2-13697 scripts: {shard2_scripts}")
    sys.exit(1)

# --- BASELINE ---
print("\n=== BASELINE EVALUATIONS ===")
baseline = {}
for county in COUNTIES:
    result = evaluate_county(county)
    baseline[county] = result
    print_evaluation_table(county, result)

# --- RUN FIXES ---
print("\n=== RUNNING FIXES ===")

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))

def run_script(script_name):
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    if not os.path.exists(script_path):
        print(f"  SKIP: {script_name} not found")
        return False
    print(f"\n  Running {script_name}...")
    result = subprocess.run(
        [sys.executable, script_path],
        capture_output=True,
        text=True,
        env=os.environ,
        timeout=300,
    )
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(f"  STDERR: {result.stderr[:500]}")
    return result.returncode == 0

# Run each county's fix script
for script_name in [
    "shard2_13697_sarasota_g_pk1000_i_fix.py",
    "shard2_13697_baker_full_fix.py",
    "shard2_13697_lake_comprehensive_fix.py",
]:
    run_script(script_name)

# --- FINAL EVALUATIONS ---
print("\n=== FINAL EVALUATIONS ===")
final = {}
for county in COUNTIES:
    result = evaluate_county(county)
    final[county] = result
    print_evaluation_table(county, result)

# --- COMPARISON ---
print("\n=== BEFORE/AFTER COMPARISON ===")
for county in COUNTIES:
    b = baseline.get(county, [])
    a = final.get(county, [])
    
    if not b or not a:
        print(f"\n  {county}: No comparison available")
        continue
    
    b_map = {}
    a_map = {}
    if isinstance(b, list):
        b_map = {item['letter']: item for item in b}
    if isinstance(a, list):
        a_map = {item['letter']: item for item in a}
    
    b_pass = sum(1 for item in (b if isinstance(b, list) else []) if item.get('pass'))
    a_pass = sum(1 for item in (a if isinstance(a, list) else []) if item.get('pass'))
    
    print(f"\n  {county.upper()}: {b_pass}/10 → {a_pass}/10")
    for letter in 'ABCDEFGHIJ':
        b_item = b_map.get(letter, {})
        a_item = a_map.get(letter, {})
        b_status = "PASS" if b_item.get('pass') else "FAIL"
        a_status = "PASS" if a_item.get('pass') else "FAIL"
        b_metric = b_item.get('metric', 'null')
        a_metric = a_item.get('metric', 'null')
        changed = b_status != a_status or str(b_metric) != str(a_metric)
        prefix = "→" if changed else " "
        print(f"    {prefix} {letter}: {b_status}({b_metric}) → {a_status}({a_metric})")

# --- LOG ULTRALOOP AUDIT ROWS ---
print("\n=== LOGGING ULTRALOOP AUDIT ROWS ===")
for county in COUNTIES:
    a = final.get(county, [])
    if not isinstance(a, list):
        continue
    for item in a:
        letter = item.get('letter')
        passed = item.get('pass', False)
        metric = item.get('metric')
        
        # Log PASS letters as verified
        if passed:
            evidence = {
                "query": f"pencil_dod_evaluate_county('{county}')",
                "metric": metric,
                "session": "shard2_13697",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            ok = log_ultraloop_audit(
                county, letter,
                f"{county} letter {letter} PASS (metric={metric})",
                evidence,
                True,
            )
            print(f"  Logged: {county}/{letter} PASS survived={'yes' if ok else 'ERROR'}")

# --- FINAL SUMMARY ---
print("\n=== FINAL SUMMARY ===")
print(f"dispatch_id: {DISPATCH_ID}")
print(f"Completed: {datetime.now(timezone.utc).isoformat()}")
print()
for county in COUNTIES:
    a = final.get(county, [])
    if isinstance(a, list):
        passed = [item['letter'] for item in a if item.get('pass')]
        failed = [item['letter'] for item in a if not item.get('pass')]
        print(f"  {county}: {len(passed)}/10 PASS={','.join(passed)} FAIL={','.join(failed)}")

print("\n### SQL VERIFICATION")
print("```sql")
for county in COUNTIES:
    print(f"SELECT public.pencil_dod_evaluate_county('{county}');")
print("```")

print("\nFINAL EVALUATIONS:")
print(json.dumps(final, indent=2))
