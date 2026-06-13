#!/usr/bin/env python3
"""
SHARD-13 MASTER EXECUTION COORDINATOR - AUTOPILOT RUN 20
SHIP-TO-MAIN MANDATE: 6-hour autonomous session

This script coordinates execution of all SHARD-13 gold standard improvements:
1. J Generator (bid_decisions pipeline) - HIGHEST LEVERAGE 0→95%
2. G Zoning KPI Setup (zoning data ingestion) - Required for I
3. I Property Cards (depends on G completion) 
4. B Verified Outcomes (independent data sources)
5. C/D Parity Fix (PropertyOnion supplementary litmus)  
6. Verification Protocol (before/after metrics)

Target counties: orange (2/10), collier (1/10), pinellas (1/10), gulf (0/10)
Expected total gain: ~400+ points across all counties

Usage:
  python scripts/shard13_master_coordinator.py
  python scripts/shard13_master_coordinator.py --verify-only
  python scripts/shard13_master_coordinator.py --execute-all
"""
import os
import sys
import json
import time
import subprocess
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import logging
import argparse

# Add shared utilities to path
sys.path.append('/home/runner/work/cli-anything-biddeed/cli-anything-biddeed/shared')

try:
    import httpx
    CLIENT_AVAILABLE = True
except ImportError:
    import requests
    CLIENT_AVAILABLE = False

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

# SHARD-13 configuration
TARGET_COUNTIES = ['orange', 'collier', 'pinellas', 'gulf']
SESSION_START = datetime.now(timezone.utc)
MAX_SESSION_HOURS = 5.5  # Leave buffer for close-out

# Priority order based on leverage analysis
PRIORITY_TASKS = [
    {
        "name": "J_GENERATOR", 
        "description": "Build bid_decisions pipeline - 0→95% for all counties",
        "estimated_hours": 2.0,
        "script": "shard13_j_generator.py",
        "leverage": "HIGHEST"
    },
    {
        "name": "G_ZONING_SETUP",
        "description": "Setup zoning data for orange/collier/pinellas/gulf",  
        "estimated_hours": 1.5,
        "script": "shard13_g_zoning_setup.py",
        "leverage": "HIGH"
    },
    {
        "name": "I_PROPERTY_CARDS", 
        "description": "Property card completion (depends on G)",
        "estimated_hours": 1.0,
        "script": "shard13_i_property_cards.py",
        "leverage": "MEDIUM"
    },
    {
        "name": "B_VERIFIED_OUTCOMES",
        "description": "Independent verified outcomes data sources",
        "estimated_hours": 1.5,
        "script": "shard13_b_verified_outcomes.py", 
        "leverage": "MEDIUM"
    },
    {
        "name": "CD_PARITY_FIX",
        "description": "PropertyOnion supplementary litmus for C/D",
        "estimated_hours": 1.0,
        "script": "shard13_cd_parity_fix.py",
        "leverage": "LOW"
    }
]

if CLIENT_AVAILABLE:
    client = httpx.Client(timeout=90)
else:
    import requests
    client = requests.Session()

def log(message, level="INFO"):
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"[{timestamp}] {level}: {message}")
    if level == "ERROR":
        logger.error(message)
    else:
        logger.info(message)

def make_request(method, url, **kwargs):
    """Unified request method that works with both httpx and requests"""
    kwargs['headers'] = HEADERS
    if CLIENT_AVAILABLE:
        if method == 'GET':
            return client.get(url, **kwargs)
        elif method == 'POST':
            return client.post(url, **kwargs)
    else:
        kwargs['timeout'] = 90
        if method == 'GET':
            return requests.get(url, **kwargs)
        elif method == 'POST':
            return requests.post(url, **kwargs)

