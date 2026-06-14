#!/usr/bin/env python3
"""
SHARD-14 Master Coordinator
Executes all targeted fixes in priority order per Gold Standard brief

Execution Order (highest leverage first):
1. Hamilton: Basic ingestion (0/10 -> ~5/10 expected)
2. Volusia: C/D parity fixes (2/10 -> ~4/10 expected)  
3. Lake: H freshness fix (1/10 -> ~2/10 expected)
4. Seminole: H freshness fix (1/10 -> ~2/10 expected)

Follows Evidence-Before-Claims protocol with verification
"""
import subprocess
import sys
import os
import time
import json
from datetime import datetime

def log_action(level, action, details):
    """Structured logging with timestamps"""
    timestamp = datetime.utcnow().isoformat() + 'Z'
    print(f"[{timestamp}] {level}: {action} - {details}")

def run_script(script_path, description):
    """Execute a fix script with proper logging"""
    log_action("INFO", "EXEC_START", f"{description} -> {script_path}")
    
    try:
        result = subprocess.run(
            ["python", script_path],
            capture_output=True,
            text=True,
            timeout=3600
        )
        
        log_action("INFO", "EXEC_RESULT", f"Exit code: {result.returncode}")
        
        # Always show stdout/stderr for transparency
        if result.stdout:
            print(f"--- STDOUT ---\n{result.stdout}")
        if result.stderr:
            print(f"--- STDERR ---\n{result.stderr}")
        
        success = result.returncode == 0
        log_action("INFO" if success else "ERROR", "EXEC_END", 
                  f"{'SUCCESS' if success else 'FAILED'}: {description}")
        
        return success, result
        
    except subprocess.TimeoutExpired:
        log_action("ERROR", "EXEC_TIMEOUT", f"{description} timed out")
        return False, None
    except Exception as e:
        log_action("ERROR", "EXEC_ERROR", f"{description} failed: {e}")
        return False, None

def verify_county_status(county_slug):
    """Verify county metrics using curl (no dependencies)"""
    log_action("INFO", "VERIFY_START", f"Checking {county_slug} metrics")
    
    supabase_url = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
    supabase_key = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
    
    if not supabase_key:
        log_action("ERROR", "VERIFY_FAIL", "No Supabase key available")
        return None
    
    try:
        result = subprocess.run([
            "curl", "-s", "-X", "POST",
            f"{supabase_url}/rest/v1/rpc/pencil_dod_evaluate_county",
            "-H", f"apikey: {supabase_key}",
            "-H", f"Authorization: Bearer {supabase_key}",
            "-H", "Content-Type: application/json",
            "-d", json.dumps({"county_slug_arg": county_slug})
        ], capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            data = json.loads(result.stdout)
            pass_count = sum(1 for item in data if item.get('pass', False))
            
            log_action("INFO", "VERIFY_SUCCESS", f"{county_slug} -> {pass_count}/10 letters")
            
            # Log individual metrics for audit
            for item in data:
                letter = item.get('letter', '?')
                metric = item.get('metric')
                passed = item.get('pass', False)
                status = "PASS" if passed else "FAIL"
                log_action("DATA", "METRIC", f"{county_slug} {letter}: {status} {metric}")
            
            return pass_count
        else:
            log_action("ERROR", "VERIFY_FAIL", f"{county_slug} curl failed: {result.returncode}")
            return None
            
    except Exception as e:
        log_action("ERROR", "VERIFY_ERROR", f"{county_slug} verification failed: {e}")
        return None

def main():
    """Execute the full SHARD-14 autonomous session"""
    log_action("INFO", "SESSION_START", "SHARD-14 Gold Standard autonomous session")
    
    # Baseline metrics from brief
    baseline_metrics = {
        'hamilton': 0,   # 0/10
        'volusia': 2,    # 2/10 (A,H pass)
        'lake': 1,       # 1/10 (A pass)
        'seminole': 1    # 1/10 (A pass)
    }
    
    # Execution plan in priority order
    execution_plan = [
        {
            'county': 'hamilton',
            'script': 'scripts/shard14_hamilton_ingestion.py',
            'description': 'Hamilton basic ingestion (highest leverage)',
            'expected_gain': '5+ letters',
            'baseline': 0
        },
        {
            'county': 'volusia', 
            'script': 'scripts/shard14_parity_fix.py',
            'description': 'Volusia C/D parity fix',
            'expected_gain': '2-3 letters',
            'baseline': 2
        },
        {
            'county': 'lake',
            'script': 'scripts/shard14_freshness_fix.py',
            'description': 'Lake H freshness fix',
            'expected_gain': '1-2 letters',
            'baseline': 1
        },
        {
            'county': 'seminole',
            'script': 'scripts/shard14_freshness_fix.py', 
            'description': 'Seminole H freshness fix',
            'expected_gain': '1-2 letters',
            'baseline': 1
        }
    ]
    
    results = {}
    total_letters_gained = 0
    
    # Execute each fix
    for i, plan in enumerate(execution_plan, 1):
        county = plan['county']
        
        log_action("INFO", "COUNTY_START", 
                  f"[{i}/{len(execution_plan)}] {county} - baseline {plan['baseline']}/10")
        
        # Execute the fix
        success, result = run_script(plan['script'], plan['description'])
        
        if success:
            # Wait for DB consistency
            log_action("INFO", "DB_WAIT", "Waiting 10s for DB consistency")
            time.sleep(10)
            
            # Verify results
            final_count = verify_county_status(county)
            
            if final_count is not None:
                improvement = final_count - plan['baseline']
                total_letters_gained += improvement
                
                results[county] = {
                    'baseline': plan['baseline'],
                    'final': final_count,
                    'improvement': improvement,
                    'success': True,
                    'verified': True
                }
                
                log_action("INFO", "COUNTY_SUCCESS", 
                          f"{county} -> {improvement:+d} letters ({plan['baseline']} -> {final_count})")
            else:
                results[county] = {
                    'baseline': plan['baseline'],
                    'success': True,
                    'verified': False
                }
                log_action("WARN", "COUNTY_UNVERIFIED", f"{county} -> fix applied, verification failed")
        else:
            results[county] = {
                'baseline': plan['baseline'],
                'success': False,
                'verified': False
            }
            log_action("ERROR", "COUNTY_FAILED", f"{county} -> fix failed")
    
    # Session summary with evidence
    log_action("INFO", "SESSION_END", "SHARD-14 session completed")
    log_action("DATA", "TOTAL_IMPROVEMENT", f"{total_letters_gained} letters gained")
    log_action("DATA", "SESSION_RESULTS", json.dumps(results, indent=2))
    
    # Evidence summary for HONESTY PROTOCOL
    log_action("EVIDENCE", "VERIFICATION_METHOD", "pencil_dod_evaluate_county RPC via curl")
    log_action("EVIDENCE", "TIMESTAMP", datetime.utcnow().isoformat() + 'Z')
    log_action("EVIDENCE", "TOTAL_VERIFIED", 
              f"{sum(1 for r in results.values() if r.get('verified'))} counties verified")
    
    # Success criteria
    verified_improvements = sum(r.get('improvement', 0) for r in results.values() if r.get('verified'))
    session_success = verified_improvements > 0
    
    log_action("INFO", "SESSION_RESULT", 
              f"{'SUCCESS' if session_success else 'PARTIAL'}: {verified_improvements} verified letter improvements")
    
    return results

if __name__ == "__main__":
    results = main()
    
    # Exit code based on any verified improvements
    verified_improvements = sum(r.get('improvement', 0) for r in results.values() if r.get('verified'))
    sys.exit(0 if verified_improvements > 0 else 1)