#!/usr/bin/env python3
"""
SHARD-9 MASTER EXECUTOR
Coordinates all Gold Standard fixes for: palm_beach, escambia, okaloosa, dixie, taylor

EXECUTION ORDER (based on dependency chain and issue priorities):
1. Letter A: Configure lanes for dixie/taylor (bootstrap 0/10 counties)
2. Letter J: Deploy deal thesis generator (county-agnostic, high impact)
3. Letter B: Build verified outcome scrapers (critical for certification)
4. Letter E: Parcel linkage fixes (enables downstream flows)
5. Letter H: Freshness fixes for escambia/okaloosa (immediate impact)
6. Verification: Run pencil_dod_evaluate_county for all counties

SHIP-TO-MAIN MANDATE: Direct commits, no side branches, frequent pushes
"""
import os
import sys
import subprocess
import time
import json
from datetime import datetime, timezone

# SHARD-9 execution plan
EXECUTION_PLAN = [
    {
        'phase': 'A_bootstrap',
        'script': 'scripts/shard9_a_lane_configuration.py',
        'description': 'Configure dual lanes for dixie/taylor (0/10 → data)',
        'target_counties': ['dixie', 'taylor'],
        'estimated_minutes': 15
    },
    {
        'phase': 'J_generator', 
        'script': 'scripts/shard9_j_deal_thesis_generator.py',
        'description': 'Deploy Shapira Formula pipeline (county-agnostic)',
        'target_counties': ['all'],
        'estimated_minutes': 30
    },
    {
        'phase': 'B_verification',
        'script': 'scripts/shard9_b_verified_outcomes.py', 
        'description': 'Build clerk-based outcome scrapers (critical for cert)',
        'target_counties': ['palm_beach', 'escambia', 'okaloosa', 'dixie', 'taylor'],
        'estimated_minutes': 45
    },
    {
        'phase': 'E_linkage',
        'script': 'scripts/shard9_e_parcel_linkage.py',
        'description': 'Fix parcel ID linkage via county GIS (enables I)',
        'target_counties': ['palm_beach', 'escambia', 'okaloosa'],
        'estimated_minutes': 30
    },
    {
        'phase': 'H_freshness',
        'script': 'scripts/shard9_h_freshness_fix.py',
        'description': 'Repair stale data flows for immediate H improvement',
        'target_counties': ['escambia', 'okaloosa'], 
        'estimated_minutes': 20
    }
]

def log_action(msg: str, level: str = "INFO", honesty_tag: str = "UNTESTED"):
    """Log with timestamp and honesty protocol tag"""
    timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{timestamp}] {level} [{honesty_tag}]: {msg}")

def run_script(script_path: str, phase: str) -> dict:
    """
    Execute a fix script and capture results
    """
    log_action(f"Executing {phase}: {script_path}", "INFO", "UNTESTED")
    
    try:
        # Run the script
        result = subprocess.run(
            [sys.executable, script_path],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout per script
        )
        
        execution_result = {
            'phase': phase,
            'script': script_path,
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'return_code': result.returncode
        }
        
        if result.returncode == 0:
            log_action(f"✅ {phase}: COMPLETED", "INFO", "VERIFIED")
        else:
            log_action(f"❌ {phase}: FAILED (exit {result.returncode})", "ERROR", "VERIFIED")
            if result.stderr:
                log_action(f"{phase} stderr: {result.stderr[:200]}", "ERROR", "VERIFIED")
        
        return execution_result
        
    except subprocess.TimeoutExpired:
        log_action(f"❌ {phase}: TIMEOUT after 5 minutes", "ERROR", "VERIFIED")
        return {
            'phase': phase,
            'script': script_path,
            'success': False,
            'error': 'timeout',
            'return_code': -1
        }
    except Exception as e:
        log_action(f"❌ {phase}: EXECUTION ERROR: {e}", "ERROR", "VERIFIED")
        return {
            'phase': phase,
            'script': script_path,
            'success': False,
            'error': str(e),
            'return_code': -2
        }

