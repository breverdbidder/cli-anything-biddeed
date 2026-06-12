#!/usr/bin/env python3
"""
SHARD-10 Gold Standard metrics check
Assigned counties: leon, baker, okaloosa, franklin, union
"""
import os
import json
import httpx
from datetime import datetime

# Configuration from environment (as per CLAUDE.md)
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

SHARD10_COUNTIES = ['leon', 'baker', 'okaloosa', 'franklin', 'union']

def test_connection():
    """Test basic connectivity"""
    if not SUPABASE_KEY:
        print("❌ No Supabase API key found")
        return False
        
    try:
        client = httpx.Client(timeout=10)
        response = client.get(f"{BASE}/fl_counties?select=count&limit=1", headers=HEADERS)
        if response.status_code == 200:
            print("✅ Database connection successful")
            return True
        else:
            print(f"❌ Connection failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def evaluate_county(county_slug):
    """Run pencil_dod_evaluate_county for a county"""
    try:
        client = httpx.Client(timeout=60)
        
        # Call the RPC function
        response = client.post(
            f"{BASE}/rpc/pencil_dod_evaluate_county",
            headers=HEADERS,
            json={"county_slug_arg": county_slug}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"County: {county_slug}")
            
            pass_count = 0
            total_letters = 10
            
            if isinstance(result, list):
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric', 'null')
                    is_pass = letter_data.get('pass', False)
                    details = letter_data.get('details', '')
                    
                    if is_pass:
                        pass_count += 1
                        
                    status = "PASS" if is_pass else "FAIL"
                    print(f"    {letter} {status} metric={metric} [{details}]")
                    
            print(f"    TOTAL: {pass_count}/{total_letters}")
            return result
        else:
            print(f"❌ Failed to evaluate {county_slug}: {response.status_code} - {response.text[:200]}")
            return None
            
    except Exception as e:
        print(f"❌ Error evaluating {county_slug}: {e}")
        return None

def main():
    print("=== SHARD-10 Gold Standard Metrics ===")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    if not test_connection():
        return 1
    
    print(f"\nEvaluating {len(SHARD10_COUNTIES)} counties...")
    
    for county in SHARD10_COUNTIES:
        print(f"\n## {county}")
        evaluate_county(county)
    
    return 0

if __name__ == "__main__":
    exit(main())