def run_verification_protocol():
    """Run verification protocol with before/after metrics per brief requirement"""
    log("🔍 VERIFICATION PROTOCOL: Running pencil_dod_evaluate_county for all target counties")
    
    verification_results = {
        "protocol_start": datetime.now(timezone.utc).isoformat(),
        "target_counties": TARGET_COUNTIES,
        "before_metrics": {},
        "verification_status": "IN_PROGRESS"
    }
    
    for county in TARGET_COUNTIES:
        try:
            # Try both parameter patterns
            for param_name in ["county_slug_arg", "county_name"]:
                payload = {param_name: county}
                response = make_request('POST', f"{BASE}/rpc/pencil_dod_evaluate_county", json=payload)
                
                if response.status_code == 200:
                    evaluation = response.json()
                    
                    # Parse evaluation results
                    county_metrics = {}
                    total_pass = 0
                    
                    if isinstance(evaluation, list):
                        for item in evaluation:
                            letter = item.get('letter', '?')
                            metric = item.get('metric')
                            passed = item.get('pass', False)
                            context = item.get('context', {})
                            
                            county_metrics[f"letter_{letter.lower()}"] = {
                                "metric": metric,
                                "pass": passed,
                                "context": context
                            }
                            
                            if passed:
                                total_pass += 1
                    
                    verification_results["before_metrics"][county] = {
                        "total_pass": total_pass,
                        "letters": county_metrics,
                        "evaluation_timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    
                    log(f"✅ {county}: {total_pass}/10 letters passing")
                    break
                else:
                    log(f"⚠️ {county}: {param_name} failed with {response.status_code}")
        
        except Exception as e:
            log(f"❌ Error evaluating {county}: {e}", "ERROR")
            verification_results["before_metrics"][county] = {"error": str(e)}
    
    verification_results["verification_status"] = "COMPLETED"
    return verification_results

def execute_task(task_info):
    """Execute a single priority task"""
    task_name = task_info["name"]
    script_path = f"scripts/{task_info['script']}"
    
    log(f"🚀 EXECUTING: {task_name} - {task_info['description']}")
    log(f"   Estimated hours: {task_info['estimated_hours']}")
    log(f"   Leverage: {task_info['leverage']}")
    
    start_time = datetime.now(timezone.utc)
    
    # Check if script exists
    if not os.path.exists(script_path):
        log(f"❌ Script not found: {script_path}", "ERROR")
        log(f"   Creating stub script for {task_name}")
        create_stub_script(task_info)
        return False
    
    try:
        # Execute the script
        result = subprocess.run([
            sys.executable, script_path
        ], capture_output=True, text=True, timeout=task_info['estimated_hours'] * 3600)
        
        duration = datetime.now(timezone.utc) - start_time
        
        if result.returncode == 0:
            log(f"✅ {task_name} completed successfully in {duration.total_seconds()/60:.1f} minutes")
            log(f"   STDOUT: {result.stdout[-500:]}")  # Last 500 chars
            return True
        else:
            log(f"❌ {task_name} failed with return code {result.returncode}", "ERROR")
            log(f"   STDERR: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        log(f"⏰ {task_name} timed out after {task_info['estimated_hours']} hours", "ERROR")
        return False
    except Exception as e:
        log(f"❌ {task_name} execution error: {e}", "ERROR")
        return False

def create_stub_script(task_info):
    """Create a stub script for missing task scripts"""
    script_path = f"scripts/{task_info['script']}"
    
    stub_content = f'''#!/usr/bin/env python3
"""
{task_info["name"]} - {task_info["description"]}
SHARD-13 Implementation

TODO: Implement {task_info["description"]}
"""
import os
import sys
import json
from datetime import datetime, timezone

def main():
    print(f"=== {{task_info['name']}} STUB ===")
    print(f"Description: {{task_info['description']}}")
    print(f"Leverage: {{task_info['leverage']}}")
    print("❌ STUB ONLY - Implementation required")
    
    # TODO: Implement actual functionality
    return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
'''
    
    os.makedirs(os.path.dirname(script_path), exist_ok=True)
    with open(script_path, 'w') as f:
        f.write(stub_content)
    
    os.chmod(script_path, 0o755)
    log(f"📝 Created stub script: {script_path}")

def main():
    parser = argparse.ArgumentParser(description='SHARD-13 Master Execution Coordinator')
    parser.add_argument('--verify-only', action='store_true', help='Only run verification protocol')
    parser.add_argument('--execute-all', action='store_true', help='Execute all tasks without time limits')
    parser.add_argument('--task', type=str, help='Execute specific task only')
    
    args = parser.parse_args()
    
    log("=== SHARD-13 MASTER COORDINATOR START ===")
    log(f"Target counties: {', '.join(TARGET_COUNTIES)}")
    log(f"Session start: {SESSION_START.isoformat()}")
    log(f"Max session hours: {MAX_SESSION_HOURS}")
    
    # Check API key
    if not SUPABASE_KEY:
        log("❌ No Supabase API key found in environment", "ERROR")
        return False
    
    # Run initial verification
    log("\n🔍 INITIAL VERIFICATION PROTOCOL")
    initial_metrics = run_verification_protocol()
    
    if args.verify_only:
        log("✅ Verification-only mode completed")
        return True
    
    # Execute priority tasks
    log("\n🎯 PRIORITY TASK EXECUTION")
    
    elapsed_hours = 0
    completed_tasks = []
    failed_tasks = []
    
    for task_info in PRIORITY_TASKS:
        if args.task and task_info["name"] != args.task:
            continue
            
        # Check time remaining
        if not args.execute_all:
            if elapsed_hours + task_info["estimated_hours"] > MAX_SESSION_HOURS:
                log(f"⏰ Insufficient time for {task_info['name']} ({task_info['estimated_hours']}h), skipping")
                continue
        
        # Execute task
        task_start = datetime.now(timezone.utc)
        success = execute_task(task_info)
        task_duration = (datetime.now(timezone.utc) - task_start).total_seconds() / 3600
        
        if success:
            completed_tasks.append(task_info["name"])
        else:
            failed_tasks.append(task_info["name"])
        
        elapsed_hours += task_duration
        
        # Early exit if single task mode
        if args.task:
            break
    
    # Final verification
    log("\n🔍 FINAL VERIFICATION PROTOCOL")
    final_metrics = run_verification_protocol()
    
    # Summary
    log("\n📊 SESSION SUMMARY")
    log(f"Total elapsed: {elapsed_hours:.1f} hours")
    log(f"Completed tasks: {completed_tasks}")
    log(f"Failed tasks: {failed_tasks}")
    
    # Compare before/after metrics
    for county in TARGET_COUNTIES:
        initial = initial_metrics.get("before_metrics", {}).get(county, {})
        final = final_metrics.get("before_metrics", {}).get(county, {})
        
        if initial and final and not isinstance(initial, dict) or "error" not in initial:
            initial_pass = initial.get("total_pass", 0)
            final_pass = final.get("total_pass", 0)
            delta = final_pass - initial_pass
            
            log(f"{county}: {initial_pass}/10 → {final_pass}/10 (Δ{delta:+d})")
    
    log("=== SHARD-13 MASTER COORDINATOR COMPLETE ===")
    return len(failed_tasks) == 0

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)