#!/usr/bin/env python3
"""
SHARD-6 Master Coordinator - Autonomous Gold Standard Campaign
SHIP-TO-MAIN SESSION - RUN 23

Coordinates execution of all SHARD-6 fixes based on priority order from the brief:
1. C/D parity fixes (escambia, martin, calhoun) - highest leverage
2. A-lane configuration (suwannee, calhoun, liberty) - enables other metrics
3. E parcel linkage (all counties) - moderate leverage  
4. J generator (all counties) - pipeline enabler

Counties: escambia, suwannee, martin, calhoun, liberty

Per brief SHIP-TO-MAIN MANDATE:
- Commit and push DIRECTLY TO MAIN. Do NOT create side branches.
- Database changes ship as Supabase migrations applied LIVE during the session.
- "Done" is defined ONLY by the live scoreboard metrics moving.

Usage:
  python scripts/shard6_master_coordinator.py
"""
import os
import sys
import json
import subprocess
import httpx
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import time

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
    "Content-Type": "application/json"
}

SHARD6_COUNTIES = ['escambia', 'suwannee', 'martin', 'calhoun', 'liberty']

client = httpx.Client(timeout=120)

def log(message, level="INFO"):
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"[{timestamp}] {level}: {message}")
    if level == "ERROR":
        logger.error(message)
    else:
        logger.info(message)

