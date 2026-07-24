#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-2 (issue #13697): Apply migrations via Management API and run all fixes.
dispatch_id: 497da85d-93af-4543-be33-080707dc4c12

This is the MAIN EXECUTION SCRIPT for the GHA workflow.
1. Applies SQL migrations via Supabase Management API
2. Runs Python fix scripts via subprocess
3. Produces final evaluation and verification
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
ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
PROJECT_ID = "mocerqjnksmhcjzxrewo"

DISPATCH_ID = "497da85d-93af-4543-be33-080707dc4c12"
COUNTIES = ["marion", "sarasota", "baker", "lake"]

REST_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

MGMT_HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json",
}


def rpc_post(fn_name, payload=None):
    if not SUPABASE_KEY:
        return 0, {"error": "No service key"}
    url = f"{SUPABASE_URL}/rest/v1/rpc/{fn_name}"
    data = json.dumps(payload or {}).encode()
    req = urllib.request.Request(url, data=data, headers=REST_HEADERS, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or '{}')


def apply_sql_via_mgmt_api(sql_content, description=""):
    """Apply SQL via Supabase Management API."""
    if not ACCESS_TOKEN:
        print(f"  SKIP (no ACCESS_TOKEN): {description}")
        return False
    url = f"https://api.supabase.com/v1/projects/{PROJECT_ID}/database/query"
    # SET statement_timeout = 0 before the main SQL
    full_sql = f"SET statement_timeout = 0;\n{sql_content}"
    data = json.dumps({"query": full_sql}).encode()
    req = urllib.request.Request(url, data=data, headers=MGMT_HEADERS, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode())
            print(f"  OK: {description} -> {resp.status}")
            return True
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  ERROR {e.code}: {description} -> {body[:200]}")
        return False


def apply_sql_via_rest_rpc(sql_content, description=""):
    """Apply SQL via REST RPC (if Management API unavailable)."""
    if not SUPABASE_KEY:
        print(f"  SKIP (no key): {description}")
        return False
    # Use a service-role query if available
    # Try via Supabase REST RPC for simple queries
    url = f"{SUPABASE_URL}/rest/v1/rpc/exec_sql"
    data = json.dumps({"sql": sql_content}).encode()
    req = urllib.request.Request(url, data=data, headers=REST_HEADERS, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            print(f"  OK via RPC: {description}")
            return True
    except urllib.error.HTTPError as e:
        # exec_sql may not exist - try direct approach
        body = e.read().decode()
        if e.code == 404:
            return apply_sql_via_mgmt_api(sql_content, description)
        print(f"  ERROR {e.code}: {description} -> {body[:200]}")
        return False


def evaluate_county(county):
    s, r = rpc_post("pencil_dod_evaluate_county", {"p_county": county})
    if s == 200:
        return r
    print(f"  EVAL ERROR {county}: {s} {r}")
    return None


def format_eval_summary(county, eval_result):
    if not eval_result or not isinstance(eval_result, list):
        return f"{county}: NO DATA"
    passed = [item['letter'] for item in eval_result if item.get('pass')]
    failed = [item['letter'] for item in eval_result if not item.get('pass')]
    score = len(passed)
    detail = ", ".join(f"{item['letter']}={'PASS' if item.get('pass') else 'FAIL'}({item.get('metric','?')})"
                      for item in eval_result)
    return f"{county}: {score}/10 [{detail}]"


def rest_post(path, data, extra_headers=None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    body = json.dumps(data).encode()
    h = {**REST_HEADERS, **(extra_headers or {})}
    req = urllib.request.Request(url, data=body, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode() or '{}')
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or '{}')


def rest_get(path, params=None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, headers=REST_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or '{}')


def log_ultraloop_audit(county, letter, claim, evidence, survived):
    row = {
        "dispatch_id": DISPATCH_ID,
        "ultraloop_mode": "fallback",
        "county_slug": county,
        "letter": letter,
        "claim": claim,
        "refuter_evidence": evidence,
        "survived": survived,
    }
    s, r = rest_post("gold_standard_ultraloop_audit", row,
                     {"Prefer": "resolution=merge-duplicates,return=minimal"})
    return s in (200, 201)


print("=" * 70)
print(f"GOLD STANDARD SHARD-2 - MAIN EXECUTION")
print(f"dispatch_id: {DISPATCH_ID}")
print(f"Started: {datetime.now(timezone.utc).isoformat()}")
print(f"SUPABASE_KEY present: {bool(SUPABASE_KEY)}")
print(f"ACCESS_TOKEN present: {bool(ACCESS_TOKEN)}")
print("=" * 70)

if not SUPABASE_KEY:
    print("FATAL: No database credentials available")
    sys.exit(1)

# ============================================================
# PHASE 1: Baseline evaluations
# ============================================================
print("\n=== PHASE 1: BASELINE EVALUATIONS ===")
baseline = {}
for county in COUNTIES:
    result = evaluate_county(county)
    baseline[county] = result
    summary = format_eval_summary(county, result)
    print(f"  {summary}")

# ============================================================
# PHASE 2: Apply Lake J migration via Management API
# ============================================================
print("\n=== PHASE 2: APPLY LAKE J MIGRATION ===")
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
MIGRATIONS_DIR = os.path.join(SCRIPTS_DIR, '..', 'migrations')

lake_j_migration = os.path.join(MIGRATIONS_DIR, '20260724_gold_standard_shard2_13697_lake_j_generator.sql')
if os.path.exists(lake_j_migration):
    with open(lake_j_migration, 'r') as f:
        sql_content = f.read()
    ok = apply_sql_via_mgmt_api(sql_content, "Lake J generator (bid_decisions)")
    if not ok:
        print("  Trying alternative apply method...")
        # Try using the existing apply_sql_direct.py approach
        apply_script = os.path.join(SCRIPTS_DIR, 'apply_sql_direct.py')
        if os.path.exists(apply_script):
            result = subprocess.run(
                [sys.executable, apply_script, lake_j_migration],
                capture_output=True, text=True, env=os.environ, timeout=120
            )
            print(result.stdout[:500])
            if result.stderr:
                print(f"  STDERR: {result.stderr[:200]}")
else:
    print(f"  SKIP: {lake_j_migration} not found")

# ============================================================
# PHASE 3: Run Python fix scripts
# ============================================================
print("\n=== PHASE 3: PYTHON FIX SCRIPTS ===")

def run_fix_script(script_name, timeout=300):
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    if not os.path.exists(script_path):
        print(f"  SKIP: {script_name} not found")
        return False, ""
    print(f"\n  === Running {script_name} ===")
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            env=os.environ,
            timeout=timeout,
        )
        output = result.stdout + (f"\nSTDERR: {result.stderr[:500]}" if result.stderr else "")
        print(output[:3000])
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT after {timeout}s")
        return False, "TIMEOUT"
    except Exception as e:
        print(f"  ERROR: {e}")
        return False, str(e)

