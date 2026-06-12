#!/usr/bin/env python3
"""
SHARD-17 Manual Execution: Gold Standard Improvements
Execute the improvement cycle manually for immediate metric movement

This script orchestrates the F criterion and C/D parity improvements
for charlotte, citrus, broward in a single session.
"""
import os
import sys
import time
import subprocess
import json

def run_script(script_name):
    """Run a Python script and capture output"""
    print(f"\n{'='*60}")
    print(f"EXECUTING: {script_name}")
    print('='*60)
    
    try:
        result = subprocess.run([
            sys.executable, 
            f"scripts/{script_name}"
        ], capture_output=True, text=True, timeout=600)
        
        print("STDOUT:")
        print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
            
        print(f"Exit code: {result.returncode}")
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("❌ Script timed out after 10 minutes")
        return False
    except Exception as e:
        print(f"❌ Error running script: {e}")
        return False

def main():
    """Execute the full improvement cycle"""
    print("SHARD-17 GOLD STANDARD AUTOPILOT - MANUAL EXECUTION")
    print("Counties: charlotte, citrus, broward")
    print("Targets: F (tier1_sold_amount), C/D (parity_status)")
    print()
    
    # Check environment
    if not os.environ.get("SUPABASE_KEY") and not os.environ.get("SUPABASE_SERVICE_KEY"):
        print("❌ SUPABASE_KEY or SUPABASE_SERVICE_KEY environment variable required")
        print("Set one of these before running:")
        print("  export SUPABASE_KEY=your_service_key")
        print("  export SUPABASE_SERVICE_KEY=your_service_key")
        sys.exit(1)
    
    print("✅ Environment configured")
    print()
    
    # Execution sequence
    scripts = [
        "shard17_f_criterion_promoter.py",
        "shard17_parity_improver.py"
    ]
    
    results = {}
    
    for script in scripts:
        success = run_script(script)
        results[script] = success
        
        if not success:
            print(f"\n⚠️  {script} failed - continuing with next script")
        else:
            print(f"\n✅ {script} completed successfully")
            
        time.sleep(3)  # Throttle between scripts
    
    # Final summary
    print("\n" + "="*60)
    print("EXECUTION SUMMARY")
    print("="*60)
    
    successful = sum(1 for success in results.values() if success)
    total = len(results)
    
    for script, success in results.items():
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"{script}: {status}")
    
    print(f"\nOverall: {successful}/{total} scripts completed successfully")
    
    if successful == total:
        print("\n🎯 All improvements completed! Check Gold Standard metrics.")
    else:
        print(f"\n⚠️  Some improvements failed. Check logs above for details.")
        
    print("\nNext steps:")
    print("1. Run: python test_db_connection.py  # To verify current metrics")
    print("2. Check gold_standard_scoreboard view for updated scores")
    print("3. Monitor GitHub Actions workflow for automated improvements")

if __name__ == "__main__":
    main()