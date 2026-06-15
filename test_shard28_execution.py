#!/usr/bin/env python3
"""
Test execution of SHARD 28 autopilot script
"""
import subprocess
import sys
import os

# Ensure httpx is available
try:
    import httpx
    print("✅ httpx available")
except ImportError:
    print("Installing httpx...")
    subprocess.run([sys.executable, "-m", "pip", "install", "httpx"], check=True)

# Test script execution
script_path = "scripts/shard28_gold_standard_autopilot.py"

if not os.path.exists(script_path):
    print(f"❌ Script not found: {script_path}")
    sys.exit(1)

print(f"✅ Script exists: {script_path}")

# Test verify-only mode first
try:
    print("Testing verify-only mode...")
    result = subprocess.run([
        sys.executable, script_path, 
        "--verify-only",
        "--max-runtime-minutes", "5"
    ], capture_output=True, text=True, timeout=300)
    
    print(f"Exit code: {result.returncode}")
    print("STDOUT:")
    print(result.stdout)
    
    if result.stderr:
        print("STDERR:")
        print(result.stderr)
        
    if result.returncode == 0:
        print("✅ Verify-only test passed")
    else:
        print("❌ Verify-only test failed")
        
except subprocess.TimeoutExpired:
    print("❌ Script timed out")
except Exception as e:
    print(f"❌ Execution error: {e}")

print("\nScript test completed.")