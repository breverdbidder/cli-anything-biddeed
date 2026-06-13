#!/usr/bin/env python3
"""
SHARD-20 Wrapper: Execute C/D Parity Fix for Charlotte/Citrus/Broward
Runs the existing shard19_cd_parity_fix.py implementation
"""
import os
import sys
import subprocess
import json
from datetime import datetime

def main():
    print("🚀 SHARD-20 C/D PARITY FIX EXECUTION")
    print("Counties: charlotte, citrus, broward")
    print("Using existing shard19_cd_parity_fix.py implementation")
    print("-" * 60)
    
    try:
        # Set any required environment variables
        env = os.environ.copy()
        
        # Run the existing shard19 script
        result = subprocess.run(
            [sys.executable, "scripts/shard19_cd_parity_fix.py"],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
            env=env
        )
        
        print("STDOUT:")
        print(result.stdout)
        
        if result.stderr:
            print("\nSTDERR:")
            print(result.stderr)
            
        print(f"\nReturn code: {result.returncode}")
        
        if result.returncode == 0:
            print("✅ C/D Parity analysis completed successfully")
        else:
            print("❌ C/D Parity analysis failed")
            
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("❌ Script timed out after 5 minutes")
        return False
    except Exception as e:
        print(f"❌ Error running C/D parity fix: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)