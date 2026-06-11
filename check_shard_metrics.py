#!/usr/bin/env python3
"""
Check current Gold Standard metrics for SHARD-10 counties:
manatee, alachua, martin, franklin, union
"""
import os
import sys
import json
import urllib.request
import urllib.parse

# Setup Supabase connection - using hardcoded values from CLAUDE.md
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
# Try multiple environment variable names for API key
SUPABASE_KEY = (
    os.environ.get("SUPABASE_KEY") or 
    os.environ.get("SUPABASE_SERVICE_KEY") or
    os.environ.get("SUPABASE_ANON_KEY") or
    ""
)

print(f"Using Supabase URL: {SUPABASE_URL}")
print(f"API Key present: {bool(SUPABASE_KEY)}")

def sb_headers():
    return {
        "apikey": SUPABASE_KEY, 
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def test_connection():
    """Test basic connection to Supabase"""
    try:
        client = httpx.Client(timeout=30)
        r = client.get(f"{SUPABASE_URL}/rest/v1/fl_counties?select=count&limit=1", headers=sb_headers())
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
        client = httpx.Client(timeout=60)
        
        # Call the RPC function
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=sb_headers(),
            json={"county_slug_arg": county_slug}
        )
        
        if r.status_code == 200:
            result = r.json()
            print(f"✅ County evaluation for {county_slug}:")
            if isinstance(result, list) and len(result) > 0:
                pass_count = 0
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    is_pass = letter_data.get('pass', False)
                    if is_pass:
                        pass_count += 1
                    status = "✅ PASS" if is_pass else "❌ FAIL"
                    print(f"  {letter}: {status} metric={metric}")
                print(f"  TOTAL: {pass_count}/10")
            return result
        else:
            print(f"❌ Failed to evaluate county {county_slug}: {r.status_code} - {r.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return None

if __name__ == "__main__":
    print("=== SHARD-10 Counties Gold Standard Check ===")
    
    if not SUPABASE_KEY:
        print("❌ No Supabase API key found in environment")
        print("Available env vars:", [k for k in os.environ.keys() if 'SUPABASE' in k or 'API' in k])
        sys.exit(1)
    
    if not test_connection():
        sys.exit(1)
    
    print("\n=== Fresh County Evaluations ===")
    assigned_counties = ['manatee', 'alachua', 'martin', 'franklin', 'union']
    
    for county in assigned_counties:
        print(f"\n--- {county.upper()} ---")
        evaluate_county_current(county)