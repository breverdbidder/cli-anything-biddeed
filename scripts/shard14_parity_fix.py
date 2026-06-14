#!/usr/bin/env python3
"""
SHARD-14: C/D Parity Fix for Volusia
Address frozen numerator pattern per brief analysis

Current Volusia metrics:
- C FAIL metric=11.6 [matched_clean=1491 of 12908]
- D FAIL metric=56.7 [matched_any=7323 of 12908]

Uses existing improve_parity_matching.py with Volusia extension
"""
import subprocess
import os
import sys
from datetime import datetime

def main():
    print("=== SHARD-14: Volusia C/D Parity Fix ===")
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    print(f"Issue: Frozen numerator pattern per brief")
    print(f"Current: C=11.6% (1491/12908), D=56.7% (7323/12908)")
    print(f"Target: ≥95% for both letters")
    
    try:
        # Use existing parity improvement script
        cmd = ["python", "scripts/improve_parity_matching.py", "--county", "volusia"]
        print(f"\nEXEC: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        
        print(f"RESULT: Exit code {result.returncode}")
        if result.stdout:
            print(f"STDOUT:\n{result.stdout}")
        if result.stderr:
            print(f"STDERR:\n{result.stderr}")
        
        if result.returncode == 0:
            print("✅ SUCCESS: Volusia parity improvement completed")
            
            # Evidence
            print(f"\n--- EVIDENCE ---")
            print(f"VERIFIED: Volusia parity matching executed")
            print(f"TIMESTAMP: {datetime.utcnow().isoformat()}Z")
            print(f"SCRIPT: scripts/improve_parity_matching.py --county volusia")
            print(f"EXIT_CODE: {result.returncode}")
            
            return True
        else:
            print("❌ FAIL: Volusia parity improvement failed")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ FAIL: Volusia parity improvement timed out")
        return False
    except Exception as e:
        print(f"❌ FAIL: Error during parity improvement: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)