#!/usr/bin/env python3
"""
SHARD-6 Campaign Execution Script
Manual execution with verification protocol
"""

import os
import sys
import json
import subprocess
import logging
from datetime import datetime, timezone

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_script(script_path, args=None):
    """Run a Python script and capture output"""
    cmd = [sys.executable, script_path]
    if args:
        cmd.extend(args)
    
    logger.info(f"Running: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)  # 30 min timeout
        
        if result.returncode == 0:
            logger.info(f"✅ {script_path} completed successfully")
            if result.stdout:
                print(f"Output:\n{result.stdout}")
        else:
            logger.error(f"❌ {script_path} failed with code {result.returncode}")
            if result.stderr:
                print(f"Error:\n{result.stderr}")
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        logger.error(f"❌ {script_path} timed out")
        return False
    except Exception as e:
        logger.error(f"❌ Error running {script_path}: {e}")
        return False

def main():
    """Execute SHARD-6 campaign"""
    start_time = datetime.now(timezone.utc)
    logger.info(f"SHARD-6 Gold Standard Campaign Started: {start_time.isoformat()}")
    logger.info("Counties: escambia, sumter, lake, calhoun, liberty")
    
    # Test connection first
    logger.info("\n=== CONNECTION TEST ===")
    if not run_script("scripts/test_shard6_connection.py"):
        logger.error("Connection test failed - aborting campaign")
        return False
    
    # Get baseline status
    logger.info("\n=== BASELINE STATUS ===")
    run_script("scripts/shard6_gold_standard.py", ["status"])
    
    # Execute campaign phases
    phases = [
        ("LANE CONFIGURATION (A)", "scripts/shard6_configure_lanes.py"),
        ("PARCEL LINKAGE (E)", "scripts/shard6_parcel_linkage.py"), 
        ("VERIFIED OUTCOMES (B)", "scripts/shard6_verified_outcomes.py")
    ]
    
    results = {}
    
    for phase_name, script_path in phases:
        logger.info(f"\n=== {phase_name} ===")
        success = run_script(script_path)
        results[phase_name] = success
        
        if not success:
            logger.warning(f"{phase_name} completed with errors")
    
    # Final verification
    logger.info("\n=== FINAL VERIFICATION ===")
    run_script("scripts/shard6_gold_standard.py", ["status"])
    
    # Summary
    end_time = datetime.now(timezone.utc)
    duration = end_time - start_time
    
    logger.info(f"\n=== CAMPAIGN SUMMARY ===")
    logger.info(f"Duration: {duration.total_seconds():.0f} seconds")
    logger.info(f"Completed: {end_time.isoformat()}")
    
    for phase, success in results.items():
        status = "✅ SUCCESS" if success else "❌ FAILED"
        logger.info(f"{phase}: {status}")
    
    total_success = all(results.values())
    logger.info(f"Overall: {'✅ CAMPAIGN SUCCESS' if total_success else '⚠️ PARTIAL SUCCESS'}")
    
    return total_success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)