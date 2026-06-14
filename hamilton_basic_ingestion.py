#!/usr/bin/env python3
"""
Hamilton County Basic Ingestion - Highest Leverage Fix
From 0/10 letters to basic A-lane setup via FL GIO ingestion
"""
import subprocess
import sys
import os
from datetime import datetime

def run_hamilton_ingestion():
    """Run Hamilton county ingestion using existing ingest_county.py script"""
    print(f"=== HAMILTON COUNTY BASIC INGESTION ===")
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    print(f"Hamilton CO_NO: 24")
    
    try:
        # First run count check
        print("\n--- Step 1: Count Check ---")
        cmd_count = ["python", "scripts/ingest_county.py", "--county", "24"]
        print(f"Running: {' '.join(cmd_count)}")
        
        result_count = subprocess.run(cmd_count, capture_output=True, text=True, timeout=300)
        
        print(f"Count check result: {result_count.returncode}")
        if result_count.stdout:
            print(f"STDOUT:\n{result_count.stdout}")
        if result_count.stderr:
            print(f"STDERR:\n{result_count.stderr}")
        
        if result_count.returncode != 0:
            print("❌ Count check failed - aborting")
            return False
        
        # Run full ingestion
        print("\n--- Step 2: Full Ingestion ---")
        cmd_full = ["python", "scripts/ingest_county.py", "--county", "24", "--full"]
        print(f"Running: {' '.join(cmd_full)}")
        
        result_full = subprocess.run(cmd_full, capture_output=True, text=True, timeout=3600)
        
        print(f"Full ingestion result: {result_full.returncode}")
        if result_full.stdout:
            print(f"STDOUT:\n{result_full.stdout}")
        if result_full.stderr:
            print(f"STDERR:\n{result_full.stderr}")
        
        if result_full.returncode == 0:
            print("✅ Hamilton county ingestion completed")
            return True
        else:
            print("❌ Hamilton county ingestion failed")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Hamilton ingestion timed out")
        return False
    except Exception as e:
        print(f"❌ Error during Hamilton ingestion: {e}")
        return False

if __name__ == "__main__":
    success = run_hamilton_ingestion()
    sys.exit(0 if success else 1)