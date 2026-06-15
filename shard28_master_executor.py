#!/usr/bin/env python3
"""
SHARD-28 MASTER EXECUTOR: GOLD STANDARD AUTOPILOT
Autonomous 6-hour session for brevard and duval counties

SHIP-TO-MAIN MANDATE: Commit directly to main, no branches
PRIORITY ORDER:
1. C/D ROOT CAUSE - clerk/official-records supplementary litmus  
2. J GENERATOR - bid_decisions pipeline (0→95 biggest point gain)
3. B RECONCILIATION - Fix >100% anomaly  
4. Verification protocol with live DB queries

Session: db82988c-3cdf-45e2-a4ac-c4a100157b80
Counties: brevard (2/10), duval (2/10)
Target: Move both counties toward 10/10 certification
"""

import os
import sys
import json
import subprocess
import httpx
from datetime import datetime, timezone
from typing import Dict, List, Tuple

# Session configuration
SESSION_ID = "db82988c-3cdf-45e2-a4ac-c4a100157b80"
TARGET_COUNTIES = ["brevard", "duval"]
SESSION_START = datetime.now(timezone.utc)
MAX_SESSION_HOURS = 6

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "") or os.environ.get("SUPABASE_KEY", "")

def sb_headers():
    """Supabase request headers"""
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def check_session_time() -> Tuple[float, bool]:
    """Check elapsed session time and if we should continue"""
    elapsed = datetime.now(timezone.utc) - SESSION_START
    elapsed_hours = elapsed.total_seconds() / 3600
    should_continue = elapsed_hours < (MAX_SESSION_HOURS - 0.5)  # Leave 30min for closeout
    
    return elapsed_hours, should_continue

def log_session_progress(phase: str, status: str, details: str):
    """Log session progress to console and potentially to database"""
    elapsed_hours, _ = check_session_time()
    timestamp = datetime.now(timezone.utc).isoformat()
    
    print(f"[{elapsed_hours:.1f}h] {phase}: {status}")
    print(f"  Details: {details}")
    print(f"  Timestamp: {timestamp}")
    
    # Could also log to database here for session tracking

def run_python_script(script_path: str, description: str) -> Tuple[bool, str]:
    """Run a Python script and return success status and output"""
    print(f"\n🚀 Running: {description}")
    print(f"   Script: {script_path}")
    
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout per script
        )
        
        success = result.returncode == 0
        output = result.stdout if success else result.stderr
        
        if success:
            print("   ✅ SUCCESS")
        else:
            print(f"   ❌ FAILED (exit code: {result.returncode})")
            
        return success, output
        
    except subprocess.TimeoutExpired:
        return False, "Script timed out after 1 hour"
    except Exception as e:
        return False, f"Error running script: {e}"

def evaluate_county_live(county: str) -> Dict:
    """Run pencil_dod_evaluate_county for live verification"""
    print(f"\n🔍 Live evaluation: {county}")
    
    try:
        with httpx.Client(timeout=60) as client:
            response = client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
                headers=sb_headers(),
                json={"county_slug_arg": county}
            )
            response.raise_for_status()
            
            result = response.json()
            
            if isinstance(result, list) and len(result) > 0:
                # Calculate score
                pass_count = sum(1 for item in result if item.get('pass', False))
                total_letters = len(result)
                
                print(f"  📊 {county.upper()}: {pass_count}/{total_letters} ({pass_count/total_letters*100:.1f}%)")
                
                # Print letter breakdown
                for item in result:
                    letter = item.get('letter', '?')
                    metric = item.get('metric')
                    passed = item.get('pass', False)
                    
                    status = "✅" if passed else "❌"
                    metric_str = f"{metric:.1f}" if isinstance(metric, (int, float)) and metric is not None else str(metric)
                    print(f"    {letter}: {status} {metric_str}")
                
                return {
                    "county": county,
                    "pass_count": pass_count,
                    "total_letters": total_letters,
                    "score_percentage": pass_count/total_letters*100,
                    "details": result
                }
            else:
                print(f"  ❌ No evaluation data for {county}")
                return {"county": county, "pass_count": 0, "total_letters": 0, "score_percentage": 0.0}
                
    except Exception as e:
        print(f"  ❌ Error evaluating {county}: {e}")
        return {"county": county, "error": str(e)}

def commit_progress(message: str) -> bool:
    """Commit progress to main branch"""
    print(f"\n📝 Committing: {message}")
    
    try:
        # Add all files
        subprocess.run(["git", "add", "."], check=True)
        
        # Commit with message
        subprocess.run([
            "git", "commit", "-m", 
            f"{message}\n\n🤖 Generated with Claude Code - SHARD-28 AUTOPILOT\nSession: {SESSION_ID}\n\nCo-authored-by: breverdbidder <breverdbidder@users.noreply.github.com>"
        ], check=True)
        
        # Push to main
        subprocess.run(["git", "push", "origin", "main"], check=True)
        
        print("  ✅ Committed and pushed to main")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"  ❌ Git operation failed: {e}")
        return False

def execute_priority_phase_1() -> bool:
    """Execute Priority Phase 1: C/D ROOT CAUSE"""
    log_session_progress("PHASE_1", "STARTING", "C/D parity clerk supplementary litmus")
    
    # Run C/D parity fix
    success, output = run_python_script(
        "shard28_cd_parity_clerk_fix.py",
        "C/D Parity Clerk Supplementary Litmus"
    )
    
    if success:
        log_session_progress("PHASE_1", "SUCCESS", "C/D parity fix completed")
        
        # Commit progress
        commit_success = commit_progress("feat: implement C/D parity clerk supplementary litmus for brevard/duval")
        
        if commit_success:
            return True
        else:
            log_session_progress("PHASE_1", "WARNING", "Script succeeded but commit failed")
            return True  # Continue anyway
    else:
        log_session_progress("PHASE_1", "FAILED", f"C/D parity fix failed: {output}")
        return False

