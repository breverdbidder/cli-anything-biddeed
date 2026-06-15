#!/usr/bin/env python3
"""
SHARD-7 County Status Verification
Check current A-J letter grades for leon, clay, miami_dade, columbia, madison

Usage:
  python shard7_status_check.py
"""
import os
import json
from datetime import datetime

# Try both requests and httpx
try:
    import requests
    HTTP_CLIENT = 'requests'
    print("✅ Using requests for HTTP")
except ImportError:
    try:
        import httpx
        HTTP_CLIENT = 'httpx'
        print("✅ Using httpx for HTTP")
    except ImportError:
        print("❌ Neither requests nor httpx available")
        exit(1)

# Supabase configuration  
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}", 
    "Content-Type": "application/json"
}

# Target counties for SHARD-7
SHARD7_COUNTIES = ['leon', 'clay', 'miami_dade', 'columbia', 'madison']

def make_request(method, url, **kwargs):
    """Make HTTP request using available client"""
    if HTTP_CLIENT == 'requests':
        if method == 'GET':
            return requests.get(url, **kwargs)
        elif method == 'POST':
            return requests.post(url, **kwargs)
    else:  # httpx
        client = httpx.Client(timeout=30)
        if method == 'GET':
            return client.get(url, **kwargs)
        elif method == 'POST':
            return client.post(url, **kwargs)

def test_connection():
    """Test Supabase connection"""
    print(f"Testing connection to: {SUPABASE_URL}")
    print(f"API Key present: {bool(SUPABASE_KEY)}")
    
    if not SUPABASE_KEY:
        print("❌ No Supabase API key available")
        return False
        
    try:
        response = make_request('GET', f"{BASE}/audit_log", headers=HEADERS, params={"limit": "1"}, timeout=10)
        if response.status_code == 200:
            print("✅ Supabase connection successful")
            return True
        else:
            print(f"❌ Connection failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def get_county_evaluation(county):
    """Get evaluation for a specific county using pencil_dod_evaluate_county function"""
    print(f"\n--- Evaluating {county.upper()} ---")
    try:
        # Use RPC call to the evaluation function
        payload = {"county_slug_arg": county}
        response = make_request(
            'POST',
            f"{BASE}/rpc/pencil_dod_evaluate_county", 
            headers=HEADERS, 
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                pass_count = 0
                fail_count = 0
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    passes = letter_data.get('pass', False)
                    if passes:
                        pass_count += 1
                    else:
                        fail_count += 1
                    status = "✅ PASS" if passes else "❌ FAIL"
                    print(f"  {letter}: {status} metric={metric}")
                
                print(f"\n{county}: {pass_count}/10 PASS, {fail_count}/10 FAIL")
                return result
            else:
                print(f"  ❌ No evaluation data returned for {county}")
                return None
        else:
            print(f"  ❌ API error {response.status_code}: {response.text}")
            return None
            
    except Exception as e:
        print(f"  ❌ Error evaluating {county}: {e}")
        return None

def get_auction_counts():
    """Get basic auction counts for verification"""
    print("\n=== AUCTION COUNTS ===")
    for county in SHARD7_COUNTIES:
        try:
            response = make_request(
                'GET',
                f"{BASE}/multi_county_auctions", 
                headers=HEADERS, 
                params={"county": county, "select": "count"},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                count = len(data) if isinstance(data, list) else 0
                print(f"  {county}: {count} auctions")
            else:
                print(f"  {county}: API error {response.status_code}")
        except Exception as e:
            print(f"  {county}: Error - {e}")

def main():
    print("🎯 GOLD STANDARD SHARD-7 STATUS VERIFICATION")
    print(f"Counties: {', '.join(SHARD7_COUNTIES)}")
    print(f"Time: {datetime.now().isoformat()}")
    
    # Test connection first
    if not test_connection():
        print("❌ Cannot connect to database. Exiting.")
        return False
    
    # Get auction counts
    get_auction_counts()
    
    print("\n=== COUNTY EVALUATIONS ===")
    
    # Evaluate each county
    results = {}
    for county in SHARD7_COUNTIES:
        evaluation = get_county_evaluation(county)
        results[county] = evaluation
    
    # Summary
    print("\n" + "="*60)
    print("📊 SHARD-7 STATUS SUMMARY")
    total_counties = len(SHARD7_COUNTIES)
    counties_with_data = sum(1 for r in results.values() if r is not None)
    
    print(f"Counties evaluated: {counties_with_data}/{total_counties}")
    
    for county, result in results.items():
        if result:
            pass_count = sum(1 for item in result if item.get('pass', False))
            print(f"  {county}: {pass_count}/10")
        else:
            print(f"  {county}: No data")
    
    return True

if __name__ == "__main__":
    success = main()
    if success:
        print("\n✅ Status verification complete")
    else:
        print("\n❌ Status verification failed")
        exit(1)