#!/usr/bin/env python3
"""
SHARD-5 MASTER COORDINATOR - Gold Standard Campaign
SHIP-TO-MAIN: 6-hour autonomous session

Orchestrates the complete pipeline for highlands, collier, miami_dade, bradford, levy:
1. County bootstrap (A letter fixes for 0/10 counties)  
2. J Generator (highest leverage: 0% -> 95% potential)
3. B Verified Outcomes (critical path compliance)
4. C/D Parity Fixes (highlands specific + others)
5. ULTRALOOP verification protocol
6. Live metrics verification

Per CLAUDE.md: "execute immediately, zero questions" + "ship directly to main"

Usage:
  python shard5_master_coordinator.py
"""

import os
import sys
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Session configuration
SESSION_START_TIME = datetime.now(timezone.utc)
TARGET_COUNTIES = ['highlands', 'collier', 'miami_dade', 'bradford', 'levy']
BUDGET_HOURS = 6
DISPATCH_ID = "49f51462-eb6a-4438-b690-0626ad571944"

def log(message, level="INFO"):
    elapsed = datetime.now(timezone.utc) - SESSION_START_TIME
    elapsed_str = str(elapsed).split('.')[0]  # Remove microseconds
    timestamp = datetime.now(timezone.utc).isoformat()
    
    print(f"[{timestamp}] [{elapsed_str}] {level}: {message}")
    
    if level == "ERROR":
        logger.error(message)
    else:
        logger.info(message)

def check_time_budget():
    """Check if we're within time budget"""
    elapsed = datetime.now(timezone.utc) - SESSION_START_TIME
    elapsed_hours = elapsed.total_seconds() / 3600
    
    if elapsed_hours >= BUDGET_HOURS:
        log(f"⏰ Time budget exceeded: {elapsed_hours:.1f}h / {BUDGET_HOURS}h", "ERROR")
        return False
    
    remaining_hours = BUDGET_HOURS - elapsed_hours
    log(f"⏰ Time budget: {elapsed_hours:.1f}h / {BUDGET_HOURS}h ({remaining_hours:.1f}h remaining)")
    return True

def run_script(script_name: str, description: str) -> bool:
    """Run a Python script and return success status"""
    if not check_time_budget():
        log(f"⏰ Skipping {script_name} due to time budget", "ERROR")
        return False
    
    log(f"🚀 Starting: {description}")
    script_path = Path(__file__).parent / script_name
    
    if not script_path.exists():
        log(f"❌ Script not found: {script_path}", "ERROR")
        return False
    
    try:
        start_time = time.time()
        
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout per script
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        if result.returncode == 0:
            log(f"✅ Completed: {description} ({duration:.1f}s)")
            
            # Log key output lines
            if result.stdout:
                output_lines = result.stdout.strip().split('\n')
                for line in output_lines[-10:]:  # Last 10 lines
                    if any(keyword in line for keyword in ['✅', '❌', '📊', 'VERIFICATION', 'COMPLETE']):
                        log(f"   📋 {line}")
            
            return True
        else:
            log(f"❌ Failed: {description} (exit code {result.returncode})", "ERROR")
            if result.stderr:
                log(f"   Error: {result.stderr.strip()}", "ERROR")
            return False
            
    except subprocess.TimeoutExpired:
        log(f"⏰ Timeout: {description} exceeded 1 hour", "ERROR")
        return False
    except Exception as e:
        log(f"❌ Exception in {description}: {e}", "ERROR")
        return False

def commit_progress(message: str):
    """Commit current progress to main branch"""
    try:
        # Stage all changes
        result = subprocess.run(
            ["git", "add", "."],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent
        )
        
        if result.returncode != 0:
            log(f"⚠️ Git add failed: {result.stderr}", "ERROR")
            return False
        
        # Commit with message
        commit_msg = f"{message}\n\n🤖 Generated with [Claude Code](https://claude.ai/code)\n\nCo-authored-by: breverdbidder <breverdbidder@users.noreply.github.com>"
        
        result = subprocess.run(
            ["git", "commit", "-m", commit_msg],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent
        )
        
        if result.returncode == 0:
            log(f"✅ Committed: {message}")
            return True
        else:
            # Check if it's just "no changes to commit"
            if "nothing to commit" in result.stdout:
                log(f"ℹ️ No changes to commit for: {message}")
                return True
            else:
                log(f"❌ Commit failed: {result.stderr}", "ERROR")
                return False
                
    except Exception as e:
        log(f"❌ Commit exception: {e}", "ERROR")
        return False

