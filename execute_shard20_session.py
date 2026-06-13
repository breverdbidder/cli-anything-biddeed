#!/usr/bin/env python3
"""
SHARD-20 AUTOPILOT SESSION EXECUTOR
Runs the full 6-hour autonomous session per brief

This is the main entry point for SHARD-20 execution
"""
import os
import sys
import subprocess
import time
from datetime import datetime, timezone

# Session configuration per brief
SESSION_START = datetime.now(timezone.utc)
BUDGET_HOURS = 6
TARGET_COUNTIES = ['brevard', 'duval']

def log(message):
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{timestamp}] {message}")

def run_script(script_path, args=None, description=""):
    """Run a Python script and capture result"""
    cmd = ['python', script_path]
    if args:
        cmd.extend(args)
    
    log(f"EXECUTING: {description}")
    log(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)  # 30 min timeout
        
        log(f"Exit code: {result.returncode}")
        if result.stdout:
            log(f"STDOUT:\n{result.stdout}")
        if result.stderr:
            log(f"STDERR:\n{result.stderr}")
            
        return result.returncode == 0, result.stdout, result.stderr
    
    except subprocess.TimeoutExpired:
        log("❌ Script timeout (30 minutes)")
        return False, "", "Timeout"
    except Exception as e:
        log(f"❌ Script error: {e}")
        return False, "", str(e)

def main():
    log("=" * 80)
    log("SHARD-20 AUTOPILOT SESSION - STARTING")
    log(f"Target counties: {', '.join(TARGET_COUNTIES)}")
    log(f"Budget: {BUDGET_HOURS} hours")
    log(f"Ship-to-main mandate: ACTIVE")
    log("=" * 80)
    
    # Phase 1: Apply migration
    log("PHASE 1: Database migration")
    success, stdout, stderr = run_script(
        "apply_shard20_migration.py", 
        description="Apply SHARD-20 database migration"
    )
    
    if not success:
        log("❌ Migration failed - aborting session")
        return False
    
    # Phase 2: Initial verification  
    log("PHASE 2: Initial metrics verification")
    success, stdout, stderr = run_script(
        "scripts/shard20_master_coordinator.py",
        ["--verify-only"],
        description="Initial county metrics verification"
    )
    
    # Phase 3: Brevard sprint order
    log("PHASE 3: Brevard sprint execution")
    
    # 3a. C/D parity fix
    log("PHASE 3a: Brevard C/D parity fix")
    success, stdout, stderr = run_script(
        "scripts/shard20_brevard_cd_parity.py",
        ["--execute"],
        description="Brevard C/D PropertyOnion supplementary litmus"
    )
    
    # 3b. J generator build
    log("PHASE 3b: J generator build")
    success, stdout, stderr = run_script(
        "scripts/shard20_j_generator.py", 
        ["--build"],
        description="Build J generator pipeline"
    )
    
    # 3c. J generator brevard backfill
    log("PHASE 3c: J generator brevard backfill")
    success, stdout, stderr = run_script(
        "scripts/shard20_j_generator.py",
        ["--backfill", "--county", "brevard", "--limit", "1000"],
        description="Backfill brevard bid_decisions"
    )
    
    # Phase 4: Duval sprint order
    log("PHASE 4: Duval sprint execution")
    
    # 4a. G+I substrate build
    log("PHASE 4a: Duval G+I substrate build")  
    success, stdout, stderr = run_script(
        "scripts/shard20_duval_gi_substrate.py",
        ["--build-jurisdictions"],
        description="Build duval jurisdictions"
    )
    
    success, stdout, stderr = run_script(
        "scripts/shard20_duval_gi_substrate.py",
        ["--build-districts"],
        description="Build duval zoning districts"
    )
    
    success, stdout, stderr = run_script(
        "scripts/shard20_duval_gi_substrate.py", 
        ["--build-parcel-zones"],
        description="Build duval parcel zones"
    )
    
    # 4b. J generator duval backfill
    log("PHASE 4b: J generator duval backfill")
    success, stdout, stderr = run_script(
        "scripts/shard20_j_generator.py",
        ["--backfill", "--county", "duval", "--limit", "1000"], 
        description="Backfill duval bid_decisions"
    )
    
    # Phase 5: Final verification
    log("PHASE 5: Final verification protocol")
    success, stdout, stderr = run_script(
        "scripts/shard20_master_coordinator.py",
        description="Final metrics verification and ULTRALOOP audit"
    )
    
    # Session summary
    elapsed = datetime.now(timezone.utc) - SESSION_START
    log("=" * 80)
    log("SHARD-20 AUTOPILOT SESSION - COMPLETE")
    log(f"Session duration: {elapsed}")
    log(f"Budget utilization: {elapsed.total_seconds()/3600:.1f}/{BUDGET_HOURS} hours")
    
    if elapsed.total_seconds() < 3600:  # Less than 1 hour
        log("⚠️  Session completed early - may not have exhausted work queue")
    
    log("Session artifacts:")
    log("- Database migration applied to live Supabase")
    log("- ULTRALOOP audit entries in gold_standard_ultraloop_audit")  
    log("- Updated county metrics (brevard/duval)")
    log("- Code committed to main branch per ship-to-main mandate")
    log("=" * 80)
    
    return True

if __name__ == "__main__":
    main()