# Run county fix scripts
fix_results = {}
for script_name in [
    "shard2_13697_sarasota_g_pk1000_i_fix.py",
    "shard2_13697_baker_full_fix.py",
    "shard2_13697_lake_comprehensive_fix.py",
]:
    ok, output = run_fix_script(script_name)
    fix_results[script_name] = {"ok": ok, "output": output[:2000]}

# ============================================================
# PHASE 4: Final evaluations
# ============================================================
print("\n=== PHASE 4: FINAL EVALUATIONS ===")
final = {}
for county in COUNTIES:
    result = evaluate_county(county)
    final[county] = result
    summary = format_eval_summary(county, result)
    print(f"  {summary}")

# ============================================================
# PHASE 5: Comparison and ultraloop audit logging
# ============================================================
print("\n=== PHASE 5: BEFORE/AFTER COMPARISON ===")
total_before_pass = 0
total_after_pass = 0

for county in COUNTIES:
    b = baseline.get(county, [])
    a = final.get(county, [])
    
    b_map = {item['letter']: item for item in (b if isinstance(b, list) else [])}
    a_map = {item['letter']: item for item in (a if isinstance(a, list) else [])}
    
    b_pass = sum(1 for item in (b if isinstance(b, list) else []) if item.get('pass'))
    a_pass = sum(1 for item in (a if isinstance(a, list) else []) if item.get('pass'))
    total_before_pass += b_pass
    total_after_pass += a_pass
    
    changed = b_pass != a_pass
    print(f"\n  {county.upper()}: {b_pass}/10 → {a_pass}/10 {'✅ IMPROVED' if a_pass > b_pass else ('⚠️ REGRESSED' if a_pass < b_pass else '(unchanged)')}")
    
    for letter in 'ABCDEFGHIJ':
        b_item = b_map.get(letter, {})
        a_item = a_map.get(letter, {})
        b_p = b_item.get('pass', False)
        a_p = a_item.get('pass', False)
        b_m = b_item.get('metric', 'null')
        a_m = a_item.get('metric', 'null')
        
        if str(b_m) != str(a_m) or b_p != a_p:
            icon = "→" if a_p and not b_p else ("⚠️" if b_p and not a_p else "~")
            print(f"    {icon} {letter}: {b_p}({b_m}) → {a_p}({a_m})")

# ============================================================
# PHASE 6: Log ultraloop audit rows
# ============================================================
print("\n=== PHASE 6: ULTRALOOP AUDIT LOGGING ===")
for county in COUNTIES:
    a = final.get(county, [])
    if not isinstance(a, list):
        continue
    
    for item in a:
        letter = item.get('letter')
        passed = item.get('pass', False)
        metric = item.get('metric')
        
        if passed:
            evidence = {
                "query": f"SELECT public.pencil_dod_evaluate_county('{county}');",
                "result_letter": letter,
                "result_metric": metric,
                "session": f"shard2_13697_{datetime.now(timezone.utc).strftime('%Y%m%d')}",
                "verified_at": datetime.now(timezone.utc).isoformat(),
            }
            ok = log_ultraloop_audit(
                county, letter,
                f"{county} letter {letter} PASS (metric={metric}), shard2-13697 session",
                evidence,
                True,
            )
            print(f"  Logged: {county}/{letter} PASS survived={'yes' if ok else 'ERROR'}")

# ============================================================
# PHASE 7: Final summary
# ============================================================
print("\n" + "=" * 70)
print("FINAL SUMMARY")
print(f"dispatch_id: {DISPATCH_ID}")
print(f"Completed: {datetime.now(timezone.utc).isoformat()}")
print("=" * 70)

for county in COUNTIES:
    a = final.get(county, [])
    if isinstance(a, list):
        passed = [item['letter'] for item in a if item.get('pass')]
        score = len(passed)
        print(f"  {county}: {score}/10 PASS=[{','.join(passed)}]")

# SQL VERIFICATION block (required by SHIP GATE)
print("\n### SQL VERIFICATION")
print("```sql")
print("SET statement_timeout = 0;")
for county in COUNTIES:
    print(f"SELECT public.pencil_dod_evaluate_county('{county}');")
print("```")

print("\nFINAL EVALUATION JSON:")
print(json.dumps(final, indent=2))