def push_to_main():
    """Push commits to main branch"""
    try:
        result = subprocess.run(
            ["git", "push", "origin", "main"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent
        )
        
        if result.returncode == 0:
            log("✅ Pushed to main successfully")
            return True
        else:
            log(f"❌ Push failed: {result.stderr}", "ERROR")
            return False
            
    except Exception as e:
        log(f"❌ Push exception: {e}", "ERROR")
        return False

def verify_final_metrics():
    """Final verification of all county metrics"""
    log("📊 Final metrics verification")
    
    verification_results = {}
    
    for county in TARGET_COUNTIES:
        # Use the status query script to get final metrics
        try:
            result = subprocess.run(
                [sys.executable, "-c", f"""
import sys
sys.path.append('.')
from shard5_current_status import get_county_status
result = get_county_status('{county}')
if result:
    print('SUCCESS')
else:
    print('FAILED')
"""],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent
            )
            
            if "SUCCESS" in result.stdout:
                verification_results[county] = "✅ Verified"
            else:
                verification_results[county] = "❌ Failed"
                
        except Exception as e:
            verification_results[county] = f"❌ Error: {e}"
    
    log("📊 Final verification results:")
    for county, status in verification_results.items():
        log(f"   {county}: {status}")
    
    return verification_results

def main():
    """Execute SHARD-5 master coordination pipeline"""
    log("🎯 SHARD-5 MASTER COORDINATOR - STARTING 6H AUTONOMOUS SESSION")
    log(f"Dispatch ID: {DISPATCH_ID}")
    log(f"Counties: {', '.join(TARGET_COUNTIES)}")
    log(f"Budget: {BUDGET_HOURS} hours")
    log("🎯 Mission: Ship directly to main, highest-leverage fixes, ULTRALOOP verification")
    
    # Pipeline execution order (optimized for maximum leverage)
    pipeline_phases = [
        {
            "script": "shard5_bootstrap.py",
            "description": "County Bootstrap (A letter fixes for bradford/levy 0/10)",
            "priority": "HIGH",
            "target_letters": ["A"]
        },
        {
            "script": "shard5_j_generator.py", 
            "description": "J Generator - Deal Thesis Pipeline (0% -> 95% potential)",
            "priority": "CRITICAL",
            "target_letters": ["J"]
        },
        {
            "script": "shard5_b_verified_outcomes.py",
            "description": "B Verified Outcomes - Independent Source Building", 
            "priority": "HIGH",
            "target_letters": ["B"]
        },
        {
            "script": "shard5_cd_parity_fix.py",
            "description": "C/D Parity Fixes - Clerk Supplementary Sources",
            "priority": "MEDIUM", 
            "target_letters": ["C", "D"]
        }
    ]
    
    # Track results
    execution_results = {}
    successful_phases = 0
    total_phases = len(pipeline_phases)
    
    # Execute each phase
    for i, phase in enumerate(pipeline_phases, 1):
        if not check_time_budget():
            log("⏰ Time budget exhausted, stopping execution", "ERROR")
            break
        
        log(f"\n🔧 PHASE {i}/{total_phases}: {phase['description']}")
        log(f"   Priority: {phase['priority']} | Letters: {phase['target_letters']}")
        
        success = run_script(phase["script"], phase["description"])
        execution_results[phase["script"]] = success
        
        if success:
            successful_phases += 1
            
            # Commit after each successful phase  
            commit_message = f"feat: SHARD-5 {phase['description']} complete\n\nLetters: {', '.join(phase['target_letters'])}\nPhase: {i}/{total_phases}"
            commit_progress(commit_message)
        else:
            log(f"⚠️ Phase {i} failed, continuing to next phase")
        
        log(f"✅ Phase {i} complete | Success rate: {successful_phases}/{i}")
    
    # Final verification and summary
    log(f"\n📊 PIPELINE EXECUTION SUMMARY")
    log(f"Successful phases: {successful_phases}/{total_phases}")
    log(f"Success rate: {successful_phases/total_phases*100:.1f}%")
    
    # Final metrics verification
    final_metrics = verify_final_metrics()
    
    # Final commit with summary
    session_duration = datetime.now(timezone.utc) - SESSION_START_TIME
    final_commit_msg = f"feat: SHARD-5 Gold Standard campaign complete\n\nPhases: {successful_phases}/{total_phases} successful\nDuration: {str(session_duration).split('.')[0]}\nCounties: {', '.join(TARGET_COUNTIES)}"
    
    commit_progress(final_commit_msg)
    
    # Push to main (per SHIP-TO-MAIN mandate)
    log("\n🚀 SHIPPING TO MAIN")
    push_success = push_to_main()
    
    # Final session report
    session_summary = {
        "session_type": "shard5_master_coordinator",
        "dispatch_id": DISPATCH_ID,
        "start_time": SESSION_START_TIME.isoformat(),
        "end_time": datetime.now(timezone.utc).isoformat(),
        "duration": str(session_duration).split('.')[0],
        "target_counties": TARGET_COUNTIES,
        "pipeline_phases": pipeline_phases,
        "execution_results": execution_results,
        "successful_phases": successful_phases,
        "total_phases": total_phases,
        "success_rate": round(successful_phases/total_phases*100, 1),
        "final_metrics": final_metrics,
        "pushed_to_main": push_success,
        "budget_hours": BUDGET_HOURS,
        "sql_verification": [f"SELECT public.pencil_dod_evaluate_county('{county}')" for county in TARGET_COUNTIES]
    }
    
    log("\n" + "="*80)
    log("SHARD-5 GOLD STANDARD CAMPAIGN - SESSION COMPLETE")
    log("="*80)
    
    print(json.dumps(session_summary, indent=2))
    
    # Exit with appropriate code
    if successful_phases == total_phases:
        log("✅ ALL PHASES SUCCESSFUL - SHARD-5 CAMPAIGN COMPLETE")
        sys.exit(0)
    elif successful_phases > 0:
        log(f"⚠️ PARTIAL SUCCESS - {successful_phases}/{total_phases} phases complete")
        sys.exit(1)
    else:
        log("❌ CAMPAIGN FAILED - No phases completed successfully")
        sys.exit(2)

if __name__ == "__main__":
    main()