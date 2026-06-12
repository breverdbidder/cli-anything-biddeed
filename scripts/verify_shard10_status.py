#!/usr/bin/env python3
"""
SHARD-10 County Status Verification
Check current A-J letter grades for leon, baker, okaloosa, franklin, union

Usage:
  python scripts/verify_shard10_status.py
"""
import os
import requests
import json
from datetime import datetime

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}", 
    "Content-Type": "application/json"
}

# Target counties for SHARD-10
SHARD10_COUNTIES = ['leon', 'baker', 'okaloosa', 'franklin', 'union']

def test_connection():
    """Test Supabase connection"""
    if not SUPABASE_KEY:
        print("❌ No Supabase API key found")
        return False
        
    try:
        response = requests.get(f"{BASE}/audit_log", headers=HEADERS, params={"limit": "1"}, timeout=10)
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
    """Get current evaluation for a county using pencil_dod_evaluate_county"""
    try:
        response = requests.post(
            f"{BASE}/rpc/pencil_dod_evaluate_county",
            headers=HEADERS,
            json={"county_slug_arg": county_slug},
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n## {county_slug}")
            
            pass_count = 0
            letters = {}
            
            if isinstance(result, list):
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    is_pass = letter_data.get('pass', False)
                    details = letter_data.get('details', '')
                    
                    letters[letter] = {
                        'metric': metric,
                        'pass': is_pass,
                        'details': details
                    }
                    
                    if is_pass:
                        pass_count += 1
                    
                    status = "PASS" if is_pass else "FAIL"
                    print(f"    {letter} {status} metric={metric} [{details}]")
            
            print(f"    OVERALL: {pass_count}/10")
            return letters
        else:
            print(f"❌ Failed to evaluate {county_slug}: {response.status_code}")
            if response.text:
                print(f"    Error: {response.text[:200]}")
            return None
            
    except Exception as e:
        print(f"❌ Error evaluating {county_slug}: {e}")
        return None

def main():
    print("=== SHARD-10 Gold Standard Status Verification ===")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Counties: {', '.join(SHARD10_COUNTIES)}")
    
    if not test_connection():
        return 1
    
    print("\n=== County Evaluations ===")
    
    county_results = {}
    for county in SHARD10_COUNTIES:
        letters = evaluate_county(county)
        if letters:
            county_results[county] = letters
    
    # Summary analysis
    print(f"\n=== Summary ===")
    
    for county, letters in county_results.items():
        pass_count = sum(1 for data in letters.values() if data['pass'])
        print(f"{county}: {pass_count}/10 passes")
        
        # Identify critical failures (B, I, J)
        critical_letters = ['B', 'I', 'J']
        critical_fails = []
        for letter in critical_letters:
            if letter in letters and not letters[letter]['pass']:
                critical_fails.append(letter)
        
        if critical_fails:
            print(f"  Critical failures: {', '.join(critical_fails)}")
    
    return 0

if __name__ == "__main__":
    exit(main())