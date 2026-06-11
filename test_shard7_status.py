#!/usr/bin/env python3
"""
SHARD-7 Gold Standard Status Checker
Test connectivity and get current metrics for assigned counties:
hillsborough, suwannee, lake, columbia, madison
"""
import os
import sys
import json
import urllib.request
import urllib.parse
import urllib.error

print("✅ Using urllib for HTTP requests")

# Setup Supabase connection using environment variables or hardcoded values
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

print(f"Using Supabase URL: {SUPABASE_URL}")
print(f"API Key present: {bool(SUPABASE_KEY)}")

if not SUPABASE_KEY:
    print("❌ No Supabase API key found in environment")
    # Try to continue anyway for testing
    SUPABASE_KEY = "mock_key"

def sb_headers():
    return {
        "apikey": SUPABASE_KEY, 
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def test_connection():
    """Test basic connection to Supabase"""
    try:
        url = f"{SUPABASE_URL}/rest/v1/fl_counties?select=count&limit=1"
        req = urllib.request.Request(url, headers=sb_headers())
        
        with urllib.request.urlopen(req, timeout=30) as response:
            status = response.getcode()
            print(f"Connection status: {status}")
            if status == 200:
                print("✅ Database connection successful")
                return True
            else:
                print(f"❌ Database connection failed: status {status}")
                return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def evaluate_county_current(county_slug):
    """Run the pencil_dod_evaluate_county function for a single county"""
    try:
        url = f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county"
        data = json.dumps({"county_slug_arg": county_slug}).encode('utf-8')
        
        req = urllib.request.Request(url, data=data, headers=sb_headers(), method='POST')
        
        with urllib.request.urlopen(req, timeout=60) as response:
            status = response.getcode()
            response_data = response.read()
            
            if status == 200:
                result = json.loads(response_data.decode('utf-8'))
                print(f"✅ County evaluation for {county_slug}:")
                if isinstance(result, list) and len(result) > 0:
                    for letter_data in result:
                        letter = letter_data.get('letter', '?')
                        metric = letter_data.get('metric')
                        status_icon = "✅" if letter_data.get('pass') else "❌"
                        evidence = letter_data.get('evidence', '')
                        print(f"  {letter}: {status_icon} {metric} [{evidence}]")
                    
                    # Count passing metrics
                    pass_count = sum(1 for ld in result if ld.get('pass'))
                    print(f"  SCORE: {pass_count}/10")
                    return result
                else:
                    print(f"  No evaluation data returned")
                    return []
            else:
                print(f"❌ Failed to evaluate county {county_slug}: status {status}")
                return None
                
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return None

if __name__ == "__main__":
    print("=== SHARD-7 Database Connectivity Test ===")
    
    connection_ok = test_connection()
    
    print("\n=== SHARD-7 County Evaluations ===")
    assigned_counties = ['hillsborough', 'suwannee', 'lake', 'columbia', 'madison']
    
    all_results = {}
    for county in assigned_counties:
        print(f"\n--- {county} ---")
        result = evaluate_county_current(county)
        all_results[county] = result
    
    # Summary
    print("\n=== SHARD-7 SUMMARY ===")
    for county, result in all_results.items():
        if result is not None:
            if isinstance(result, list):
                pass_count = sum(1 for ld in result if ld.get('pass'))
                print(f"{county}: {pass_count}/10 (A-J letters)")
            else:
                print(f"{county}: ERROR")
        else:
            print(f"{county}: NO DATA")