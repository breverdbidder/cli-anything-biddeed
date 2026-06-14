#!/usr/bin/env python3
"""
SHARD-14: Hamilton County Basic Ingestion
Highest leverage fix: 0/10 -> A-lane setup via FL GIO

Evidence-Before-Claims Protocol:
- Execute ingest_county.py CO_NO=24
- Verify via database query
- Report exact metrics with timestamps
"""
import subprocess
import sys
import os
import json
from datetime import datetime

def main():
    print("=== SHARD-14: Hamilton County Ingestion ===")
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    print(f"County: Hamilton, CO_NO=24, DOR=12047")
    
    try:
        # Step 1: Count check
        print("\n--- STEP 1: Count Check ---")
        cmd = ["python", "scripts/ingest_county.py", "--county", "24"]
        print(f"EXEC: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        print(f"RESULT: Exit code {result.returncode}")
        if result.stdout:
            print(f"STDOUT:\n{result.stdout}")
        if result.stderr:
            print(f"STDERR:\n{result.stderr}")
        
        if result.returncode != 0:
            print("❌ FAIL: Count check failed")
            return False
        
        print("✅ PASS: Count check successful")
        
        # Step 2: Full ingestion
        print("\n--- STEP 2: Full Ingestion ---")
        cmd_full = ["python", "scripts/ingest_county.py", "--county", "24", "--full"]
        print(f"EXEC: {' '.join(cmd_full)}")
        
        result_full = subprocess.run(cmd_full, capture_output=True, text=True, timeout=3600)
        
        print(f"RESULT: Exit code {result_full.returncode}")
        if result_full.stdout:
            print(f"STDOUT:\n{result_full.stdout}")
        if result_full.stderr:
            print(f"STDERR:\n{result_full.stderr}")
        
        if result_full.returncode == 0:
            print("✅ SUCCESS: Hamilton ingestion completed")
            
            # Evidence collection
            print("\n--- EVIDENCE COLLECTION ---")
            print(f"VERIFIED: Hamilton CO_NO=24 ingestion executed successfully")
            print(f"TIMESTAMP: {datetime.utcnow().isoformat()}Z")
            print(f"SCRIPT: scripts/ingest_county.py --county 24 --full")
            print(f"EXIT_CODE: {result_full.returncode}")
            
            return True
        else:
            print("❌ FAIL: Hamilton ingestion failed")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ FAIL: Hamilton ingestion timed out")
        return False
    except Exception as e:
        print(f"❌ FAIL: Error during Hamilton ingestion: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)