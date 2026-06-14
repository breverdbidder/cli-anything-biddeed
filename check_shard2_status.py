#!/usr/bin/env python3
"""
Check current Gold Standard status for SHARD-2 counties
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
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    status = "✅ PASS" if letter_data.get('pass') else "❌ FAIL"
                    print(f"  {letter}: {status} metric={metric}")
            return result
        else:
            print(f"❌ Failed to evaluate county {county_slug}: {r.status_code} - {r.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return None

def get_multi_county_auctions_count(county_slug):
    """Get count of multi_county_auctions for a county"""
    try:
        client = httpx.Client(timeout=30)
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions?select=count&county_slug=eq.{county_slug}",
            headers=sb_headers()
        )
        if r.status_code == 200:
            data = r.json()
            if len(data) > 0:
                return data[0].get('count', 0)
        return 0
    except Exception as e:
        print(f"❌ Error getting auction count for {county_slug}: {e}")
        return 0

if __name__ == "__main__":
    print("=== SHARD-2 Database Connectivity Test ===")
    
    if not test_connection():
        sys.exit(1)
    
    print("\n=== SHARD-2 County Evaluations ===")
    # SHARD-2 assigned counties per the issue
    assigned_counties = ['broward', 'baker', 'leon', 'st_lucie', 'holmes']
    
    all_results = {}
    
    for county in assigned_counties:
        print(f"\n--- {county} ---")
        
        # Get auction count first
        auction_count = get_multi_county_auctions_count(county)
        print(f"Auction records: {auction_count}")
        
        # Get current evaluation
        evaluation = evaluate_county_current(county)
        
        if evaluation:
            all_results[county] = {
                'auction_count': auction_count,
                'evaluation': evaluation
            }
    
    # Summary
    print("\n" + "="*60)
    print("SHARD-2 COUNTY STATUS SUMMARY")
    print("="*60)
    
    for county_name, county_data in all_results.items():
        if 'evaluation' in county_data:
            pass_count = sum(1 for letter in county_data['evaluation'] if letter.get('pass'))
            total_letters = len(county_data['evaluation'])
            print(f"{county_name}: {pass_count}/{total_letters} PASS, {county_data['auction_count']} auctions")
        else:
            print(f"{county_name}: NO DATA, {county_data.get('auction_count', 0)} auctions")