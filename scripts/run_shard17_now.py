#!/usr/bin/env python3
"""
SHARD-17 IMMEDIATE EXECUTION LAUNCHER
Run this script NOW to start fixing charlotte, citrus, broward counties.

WIRING MANDATE: This executes the pipelines immediately.
"""
import os
import subprocess
import sys

def main():
    print("🎯 SHARD-17 GOLD STANDARD IMMEDIATE EXECUTION")
    print("=" * 50)
    print("Counties: charlotte, citrus, broward")
    print("Letters: B (verified outcomes), I (property cards), J (deal thesis)")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not os.path.exists('scripts/shard17_execute_pipeline.py'):
        print("❌ Must run from repository root directory")
        sys.exit(1)
    
    # Run verification first
    print("\n📊 Step 1: Current Status Verification")
    try:
        result = subprocess.run([
            'python3', 'scripts/shard17_execute_pipeline.py', '--verify'
        ], timeout=120)
        if result.returncode != 0:
            print("⚠️  Verification had issues, continuing with pipeline execution...")
    except Exception as e:
        print(f"⚠️  Verification error: {e}, continuing...")
    
    # Run all pipelines
    print("\n🔧 Step 2: Pipeline Execution (All Counties, All Letters)")
    try:
        result = subprocess.run([
            'python3', 'scripts/shard17_execute_pipeline.py', 
            '--all', 
            '--letters', 'B,I,J',
            '--output', 'shard17_execution_results.json'
        ], timeout=1800)  # 30 minute timeout
        
        if result.returncode == 0:
            print("✅ Pipeline execution completed successfully!")
        else:
            print(f"❌ Pipeline execution failed with code {result.returncode}")
    except subprocess.TimeoutExpired:
        print("⏰ Pipeline execution timed out (30 minutes)")
    except Exception as e:
        print(f"❌ Pipeline execution error: {e}")
    
    print("\n🎯 SHARD-17 execution attempt complete.")
    print("Check shard17_execution_results.json for detailed results.")

if __name__ == "__main__":
    main()