def execute_priority_phase_2() -> bool:
    """Execute Priority Phase 2: J GENERATOR"""
    log_session_progress("PHASE_2", "STARTING", "J generator bid_decisions pipeline")
    
    # Run J generator
    success, output = run_python_script(
        "shard28_j_generator_implementation.py", 
        "J Generator Shapira Formula Pipeline"
    )
    
    if success:
        log_session_progress("PHASE_2", "SUCCESS", "J generator completed")
        
        # Commit progress
        commit_success = commit_progress("feat: implement J generator Shapira Formula pipeline for brevard/duval")
        
        if commit_success:
            return True
        else:
            log_session_progress("PHASE_2", "WARNING", "Script succeeded but commit failed")
            return True  # Continue anyway
    else:
        log_session_progress("PHASE_2", "FAILED", f"J generator failed: {output}")
        return False

def execute_verification_protocol() -> Dict:
    """Execute verification protocol for both counties"""
    log_session_progress("VERIFICATION", "STARTING", "Live DB verification protocol")
    
    verification_results = {}
    
    for county in TARGET_COUNTIES:
        result = evaluate_county_live(county)
        verification_results[county] = result
        
        # Log individual county results
        if "error" in result:
            log_session_progress("VERIFICATION", "ERROR", f"{county}: {result['error']}")
        else:
            score = result.get("score_percentage", 0)
            log_session_progress("VERIFICATION", "RESULT", f"{county}: {score:.1f}% ({result.get('pass_count', 0)}/10)")
    
    return verification_results

def execute_session_closeout(verification_results: Dict):
    """Execute session closeout protocol"""
    log_session_progress("CLOSEOUT", "STARTING", "Session summary and final verification")
    
    elapsed_hours, _ = check_session_time()
    
    # Create session summary
    summary = {
        "session_id": SESSION_ID,
        "elapsed_hours": elapsed_hours,
        "target_counties": TARGET_COUNTIES,
        "verification_results": verification_results,
        "completed_at": datetime.now(timezone.utc).isoformat()
    }
    
    # Calculate overall progress
    total_score = 0
    total_possible = 0
    
    for county, result in verification_results.items():
        if "pass_count" in result:
            total_score += result["pass_count"]
            total_possible += result.get("total_letters", 10)
    
    overall_percentage = (total_score / total_possible * 100) if total_possible > 0 else 0
    
    print(f"\n🏆 SESSION SUMMARY")
    print(f"Session ID: {SESSION_ID}")
    print(f"Duration: {elapsed_hours:.1f} hours")
    print(f"Overall Score: {total_score}/{total_possible} ({overall_percentage:.1f}%)")
    print(f"Counties: {', '.join(TARGET_COUNTIES)}")
    
    for county, result in verification_results.items():
        if "error" not in result:
            score = result.get("score_percentage", 0)
            pass_count = result.get("pass_count", 0)
            print(f"  {county.upper()}: {pass_count}/10 ({score:.1f}%)")
        else:
            print(f"  {county.upper()}: ERROR")
    
    # Final commit with session summary
    commit_success = commit_progress(f"feat: complete SHARD-28 autopilot session - {overall_percentage:.1f}% overall")
    
    log_session_progress("CLOSEOUT", "COMPLETE", f"Overall: {overall_percentage:.1f}% - Commit: {'OK' if commit_success else 'FAILED'}")

def main():
    print("=" * 80)
    print("SHARD-28 MASTER EXECUTOR: GOLD STANDARD AUTOPILOT")
    print(f"Session: {SESSION_ID}")
    print(f"Counties: {', '.join(TARGET_COUNTIES)}")
    print(f"Start: {SESSION_START.isoformat()}")
    print(f"Max Duration: {MAX_SESSION_HOURS} hours")
    print("=" * 80)
    
    if not SUPABASE_KEY:
        print("❌ SUPABASE_SERVICE_KEY or SUPABASE_KEY required")
        sys.exit(1)
    
    # Initial verification
    print("\n📊 INITIAL STATUS")
    initial_results = execute_verification_protocol()
    
    # Execute priority phases
    phases_completed = []
    
    # Phase 1: C/D ROOT CAUSE
    elapsed_hours, should_continue = check_session_time()
    if should_continue:
        if execute_priority_phase_1():
            phases_completed.append("CD_PARITY")
        else:
            print("❌ Phase 1 failed, continuing to next phase...")
    else:
        print("⏰ Session time limit reached, skipping to closeout")
    
    # Phase 2: J GENERATOR  
    elapsed_hours, should_continue = check_session_time()
    if should_continue:
        if execute_priority_phase_2():
            phases_completed.append("J_GENERATOR")
        else:
            print("❌ Phase 2 failed, continuing to verification...")
    else:
        print("⏰ Session time limit reached, skipping to closeout")
    
    # Final verification
    print("\n📊 FINAL VERIFICATION")
    final_results = execute_verification_protocol()
    
    # Session closeout
    execute_session_closeout(final_results)
    
    print(f"\n✅ SHARD-28 AUTOPILOT COMPLETE")
    print(f"Phases completed: {', '.join(phases_completed) if phases_completed else 'None'}")
    print(f"Final time: {datetime.now(timezone.utc).isoformat()}")

if __name__ == "__main__":
    main()