def run_script(script_path: str, description: str) -> Dict:
    """Execute a Python script and return results"""
    log(f"Running {description}...")
    
    try:
        start_time = time.time()
        result = subprocess.run(
            [sys.executable, script_path], 
            capture_output=True, 
            text=True,
            timeout=1800  # 30 minute timeout
        )
        duration = time.time() - start_time
        
        success = result.returncode == 0
        
        execution_result = {
            "script": script_path,
            "description": description,
            "success": success,
            "duration_seconds": round(duration, 1),
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        if success:
            log(f"✅ {description} completed in {duration:.1f}s")
        else:
            log(f"❌ {description} failed (exit code {result.returncode})", "ERROR")
            if result.stderr:
                log(f"Error output: {result.stderr}", "ERROR")
        
        return execution_result
        
    except subprocess.TimeoutExpired:
        log(f"❌ {description} timed out after 30 minutes", "ERROR")
        return {
            "script": script_path,
            "description": description,
            "success": False,
            "error": "timeout",
            "duration_seconds": 1800,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        log(f"❌ {description} failed with exception: {e}", "ERROR")
        return {
            "script": script_path,
            "description": description,
            "success": False,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

def get_baseline_metrics() -> Dict:
    """Get baseline metrics for all SHARD-6 counties before fixes"""
    log("Getting baseline metrics for all SHARD-6 counties...")
    
    baseline = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'counties': {}
    }
    
    for county in SHARD6_COUNTIES:
        try:
            response = client.post(
                f"{BASE}/rpc/pencil_dod_evaluate_county",
                headers=HEADERS,
                json={"county_slug_arg": county},
                timeout=30
            )
            
            if response.status_code == 200:
                evaluation = response.json()
                
                # Parse evaluation into letter grades
                letters = {}
                pass_count = 0
                
                if isinstance(evaluation, list):
                    for letter_data in evaluation:
                        if isinstance(letter_data, dict):
                            letter = letter_data.get('letter', '').upper()
                            is_pass = letter_data.get('pass', False)
                            metric = letter_data.get('metric')
                            
                            letters[letter] = {
                                'pass': is_pass,
                                'metric': metric,
                                'details': letter_data.get('details', '')
                            }
                            
                            if is_pass:
                                pass_count += 1
                
                baseline['counties'][county] = {
                    'letters': letters,
                    'pass_count': pass_count,
                    'total_letters': len(letters),
                    'score': f"{pass_count}/{len(letters)}"
                }
                
                log(f"{county} baseline: {pass_count}/{len(letters)}")
            else:
                log(f"Failed to get baseline for {county}: {response.text}", "ERROR")
                
        except Exception as e:
            log(f"Error getting baseline for {county}: {e}", "ERROR")
    
    return baseline

def commit_changes(message: str, files: List[str] = None) -> Dict:
    """Commit changes to main branch per SHIP-TO-MAIN mandate"""
    log(f"Committing changes: {message}")
    
    try:
        # Git add
        if files:
            for file in files:
                subprocess.run(["git", "add", file], check=True)
        else:
            subprocess.run(["git", "add", "-A"], check=True)
        
        # Git commit with descriptive message and co-author
        commit_result = subprocess.run([
            "git", "commit", "-m", 
            f"{message}\n\n🤖 Generated with [Claude Code](https://claude.ai/code)\n\nCo-authored-by: breverdbidder <breverdbidder@users.noreply.github.com>"
        ], capture_output=True, text=True)
        
        # Git push to main
        if commit_result.returncode == 0:
            push_result = subprocess.run(["git", "push", "origin", "main"], 
                                       capture_output=True, text=True)
            
            if push_result.returncode == 0:
                log(f"✅ Successfully committed and pushed to main")
                return {"success": True, "message": message}
            else:
                log(f"❌ Failed to push to main: {push_result.stderr}", "ERROR")
                return {"success": False, "error": push_result.stderr}
        else:
            if "nothing to commit" in commit_result.stdout:
                log("No changes to commit")
                return {"success": True, "message": "No changes"}
            else:
                log(f"❌ Failed to commit: {commit_result.stderr}", "ERROR")
                return {"success": False, "error": commit_result.stderr}
                
    except Exception as e:
        log(f"❌ Git operation failed: {e}", "ERROR")
        return {"success": False, "error": str(e)}

def verify_final_metrics() -> Dict:
    """Get final metrics after all fixes to verify improvements"""
    log("Getting final metrics to verify improvements...")
    
    # Same structure as baseline
    final = get_baseline_metrics()
    final['description'] = 'final_metrics_after_fixes'
    
    return final

def generate_session_summary(baseline: Dict, final: Dict, execution_results: List[Dict]) -> Dict:
    """Generate comprehensive session summary with before/after metrics"""
    
    summary = {
        'session_id': 'shard6_autonomous_run_23',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'duration_hours': None,
        'baseline_metrics': baseline,
        'final_metrics': final,
        'execution_results': execution_results,
        'county_improvements': {},
        'verification_evidence': {},
        'overall_success': False
    }
    
    # Calculate improvements for each county
    for county in SHARD6_COUNTIES:
        baseline_county = baseline.get('counties', {}).get(county, {})
        final_county = final.get('counties', {}).get(county, {})
        
        if baseline_county and final_county:
            baseline_pass = baseline_county.get('pass_count', 0)
            final_pass = final_county.get('pass_count', 0)
            improvement = final_pass - baseline_pass
            
            summary['county_improvements'][county] = {
                'baseline_score': baseline_county.get('score', 'unknown'),
                'final_score': final_county.get('score', 'unknown'),
                'pass_count_improvement': improvement,
                'letter_improvements': {}
            }
            
            # Track letter-level improvements
            baseline_letters = baseline_county.get('letters', {})
            final_letters = final_county.get('letters', {})
            
            for letter in 'ABCDEFGHIJ':
                if letter in baseline_letters and letter in final_letters:
                    baseline_pass = baseline_letters[letter]['pass']
                    final_pass = final_letters[letter]['pass']
                    
                    if not baseline_pass and final_pass:
                        summary['county_improvements'][county]['letter_improvements'][letter] = 'FAIL->PASS'
                    elif baseline_pass and not final_pass:
                        summary['county_improvements'][county]['letter_improvements'][letter] = 'PASS->FAIL'
            
            log(f"{county} improvement: {baseline_pass}->{final_pass} ({improvement:+d})")
    
    # Calculate overall success
    total_improvements = sum(imp.get('pass_count_improvement', 0) 
                           for imp in summary['county_improvements'].values())
    successful_scripts = sum(1 for result in execution_results if result.get('success'))
    
    summary['overall_success'] = total_improvements > 0 and successful_scripts >= 2
    
    # Add SQL verification evidence
    for county in SHARD6_COUNTIES:
        summary['verification_evidence'][county] = f"SELECT public.pencil_dod_evaluate_county('{county}')"
    
    return summary

def main():
    """
    Main execution function for SHARD-6 autonomous campaign
    Executes fixes in priority order and commits to main branch
    """
    session_start = datetime.now(timezone.utc)
    log("SHARD-6 Gold Standard Autonomous Campaign - RUN 23")
    log("SHIP-TO-MAIN Session - Direct commits, no PRs")
    log(f"Counties: {', '.join(SHARD6_COUNTIES)}")
    
    if not SUPABASE_KEY:
        log("❌ No SUPABASE_KEY found in environment", "ERROR")
        return False
    
    # Phase 1: Get baseline metrics
    baseline_metrics = get_baseline_metrics()
    
    # Phase 2: Execute fixes in priority order
    execution_sequence = [
        ("scripts/shard6_cd_parity_fix.py", "C/D Parity Fixes (Priority #1)"),
        ("scripts/shard6_configure_a_lanes.py", "A-Lane Configuration (Priority #2)"), 
        ("scripts/shard6_parcel_linkage.py", "E Parcel Linkage (Priority #3)"),
        ("scripts/shard6_j_generator.py", "J Generator Pipeline (Priority #4)")
    ]
    
    execution_results = []
    
    for script_path, description in execution_sequence:
        # Check if script exists
        if not os.path.exists(script_path):
            log(f"❌ Script not found: {script_path}", "ERROR")
            execution_results.append({
                "script": script_path,
                "description": description,
                "success": False,
                "error": "script_not_found"
            })
            continue
        
        # Execute script
        result = run_script(script_path, description)
        execution_results.append(result)
        
        # Commit changes after each successful script per SHIP-TO-MAIN
        if result.get('success'):
            commit_message = f"SHARD-6: {description}\n\nAutonomous session run 23 - {script_path}"
            commit_result = commit_changes(commit_message, [script_path])
            result['commit_result'] = commit_result
        
        # Brief pause between scripts
        time.sleep(5)
    
    # Phase 3: Get final metrics and verify improvements
    final_metrics = verify_final_metrics()
    
    # Phase 4: Generate comprehensive session summary
    session_summary = generate_session_summary(baseline_metrics, final_metrics, execution_results)
    session_summary['duration_hours'] = (datetime.now(timezone.utc) - session_start).total_seconds() / 3600
    
    # Phase 5: Commit session summary and final changes
    summary_path = '/tmp/shard6_session_summary.json'
    with open(summary_path, 'w') as f:
        json.dump(session_summary, f, indent=2)
    
    # Copy summary to repository for persistence
    repo_summary_path = f"reports/shard6_autonomous_run23_{session_start.strftime('%Y%m%d_%H%M%S')}.json"
    os.makedirs(os.path.dirname(repo_summary_path), exist_ok=True)
    with open(repo_summary_path, 'w') as f:
        json.dump(session_summary, f, indent=2)
    
    final_commit = commit_changes(
        "SHARD-6: Session summary and verification evidence\n\nComplete autonomous run 23 with metrics verification",
        [repo_summary_path]
    )
    
    # Final status report
    log(f"\n" + "="*80)
    log("SHARD-6 AUTONOMOUS CAMPAIGN SUMMARY")
    log("="*80)
    log(f"Session duration: {session_summary['duration_hours']:.1f} hours")
    log(f"Scripts executed: {len(execution_results)}")
    log(f"Successful scripts: {sum(1 for r in execution_results if r.get('success'))}")
    
    log(f"\nCounty Improvements:")
    for county, improvement in session_summary['county_improvements'].items():
        baseline = improvement['baseline_score']
        final = improvement['final_score'] 
        change = improvement['pass_count_improvement']
        status = f"{baseline} -> {final} ({change:+d})" if change != 0 else f"{baseline} (no change)"
        log(f"  {county}: {status}")
    
    overall_success = session_summary['overall_success']
    log(f"\nOverall Success: {'✅ YES' if overall_success else '❌ NO'}")
    
    log(f"\nSession summary saved: {repo_summary_path}")
    log(f"Verification evidence: {summary_path}")
    
    return session_summary

if __name__ == "__main__":
    try:
        results = main()
        log("✅ SHARD-6 autonomous campaign completed")
    except Exception as e:
        log(f"❌ SHARD-6 autonomous campaign failed: {e}", "ERROR")
        exit(1)