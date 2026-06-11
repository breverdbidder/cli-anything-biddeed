#!/usr/bin/env python3
"""
Simple check for SHARD-10 counties Gold Standard metrics using urllib
manatee, alachua, martin, franklin, union
"""
import os
import sys
import json
import urllib.request
import urllib.parse

# Setup Supabase connection - using hardcoded values from CLAUDE.md
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_KEY = (
    os.environ.get("SUPABASE_KEY") or 
    os.environ.get("SUPABASE_SERVICE_KEY") or
    ""
)

def make_supabase_request(endpoint, data=None):
    """Make a request to Supabase REST API"""
    if not SUPABASE_KEY:
        print("❌ No Supabase API key available")
        return None
    
    url = f"{SUPABASE_URL}/{endpoint}"
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json'
    }
    
    try:
        if data:
            # POST request
            data_bytes = json.dumps(data).encode('utf-8')
            req = urllib.request.Request(url, data=data_bytes, headers=headers)
            req.add_header('Content-Type', 'application/json')
        else:
            # GET request
            req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=30) as response:
            if response.status == 200:
                return json.loads(response.read().decode('utf-8'))
            else:
                print(f"❌ Request failed: {response.status}")
                return None
    except Exception as e:
        print(f"❌ Request error: {e}")
        return None

def check_connection():
    """Test basic connection to Supabase"""
    result = make_supabase_request("rest/v1/fl_counties?select=count&limit=1")
    if result is not None:
        print("✅ Database connection successful")
        return True
    return False

def evaluate_county(county_slug):
    """Evaluate a county using the pencil_dod_evaluate_county RPC function"""
    result = make_supabase_request(
        "rest/v1/rpc/pencil_dod_evaluate_county",
        {"county_slug_arg": county_slug}
    )
    
    if result:
        print(f"✅ {county_slug.upper()}:")
        if isinstance(result, list):
            pass_count = 0
            for letter_data in result:
                letter = letter_data.get('letter', '?')
                metric = letter_data.get('metric')
                is_pass = letter_data.get('pass', False)
                if is_pass:
                    pass_count += 1
                status = "✅ PASS" if is_pass else "❌ FAIL"
                details = letter_data.get('details', {})
                print(f"  {letter}: {status} metric={metric}")
                
                # Show specific details for failing metrics
                if not is_pass and details:
                    for key, value in details.items():
                        if key != 'metric':
                            print(f"    {key}={value}")
            
            print(f"  TOTAL: {pass_count}/10")
            return result
    return None

if __name__ == "__main__":
    print("=== SHARD-10 Gold Standard Check ===")
    print(f"Using Supabase URL: {SUPABASE_URL}")
    print(f"API Key present: {bool(SUPABASE_KEY)}")
    
    if not SUPABASE_KEY:
        print("❌ No Supabase API key found")
        print("Available env vars with 'SUPABASE':", [k for k in os.environ.keys() if 'SUPABASE' in k])
        print("Available env vars with 'API':", [k for k in os.environ.keys() if 'API' in k])
        sys.exit(1)
    
    if not check_connection():
        sys.exit(1)
    
    print("\n=== County Evaluations ===")
    assigned_counties = ['manatee', 'alachua', 'martin', 'franklin', 'union']
    
    for county in assigned_counties:
        print(f"\n--- {county.upper()} ---")
        evaluate_county(county)