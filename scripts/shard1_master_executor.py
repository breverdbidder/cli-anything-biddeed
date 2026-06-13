#!/usr/bin/env python3
"""
SHARD-1 MASTER EXECUTOR: Gold Standard Campaign Session Controller
Counties: charlotte, palm_beach, hendry, st_johns, hardee

WIRING MANDATE (per briefing):
"Code that is not SCHEDULED is dead code and scores zero. Every scraper/pipeline 
you ship MUST be wired to an executor in the same session."

EXECUTION ORDER (criterion-parallel per briefing):
1. J GENERATOR - bid_decisions pipeline (highest leverage: +10 points)
2. B VERIFICATION - independent outcomes verification (+10 points) 
3. E LINKAGE - parcel ID via ArcGIS FeatureServer (+10 points)
4. VERIFICATION PROTOCOL - fresh metrics evaluation

VERIFICATION PROTOCOL (mandatory per briefing):
- After each fix: SELECT public.pencil_dod_evaluate_county('<county>')
- Session end: SET statement_timeout=0; SELECT public.gold_standard_loop()
"""
import os
import sys
import json
import httpx
import subprocess
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# SHARD-1 counties
TARGET_COUNTIES = ['charlotte', 'palm_beach', 'hendry', 'st_johns', 'hardee']

# Pipeline scripts
PIPELINE_SCRIPTS = [
    {
        'name': 'J_GENERATOR',
        'script': 'scripts/shard1_j_generator.py',
        'description': 'bid_decisions pipeline - highest leverage (+10 points)',
        'target_letters': ['J']
    },
    {
        'name': 'B_VERIFICATION', 
        'script': 'scripts/shard1_b_verification.py',
        'description': 'Independent outcomes verification (+10 points)',
        'target_letters': ['B', 'F']  # F follows B automatically
    },
    {
        'name': 'E_LINKAGE',
        'script': 'scripts/shard1_e_linkage.py', 
        'description': 'Parcel ID linkage via ArcGIS (+10 points)',
        'target_letters': ['E', 'I']  # I depends on E
    }
]

def log(message, level="INFO"):
    """Enhanced logging with Honesty Protocol markers"""
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"[{timestamp}] {level}: {message}")
    if level == "ERROR":
        logger.error(message)
    else:
        logger.info(message)

