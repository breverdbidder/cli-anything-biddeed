#!/usr/bin/env python3
"""
Quick baseline check for SHARD-1 counties using hardcoded connection
This is based on shard2_baseline.py but modified for our counties
"""
import os
import json
import subprocess
import sys

# Minimal config - hardcoded from CLAUDE.md
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1vY2VycWpua3NtaGNqenhyZXdvIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTcxODEzNTQwMywiZXhwIjoyMDMzNzExNDAzfQ.Gf-cZyO5WQOd6qXbIXTnfQRGjgBgWVoZbJO2LoN_pTc"

SHARD1_COUNTIES = ['brevard', 'palm_beach', 'gilchrist', 'seminole', 'hardee']

def curl_call(endpoint, method="GET", data=None):
    """Use curl for API calls since import issues"""
    cmd = [
        "curl", "-s", "-X", method,
        "-H", f"apikey: {SUPABASE_KEY}",
        "-H", f"Authorization: Bearer {SUPABASE_KEY}",
        "-H", "Content-Type: application/json",
    ]
    
    if data:
        cmd.extend(["-d", json.dumps(data)])
    
    cmd.append(f"{SUPABASE_URL}/rest/v1{endpoint}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return json.loads(result.stdout) if result.stdout.strip() else None
        else:
            print(f"Curl error: {result.stderr}")
            return None
    except Exception as e:
        print(f"Error calling {endpoint}: {e}")
        return None

def test_connection():
    """Test basic connectivity"""
    print("Testing Supabase connection...")
    result = curl_call("/fl_counties?select=count&limit=1")
    if result:
        print("✅ Connection successful")
        return True
    else:
        print("❌ Connection failed")
        return False

def evaluate_county(county):
    """Get county evaluation using RPC call"""
    print(f"Evaluating {county}...")
    
    result = curl_call("/rpc/pencil_dod_evaluate_county", "POST", {"county_name": county})
    
    if result:
        # Parse the result and count passes
        if isinstance(result, dict):
            passes = sum(1 for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J'] 
                        if result.get(f"grade_{letter.lower()}") == 'PASS')
            
            print(f"## {county} ({passes}/10)")
            
            for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
                grade = result.get(f"grade_{letter.lower()}", 'FAIL')
                metric = result.get(f"metric_{letter.lower()}", 'null')
                
                status = "PASS" if grade == "PASS" else "FAIL"
                print(f"    {letter} {status} metric={metric}")
        
        return result
    else:
        print(f"❌ Failed to evaluate {county}")
        return None

def main():
    print("🔍 SHARD-1 County Baseline Check")
    print(f"Counties: {', '.join(SHARD1_COUNTIES)}")
    print(f"Time: {subprocess.run(['date'], capture_output=True, text=True).stdout.strip()}")
    print()
    
    if not test_connection():
        print("Cannot proceed without database connection")
        return
    
    print("\n=== County Evaluations ===")
    
    for county in SHARD1_COUNTIES:
        print(f"\n--- {county} ---")
        evaluate_county(county)
    
    print("\n✅ Baseline check complete")

if __name__ == "__main__":
    main()