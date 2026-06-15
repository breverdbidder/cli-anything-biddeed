#!/usr/bin/env python3
"""
SHARD-9 Status Verification
Counties: palm_beach, escambia, okaloosa, dixie, taylor
"""
import os
import sys
import json

# Try importing httpx 
try:
    import httpx
    print("✅ httpx available")
except ImportError:
    print("❌ httpx not available")
    sys.exit(1)

# Setup Supabase connection
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
    """Run pencil_dod_evaluate_county for a county"""
    try:
        client = httpx.Client(timeout=60)
        
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=sb_headers(),
            json={"county_slug_arg": county_slug}
        )
        
        print(f"\n=== {county_slug.upper()} STATUS ===")
        if r.status_code == 200:
            result = r.json()
            if isinstance(result, list) and len(result) > 0:
                pass_count = 0
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    passes = letter_data.get('pass', False)
                    if passes:
                        pass_count += 1
                    status = "✅" if passes else "❌"
                    details = letter_data.get('details', '')
                    print(f"  {letter}: {status} metric={metric} {details}")
                print(f"Score: {pass_count}/10")
                return result
            else:
                print(f"  ❌ No data returned for {county_slug}")
                return None
        else:
            print(f"  ❌ API error {r.status_code}: {r.text}")
            return None
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None

if __name__ == "__main__":
    print("🎯 SHARD-9 GOLD STANDARD STATUS VERIFICATION")
    print("Counties: palm_beach, escambia, okaloosa, dixie, taylor")
    
    if not test_connection():
        sys.exit(1)
    
    # Our assigned counties for SHARD-9
    assigned_counties = ['palm_beach', 'escambia', 'okaloosa', 'dixie', 'taylor']
    
    results = {}
    for county in assigned_counties:
        result = evaluate_county_current(county)
        results[county] = result
    
    print("\n" + "="*60)
    print("📋 SHARD-9 SUMMARY")
    for county in assigned_counties:
        result = results.get(county)
        if result:
            pass_count = sum(1 for item in result if item.get('pass', False))
            print(f"  {county}: {pass_count}/10")
        else:
            print(f"  {county}: ERROR")
    print("Ready for autonomous execution...")