def get_headers():
    """Get Supabase headers with authentication"""
    if not SUPABASE_KEY:
        log("ERROR: No Supabase service key found in environment", "ERROR")
        return None
    
    return {
        "apikey": SUPABASE_KEY, 
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def verify_database_connection():
    """Test Supabase connection"""
    try:
        client = httpx.Client(timeout=60)
        headers = get_headers()
        if not headers:
            return False
            
        response = client.get(f"{SUPABASE_URL}/rest/v1/audit_log", headers=headers, params={"limit": "1"})
        if response.status_code == 200:
            log("✅ VERIFIED: Database connection successful")
            return True
        else:
            log(f"❌ VERIFIED: Database connection failed: {response.status_code}")
            return False
    except Exception as e:
        log(f"❌ VERIFIED: Database connection error: {e}", "ERROR")
        return False

def evaluate_county_metrics(county_slug: str) -> Dict:
    """Execute pencil_dod_evaluate_county for verification"""
    try:
        client = httpx.Client(timeout=120)
        headers = get_headers()
        if not headers:
            return {"error": "No database headers"}
        
        # Use the evaluation function  
        payload = {"county_slug_arg": county_slug}
        response = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=headers,
            json=payload
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # Parse results into letter grades
            letter_results = {}
            pass_count = 0
            
            if isinstance(result, list):
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    passes = letter_data.get('pass', False)
                    details = letter_data.get('details', '')
                    
                    letter_results[letter] = {
                        'metric': metric,
                        'pass': passes,
                        'details': details
                    }
                    
                    if passes:
                        pass_count += 1
            
            log(f"✅ VERIFIED: {county_slug} evaluation complete - {pass_count}/10 passing")
            return {
                "status": "success",
                "county": county_slug,
                "pass_count": pass_count,
                "letters": letter_results,
                "evaluation_timestamp": datetime.now(timezone.utc).isoformat()
            }
        else:
            log(f"❌ VERIFIED: {county_slug} evaluation failed: {response.status_code}")
            return {"error": f"HTTP {response.status_code}"}
            
    except Exception as e:
        log(f"❌ VERIFIED: {county_slug} evaluation error: {e}", "ERROR")
        return {"error": str(e)}

def execute_pipeline(pipeline_info: Dict) -> Dict:
    """Execute a single pipeline script"""
    script_name = pipeline_info['name']
    script_path = pipeline_info['script']
    
    log(f"🚀 Executing pipeline: {script_name}")
    log(f"   Description: {pipeline_info['description']}")
    log(f"   Target letters: {', '.join(pipeline_info['target_letters'])}")
    
    start_time = time.time()
    
    try:
        # Check if script exists
        if not os.path.exists(script_path):
            log(f"❌ VERIFIED: Script not found: {script_path}", "ERROR")
            return {
                "status": "error",
                "error": f"Script not found: {script_path}",
                "execution_time": 0
            }
        
        # Execute the script
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=1800,  # 30 minute timeout
            cwd=os.path.dirname(os.path.dirname(script_path))  # Run from repo root
        )
        
        execution_time = time.time() - start_time
        
        if result.returncode == 0:
            log(f"✅ VERIFIED: {script_name} completed successfully in {execution_time:.1f}s")
            return {
                "status": "success",
                "execution_time": execution_time,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        else:
            log(f"❌ VERIFIED: {script_name} failed with return code {result.returncode}", "ERROR")
            log(f"   STDERR: {result.stderr}")
            return {
                "status": "failed",
                "execution_time": execution_time, 
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
            
    except subprocess.TimeoutExpired:
        log(f"❌ VERIFIED: {script_name} timed out after 30 minutes", "ERROR")
        return {
            "status": "timeout",
            "execution_time": 1800,
            "error": "Execution timeout"
        }
    except Exception as e:
        execution_time = time.time() - start_time
        log(f"❌ VERIFIED: {script_name} execution error: {e}", "ERROR")
        return {
            "status": "error",
            "execution_time": execution_time,
            "error": str(e)
        }

def run_verification_protocol() -> Dict:
    """Execute verification protocol per briefing requirements"""
    log("📈 VERIFIED: Running verification protocol for all SHARD-1 counties")
    
    verification_results = {
        "verification_timestamp": datetime.now(timezone.utc).isoformat(),
        "county_evaluations": {},
        "summary": {
            "total_counties": len(TARGET_COUNTIES),
            "total_points": 0,
            "counties_passing": [],
            "counties_failing": []
        }
    }
    
    # Evaluate each county
    for county in TARGET_COUNTIES:
        log(f"🔍 Evaluating county: {county}")
        evaluation = evaluate_county_metrics(county)
        verification_results["county_evaluations"][county] = evaluation
        
        if evaluation.get("status") == "success":
            pass_count = evaluation.get("pass_count", 0)
            verification_results["summary"]["total_points"] += pass_count
            
            if pass_count >= 8:  # Consider 8+ as strong performance
                verification_results["summary"]["counties_passing"].append(county)
            else:
                verification_results["summary"]["counties_failing"].append(county)
    
    # Calculate overall improvement
    total_possible = len(TARGET_COUNTIES) * 10
    current_total = verification_results["summary"]["total_points"]
    completion_percentage = (current_total / total_possible) * 100
    
    verification_results["summary"]["completion_percentage"] = round(completion_percentage, 1)
    verification_results["summary"]["points_gained"] = "UNKNOWN - baseline comparison needed"
    
    log(f"📊 VERIFIED: Verification complete")
    log(f"   Total points: {current_total}/{total_possible} ({completion_percentage:.1f}%)")
    log(f"   Strong performers: {verification_results['summary']['counties_passing']}")
    log(f"   Need improvement: {verification_results['summary']['counties_failing']}")
    
    return verification_results

def execute_gold_standard_loop():
    """Execute gold_standard_loop() per briefing requirements"""
    log("🎯 VERIFIED: Executing gold_standard_loop() for final scoring")
    
    try:
        client = httpx.Client(timeout=300)  # 5 minute timeout
        headers = get_headers()
        if not headers:
            return {"error": "No database headers"}
        
        # Set statement timeout first
        timeout_response = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
            headers=headers,
            json={"sql_text": "SET statement_timeout = 0;"}
        )
        
        if timeout_response.status_code != 200:
            log(f"⚠️ VERIFIED: Failed to set statement timeout: {timeout_response.status_code}")
        
        # Execute the gold standard loop
        loop_response = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/gold_standard_loop",
            headers=headers,
            json={}
        )
        
        if loop_response.status_code == 200:
            result = loop_response.json()
            log("✅ VERIFIED: gold_standard_loop() executed successfully")
            return {
                "status": "success",
                "result": result,
                "execution_timestamp": datetime.now(timezone.utc).isoformat()
            }
        else:
            log(f"❌ VERIFIED: gold_standard_loop() failed: {loop_response.status_code}")
            return {
                "status": "failed",
                "error": f"HTTP {loop_response.status_code}: {loop_response.text}"
            }
            
    except Exception as e:
        log(f"❌ VERIFIED: gold_standard_loop() error: {e}", "ERROR")
        return {"status": "error", "error": str(e)}