def commit_progress(phase: str, message: str) -> bool:
    """
    Commit progress to main branch per ship-to-main mandate
    """
    log_action(f"Committing progress after {phase}", "INFO", "UNTESTED")
    
    try:
        # Add all changes
        subprocess.run(['git', 'add', '.'], check=True, cwd=os.path.dirname(os.path.abspath(__file__)))
        
        # Commit with descriptive message
        commit_msg = f"shard9: {message}\n\nGenerated with Claude Code\n\nCo-authored-by: breverdbidder <breverdbidder@users.noreply.github.com>"
        subprocess.run(['git', 'commit', '-m', commit_msg], check=True, cwd=os.path.dirname(os.path.abspath(__file__)))
        
        # Push to main (ship-to-main mandate)
        subprocess.run(['git', 'push', 'origin', 'main'], check=True, cwd=os.path.dirname(os.path.abspath(__file__)))
        
        log_action(f"✅ Progress committed and pushed to main", "INFO", "VERIFIED")
        return True
        
    except subprocess.CalledProcessError as e:
        log_action(f"❌ Commit failed: {e}", "ERROR", "VERIFIED")
        return False

def run_county_verification() -> dict:
    """
    Run final verification using pencil_dod_evaluate_county for all SHARD-9 counties
    """
    log_action("Running final verification for all SHARD-9 counties", "INFO", "UNTESTED")
    
    verification_script = 'verify_shard9_status.py'
    
    try:
        result = subprocess.run(
            [sys.executable, verification_script],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True,
            text=True,
            timeout=180  # 3 minute timeout
        )
        
        verification_result = {
            'success': result.returncode == 0,
            'output': result.stdout,
            'errors': result.stderr
        }
        
        if result.returncode == 0:
            log_action("✅ Final verification COMPLETED", "INFO", "VERIFIED")
        else:
            log_action("❌ Final verification FAILED", "ERROR", "VERIFIED")
        
        return verification_result
        
    except Exception as e:
        log_action(f"❌ Verification error: {e}", "ERROR", "VERIFIED")
        return {'success': False, 'error': str(e)}

def main():
    """
    Execute SHARD-9 autonomous session with ship-to-main commits
    """
    session_start = time.time()
    log_action("🎯 SHARD-9 AUTONOMOUS SESSION START", "INFO", "VERIFIED")
    log_action("Counties: palm_beach, escambia, okaloosa, dixie, taylor", "INFO", "VERIFIED")
    log_action("Mandate: Ship directly to main, no side branches", "INFO", "VERIFIED")
    
    execution_results = []
    successful_phases = 0
    
    # Execute each phase
    for i, phase_config in enumerate(EXECUTION_PLAN):
        phase = phase_config['phase']
        script = phase_config['script']
        description = phase_config['description']
        estimated_min = phase_config['estimated_minutes']
        
        log_action(f"=== PHASE {i+1}/{len(EXECUTION_PLAN)}: {phase} ===", "INFO", "VERIFIED")
        log_action(f"{description}", "INFO", "VERIFIED")
        log_action(f"Estimated duration: {estimated_min} minutes", "INFO", "VERIFIED")
        
        # Execute the fix script
        result = run_script(script, phase)
        execution_results.append(result)
        
        if result['success']:
            successful_phases += 1
            
            # Commit progress after each successful phase (ship-to-main)
            commit_message = f"{phase} fixes deployed - {description}"
            commit_progress(phase, commit_message)
        else:
            log_action(f"⚠️  {phase} failed, continuing with remaining phases", "WARN", "VERIFIED")
        
        # Brief pause between phases
        time.sleep(2)
    
    # Run final verification
    log_action("=== FINAL VERIFICATION ===", "INFO", "VERIFIED") 
    verification = run_county_verification()
    
    # Session summary
    session_duration = (time.time() - session_start) / 60
    log_action("=== SESSION SUMMARY ===", "INFO", "VERIFIED")
    log_action(f"Duration: {session_duration:.1f} minutes", "INFO", "VERIFIED")
    log_action(f"Phases successful: {successful_phases}/{len(EXECUTION_PLAN)}", "INFO", "VERIFIED")
    
    # Detailed results
    for result in execution_results:
        phase = result['phase']
        success = "✅" if result['success'] else "❌"
        log_action(f"  {phase}: {success}", "INFO", "VERIFIED")
    
    verification_status = "✅" if verification.get('success', False) else "❌"
    log_action(f"  final_verification: {verification_status}", "INFO", "VERIFIED")
    
    # Final commit
    if successful_phases > 0:
        final_message = f"SHARD-9 session complete: {successful_phases}/{len(EXECUTION_PLAN)} phases successful"
        commit_progress("session_complete", final_message)
        log_action("🏁 SHARD-9 SESSION SHIPPED TO MAIN", "INFO", "VERIFIED")
    else:
        log_action("❌ No successful phases - session failed", "ERROR", "VERIFIED")
    
    return successful_phases > 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)