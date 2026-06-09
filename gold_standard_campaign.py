#!/usr/bin/env python3
"""
Gold Standard Campaign - Master Orchestrator
Executes comprehensive fixes for charlotte, brevard, broward counties.
Implements all A-J criteria improvements systematically.
"""
import os
import sys
import time
import json
import subprocess
from datetime import datetime, timezone

def log(msg):
    print(f"[GS-CAMPAIGN] {datetime.now(timezone.utc).strftime('%H:%M:%S')} {msg}")

def run_script(script_name, description):
    """Run a Python script and capture results"""
    log(f"🚀 STARTING: {description}")
    
    try:
        result = subprocess.run(
            [sys.executable, script_name], 
            capture_output=True, 
            text=True, 
            timeout=600  # 10 minute timeout
        )
        
        if result.returncode == 0:
            log(f"✅ COMPLETED: {description}")
            if result.stdout:
                log(f"Output: {result.stdout[-500:]}")  # Last 500 chars
            return True
        else:
            log(f"❌ FAILED: {description}")
            log(f"Error: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        log(f"⏰ TIMEOUT: {description} (10 min limit exceeded)")
        return False
    except Exception as e:
        log(f"💥 ERROR: {description} - {e}")
        return False

def main():
    log("=== GOLD STANDARD CAMPAIGN STARTING ===")
    log("Mission: Advance FL counties to GOLD STANDARD (10/10 A-J criteria)")
    log("Targets: charlotte (3/10), brevard (2/10), broward (2/10)")
    
    # Check environment
    supabase_key = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not supabase_key:
        log("❌ FATAL: SUPABASE_KEY not found in environment")
        sys.exit(1)
    
    log("✅ Environment check passed")
    
    # Execute campaign phases
    phases = [
        ("gold_standard_assessment.py", "Baseline Assessment & Analysis"),
        ("gold_standard_fixes.py", "Core Fixes (B/C/D/E/F)"),  
        ("gold_standard_advanced_fixes.py", "Advanced Fixes (G/I/J)"),
    ]
    
    results = {}
    
    for script, description in phases:
        success = run_script(script, description)
        results[description] = "SUCCESS" if success else "FAILED"
        
        if not success:
            log(f"⚠️  Phase failed but continuing: {description}")
        
        # Brief pause between phases
        time.sleep(3)
    
    # Final verification and reporting
    log("\n=== FINAL VERIFICATION & REPORTING ===")
    
    try:
        # This would be executed if we had direct database access
        log("Note: Final verification requires database connection")
        log("Expected improvements:")
        log("- B: Independent verified outcomes for all closed auctions")
        log("- C/D: Improved PropertyOnion parity via date/address fixes")
        log("- E: Enhanced parcel linkage through address matching")
        log("- F: Tier1 sold amounts populated from winning bids")
        log("- G: Baseline zoning coverage established")
        log("- I: Property cards completed with address/geo/value")
        log("- J: Bid decisions created using Shapira formula")
        
    except Exception as e:
        log(f"Verification error: {e}")
    
    # Campaign summary
    log(f"\n=== CAMPAIGN SUMMARY ===")
    success_count = sum(1 for status in results.values() if status == "SUCCESS")
    total_phases = len(results)
    
    log(f"Phases completed: {success_count}/{total_phases}")
    
    for phase, status in results.items():
        icon = "✅" if status == "SUCCESS" else "❌"
        log(f"{icon} {phase}: {status}")
    
    if success_count == total_phases:
        log("\n🎉 CAMPAIGN COMPLETED SUCCESSFULLY")
        log("Next steps:")
        log("1. Monitor gold_standard_scoreboard for updated pass counts")
        log("2. Run daily gold_standard_loop() to track progress") 
        log("3. Verify certification via gold_standard_certify()")
    else:
        log(f"\n⚠️  CAMPAIGN PARTIALLY COMPLETED ({success_count}/{total_phases})")
        log("Manual intervention may be required for failed phases")
    
    return results

if __name__ == "__main__":
    results = main()
    
    # Return exit code based on success rate
    success_rate = sum(1 for status in results.values() if status == "SUCCESS") / len(results)
    sys.exit(0 if success_rate >= 0.5 else 1)  # Success if >=50% phases completed