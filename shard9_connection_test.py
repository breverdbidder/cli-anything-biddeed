#!/usr/bin/env python3
"""
SHARD-9 Database Connection Test and County Evaluation
Counties: lee, baker, okaloosa, dixie, taylor

This script tests the database connection and gets current metrics for our assigned counties.
Uses the same pattern as other shard verification scripts.
"""
import os
import requests
import json
from datetime import datetime

# Supabase configuration - follows the existing pattern from other shard scripts
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_KEY:
    print("❌ No SUPABASE_KEY or SUPABASE_SERVICE_KEY found in environment")
    print("Available env vars with 'SUPABASE' in name:")
    for key in os.environ.keys():
        if 'SUPABASE' in key.upper():
            print(f"  {key}={os.environ[key][:10]}..." if len(os.environ[key]) > 10 else f"  {key}={os.environ[key]}")
    exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}", 
    "Content-Type": "application/json"
}

# SHARD-9 assigned counties
SHARD9_COUNTIES = ['lee', 'baker', 'okaloosa', 'dixie', 'taylor']

def test_connection():
    """Test Supabase connection"""
    try:
        response = requests.get(f"{BASE}/audit_log", headers=HEADERS, params={"limit": "1"}, timeout=30)
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
    try:
        # Use RPC call to the evaluation function
        payload = {"county_slug_arg": county}
        response = requests.post(
            f"{BASE}/rpc/pencil_dod_evaluate_county", 
            headers=HEADERS, 
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Evaluation failed for {county}: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error evaluating {county}: {e}")
        return None

def get_auction_counts():
    """Get auction counts for our counties from multi_county_auctions"""
    try:
        for county in SHARD9_COUNTIES:
            response = requests.get(
                f"{BASE}/multi_county_auctions", 
                headers=HEADERS, 
                params={
                    "select": "count",
                    "county_slug": f"eq.{county}"
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                count = data[0]['count'] if data else 0
                print(f"  {county}: {count} auctions in multi_county_auctions")
            else:
                print(f"  {county}: Error getting count - {response.status_code}")
    except Exception as e:
        print(f"❌ Error checking auction counts: {e}")

def main():
    """Main execution"""
    print("=== SHARD-9 Database Connection Test ===")
    print(f"Target Counties: {', '.join(SHARD9_COUNTIES)}")
    print(f"Supabase URL: {SUPABASE_URL}")
    print(f"Key present: {bool(SUPABASE_KEY)}")
    
    # Test connection
    if not test_connection():
        print("❌ Cannot proceed without database connection")
        return 1
    
    print("\n=== County Auction Counts ===")
    get_auction_counts()
    
    print("\n=== Current County Evaluations ===")
    for county in SHARD9_COUNTIES:
        print(f"\n--- {county} ---")
        evaluation = get_county_evaluation(county)
        
        if evaluation and isinstance(evaluation, list):
            pass_count = 0
            for letter_data in evaluation:
                letter = letter_data.get('letter', '?')
                metric = letter_data.get('metric')
                passed = letter_data.get('pass', False)
                details = letter_data.get('details', '')
                
                status = "✅ PASS" if passed else "❌ FAIL"
                if passed:
                    pass_count += 1
                    
                print(f"  {letter}: {status} metric={metric} {details}")
                
            print(f"  TOTAL: {pass_count}/10 letters passing")
        else:
            print(f"  ❌ No evaluation data returned for {county}")
    
    print(f"\n=== Session Complete at {datetime.now().isoformat()} ===")
    return 0

if __name__ == "__main__":
    exit(main())