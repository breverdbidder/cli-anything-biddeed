#!/usr/bin/env python3
"""
SHARD-19 Campaign Executor - Entry Point for Issue #7607
Gold Standard Autonomous Campaign

This is the main execution entry point that can be called by existing executors
or GitHub Actions workflows to run the complete SHARD-19 campaign.

Usage:
  python execute_shard19_campaign.py
  
Environment: Requires SUPABASE_URL and SUPABASE_KEY environment variables
Counties: charlotte, citrus, broward
Priority: C_D_ROOT_CAUSE fixes per Brevard Sprint Order
"""
import os
import sys
import json
import subprocess
from datetime import datetime, timezone

def main():
    """Execute SHARD-19 Gold Standard campaign"""
    session_start = datetime.now(timezone.utc)
    
    print("🎯 SHARD-19 GOLD STANDARD CAMPAIGN - AUTONOMOUS EXECUTION")
    print(f"Issue: #7607 | Session: {session_start.isoformat()}")
    print(f"Counties: charlotte, citrus, broward")
    print(f"Priority: C_D_ROOT_CAUSE (parity clean/any fixes)")
    print()
    
    # Check environment
    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
    
    if not supabase_url or not supabase_key:
        print("❌ BLOCKED: Missing Supabase environment variables")
        print("Required: SUPABASE_URL and SUPABASE_KEY (or SUPABASE_SERVICE_KEY)")
        return {"status": "BLOCKED", "reason": "missing_environment"}
    
    print("✅ Environment check passed")
    print(f"   Supabase URL: {supabase_url}")
    print(f"   API Key length: {len(supabase_key)}")
    print()
    
    # Execute master coordinator with live mode
    print("🚀 Launching master coordinator...")
    try:
        result = subprocess.run([
            sys.executable, 
            "scripts/shard19_master_coordinator.py",
            "--execute-live"
        ], capture_output=True, text=True, timeout=1800)  # 30 min timeout
        
        if result.returncode == 0:
            print("✅ SHARD-19 campaign execution completed successfully")
            print("\n=== STDOUT ===")
            print(result.stdout)
            
            # Try to load results if available
            try:
                with open("/tmp/shard19_campaign_results.json", "r") as f:
                    results = json.load(f)
                    
                print("\n=== EXECUTION SUMMARY ===")
                print(f"Session: {results.get('session_start')} → {results.get('session_end')}")
                print(f"Mode: {results.get('execution_mode', 'unknown')}")
                print(f"Counties: {len(results.get('counties', []))}")
                print(f"Phases: {len(results.get('phase_results', []))}")
                
                if results.get('ultraloop_audit'):
                    survival_rate = results['ultraloop_audit'].get('overall_survival_rate', 0)
                    print(f"ULTRALOOP survival: {survival_rate:.1%}")
                    
            except:
                print("(Results file not available)")
                
            return {"status": "SUCCESS", "return_code": result.returncode}
        else:
            print("❌ SHARD-19 campaign execution failed")
            print(f"Return code: {result.returncode}")
            if result.stderr:
                print(f"STDERR: {result.stderr}")
            if result.stdout:
                print(f"STDOUT: {result.stdout}")
                
            return {"status": "FAILED", "return_code": result.returncode, "stderr": result.stderr}
            
    except subprocess.TimeoutExpired:
        print("⏰ SHARD-19 campaign execution timed out (30 min limit)")
        return {"status": "TIMEOUT"}
    except Exception as e:
        print(f"💥 Exception during execution: {e}")
        return {"status": "EXCEPTION", "error": str(e)}

if __name__ == "__main__":
    result = main()
    exit_code = 0 if result.get("status") == "SUCCESS" else 1
    sys.exit(exit_code)