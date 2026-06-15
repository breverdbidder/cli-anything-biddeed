#!/usr/bin/env python3
"""Execute verification protocol and show evidence output"""
import subprocess
import sys

print("=== SHARD-4 VERIFICATION PROTOCOL EXECUTION ===")
print("Per Issue #7801 brief: mandatory verification with literal JSON evidence")
print()

try:
    # Execute the verification protocol
    result = subprocess.run([sys.executable, 'shard4_verification_protocol.py'], 
                          capture_output=True, text=True, timeout=120)
    
    print("STDOUT:")
    print(result.stdout)
    
    if result.stderr:
        print("\nSTDERR:")
        print(result.stderr)
    
    print(f"\nReturn code: {result.returncode}")
    
except subprocess.TimeoutExpired:
    print("Verification protocol execution timed out")
except Exception as e:
    print(f"Error executing verification protocol: {e}")