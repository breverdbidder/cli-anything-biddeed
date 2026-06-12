#!/usr/bin/env python3
"""
Quick script to check current Gold Standard metrics for MY assigned counties:
charlotte, citrus, broward
"""
import os
import sys
import json

# Try importing requests 
try:
    import requests
    print("✅ requests available")
except ImportError:
    print("❌ requests not available")
    sys.exit(1)

# Setup Supabase connection using environment variables or hardcoded values
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

print(f"Using Supabase URL: {SUPABASE_URL}")
print(f"API Key present: {bool(SUPABASE_KEY)}")

if not SUPABASE_KEY:
    print("❌ No Supabase API key found in environment")
    sys.exit(1)

def sb_headers():
    return {
        "apikey": SUPABASE_KEY, 
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def test_connection():
    """Test basic connection to Supabase"""
    try:
        r = requests.get(f"{SUPABASE_URL}/rest/v1/fl_counties?select=count&limit=1", headers=sb_headers(), timeout=30)
        print(f"Connection status: {r.status_code}")
        if r.status_code == 200:
            print("✅ Database connection successful")
            return True
        else:
            print(f"❌ Database connection failed: {r.text}")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def evaluate_county_current(county_slug):
    """Run the pencil_dod_evaluate_county function for a single county"""
    try:
        # Call the RPC function
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=sb_headers(),
            json={"county_slug_arg": county_slug},
            timeout=60
        )
        
        if r.status_code == 200:
            result = r.json()
            print(f"✅ County evaluation for {county_slug}:")
            if isinstance(result, list) and len(result) > 0:
                pass_count = sum(1 for item in result if item.get('pass'))
                print(f"   SCORE: {pass_count}/10")
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    status = "✅" if letter_data.get('pass') else "❌"
                    notes = letter_data.get('notes', '')
                    print(f"   {letter}: {status} {metric} {notes}")
            return result
        else:
            print(f"❌ Failed to evaluate county {county_slug}: {r.status_code} - {r.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return None

if __name__ == "__main__":
    print("=== MY SHARD County Evaluations ===")
    print("Assigned Counties: charlotte, citrus, broward")
    
    if not test_connection():
        sys.exit(1)
    
    my_assigned_counties = ['charlotte', 'citrus', 'broward']
    county_results = {}
    
    for county in my_assigned_counties:
        print(f"\n--- {county} ---")
        result = evaluate_county_current(county)
        county_results[county] = result
    
    print("\n=== SUMMARY ===")
    for county, result in county_results.items():
        if result:
            pass_count = sum(1 for item in result if item.get('pass'))
            failing_letters = [item.get('letter') for item in result if not item.get('pass')]
            print(f"{county}: {pass_count}/10 - Failing: {', '.join(failing_letters)}")
        else:
            print(f"{county}: EVALUATION_FAILED")