#!/usr/bin/env python3
"""
Query gold standard metrics for charlotte, citrus, and broward counties
"""
import os
import sys
import json
import requests
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

print(f"Using Supabase URL: {SUPABASE_URL}")
print(f"API Key present: {bool(SUPABASE_KEY)}")

if not SUPABASE_KEY:
    print("❌ No Supabase API key found in environment")
    sys.exit(1)

def evaluate_county_current(county_slug):
    """Run the pencil_dod_evaluate_county function for a single county"""
    try:
        print(f"\n=== Executing SELECT public.pencil_dod_evaluate_county('{county_slug}'); ===")
        
        # Try both parameter patterns as found in verify_shard1_status.py
        for param_name in ["county_slug_arg", "county_name"]:
            payload = {param_name: county_slug}
            response = requests.post(
                f"{BASE}/rpc/pencil_dod_evaluate_county", 
                headers=HEADERS, 
                json=payload,
                timeout=60
            )
            
            print(f"Attempt with {param_name}: Status {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                if result:  # If we got data, this param name worked
                    print(f"SUCCESS - Raw result: {json.dumps(result, indent=2)}")
                    return result
            elif param_name == "county_name":  # Last attempt failed
                print(f"❌ Failed to evaluate {county_slug}: {response.status_code}")
                print(f"Error response: {response.text}")
                return None
        
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return None
    
    return None

def get_gold_standard_status(counties):
    """Get current gold_standard_county_status for specified counties"""
    try:
        counties_filter = ','.join(f'"{c}"' for c in counties)
        params = {
            "select": "*",
            "county_slug": f"in.({counties_filter})",
            "order": "loop_run_id.desc",
            "limit": "50"
        }
        
        print(f"\n=== Querying gold_standard_county_status table for: {', '.join(counties)} ===")
        print(f"Query URL: {BASE}/gold_standard_county_status")
        print(f"Query params: {params}")
        
        response = requests.get(
            f"{BASE}/gold_standard_county_status",
            headers=HEADERS,
            params=params,
            timeout=30
        )
        
        print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            results = response.json()
            print(f"Raw results: {json.dumps(results, indent=2)}")
            return results
        else:
            print(f"❌ Failed to retrieve gold_standard_county_status: {response.status_code}")
            print(f"Error response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error retrieving gold_standard_county_status: {e}")
        return None

if __name__ == "__main__":
    # Counties requested by user
    requested_counties = ['charlotte', 'citrus', 'broward']
    
    print("=== GOLD STANDARD COUNTY METRICS QUERY ===")
    print(f"Querying counties: {', '.join(requested_counties)}")
    
    # 1. Get current metrics from gold_standard_county_status table
    status_results = get_gold_standard_status(requested_counties)
    
    # 2. Run pencil_dod_evaluate_county for each county
    evaluation_results = {}
    for county in requested_counties:
        evaluation_results[county] = evaluate_county_current(county)
    
    print("\n=== SUMMARY ===")
    print(f"gold_standard_county_status records retrieved: {len(status_results) if status_results else 0}")
    for county, result in evaluation_results.items():
        status = "✅ SUCCESS" if result is not None else "❌ FAILED"
        print(f"pencil_dod_evaluate_county('{county}'): {status}")