def main():
    """Main executor for SHARD-1 Gold Standard Campaign session"""
    session_start = datetime.now(timezone.utc)
    log("🎯 SHARD-1 MASTER EXECUTOR - GOLD STANDARD CAMPAIGN RUN 23")
    log(f"   Session start: {session_start.isoformat()}")
    log(f"   Target counties: {', '.join(TARGET_COUNTIES)}")
    log(f"   Ship-to-main mandate: Direct commits, no PRs")
    
    session_results = {
        "session_start": session_start.isoformat(),
        "shard": "SHARD-1",
        "target_counties": TARGET_COUNTIES,
        "ship_to_main": True,
        "pipeline_results": {},
        "verification_results": {},
        "session_summary": {}
    }
    
    try:
        # Phase 1: Verify database connection
        if not verify_database_connection():
            session_results["status"] = "FAILED"
            session_results["error"] = "Database connection failed"
            return session_results
        
        # Phase 2: Get baseline metrics
        log("📊 Phase 2: Capturing baseline metrics")
        baseline_verification = run_verification_protocol()
        session_results["baseline_metrics"] = baseline_verification
        
        # Phase 3: Execute pipelines in sequence
        log("🚀 Phase 3: Executing pipelines")
        pipeline_success_count = 0
        
        for pipeline in PIPELINE_SCRIPTS:
            pipeline_result = execute_pipeline(pipeline)
            session_results["pipeline_results"][pipeline['name']] = pipeline_result
            
            if pipeline_result.get("status") == "success":
                pipeline_success_count += 1
                log(f"✅ Pipeline {pipeline['name']} completed successfully")
            else:
                log(f"❌ Pipeline {pipeline['name']} failed")
            
            # Brief pause between pipelines
            time.sleep(5)
        
        # Phase 4: Final verification protocol
        log("📈 Phase 4: Final verification protocol")
        final_verification = run_verification_protocol()
        session_results["final_verification"] = final_verification
        
        # Phase 5: Execute gold standard loop
        log("🎯 Phase 5: Gold standard loop execution")
        loop_result = execute_gold_standard_loop()
        session_results["gold_standard_loop"] = loop_result
        
        # Calculate session summary
        session_end = datetime.now(timezone.utc)
        session_duration = (session_end - session_start).total_seconds() / 60
        
        baseline_points = baseline_verification["summary"].get("total_points", 0)
        final_points = final_verification["summary"].get("total_points", 0)
        points_gained = final_points - baseline_points
        
        session_results["session_summary"] = {
            "session_end": session_end.isoformat(),
            "session_duration_minutes": round(session_duration, 1),
            "pipelines_executed": len(PIPELINE_SCRIPTS),
            "pipelines_successful": pipeline_success_count,
            "baseline_points": baseline_points,
            "final_points": final_points,
            "points_gained": points_gained,
            "completion_status": "COMPLETE" if pipeline_success_count == len(PIPELINE_SCRIPTS) else "PARTIAL"
        }
        
        # Save full results
        results_file = "/tmp/shard1_master_executor_results.json"
        with open(results_file, "w") as f:
            json.dump(session_results, f, indent=2, default=str)
        
        # Output summary
        print("\n" + "="*80)
        print("SHARD-1 GOLD STANDARD CAMPAIGN SESSION COMPLETE")
        print("="*80)
        print(f"Duration: {session_duration:.1f} minutes")
        print(f"Pipelines: {pipeline_success_count}/{len(PIPELINE_SCRIPTS)} successful")
        print(f"Points: {baseline_points} → {final_points} (+{points_gained})")
        print(f"Status: {session_results['session_summary']['completion_status']}")
        print("\nDetailed results saved to:", results_file)
        
        log("🏁 SHARD-1 Master Executor session complete")
        return session_results
        
    except Exception as e:
        log(f"CRITICAL SESSION ERROR: {e}", "ERROR")
        session_results["status"] = "CRITICAL_ERROR"
        session_results["error"] = str(e)
        return session_results

if __name__ == "__main__":
    main()