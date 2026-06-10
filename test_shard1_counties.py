#!/usr/bin/env python3
"""
GOLD STANDARD WAVE2-SHARD-1 county analysis
Check current metrics for: st_johns, baker, hendry, nassau, bradford, glades, levy
"""
import os
import sys
import json

try:
    import httpx
    print("✅ httpx available")
except ImportError:
    print("❌ httpx not available")
    sys.exit(1)

# Setup Supabase connection
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
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
                pass_count = sum(1 for letter_data in result if letter_data.get('pass'))
                print(f"  Overall: {pass_count}/10 letters passing")
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    status = "✅" if letter_data.get('pass') else "❌"
                    explanation = letter_data.get('explanation', '')
                    print(f"  {letter}: {status} {metric} - {explanation}")
            else:
                print(f"  No evaluation data returned for {county_slug}")
            return result
        else:
            print(f"❌ Failed to evaluate county {county_slug}: {r.status_code} - {r.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return None

def get_auction_counts(county_name):
    """Get auction counts from multi_county_auctions"""
    try:
        client = httpx.Client(timeout=30)
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions?select=count&county_name=eq.{county_name}",
            headers=sb_headers()
        )
        if r.status_code == 200:
            data = r.json()
            if data and len(data) > 0:
                return data[0].get('count', 0)
            return 0
        else:
            print(f"❌ Failed to get auction count for {county_name}: {r.text}")
            return None
    except Exception as e:
        print(f"❌ Error getting auction count for {county_name}: {e}")
        return None

if __name__ == "__main__":
    print("=== SHARD-1 County Analysis ===")
    
    if not test_connection():
        sys.exit(1)
    
    # SHARD-1 assigned counties
    shard1_counties = ['st_johns', 'baker', 'hendry', 'nassau', 'bradford', 'glades', 'levy']
    
    print("\n=== Fresh County Evaluations ===")
    for county in shard1_counties:
        print(f"\n--- {county} ---")
        
        # Get auction count first
        auction_count = get_auction_counts(county)
        print(f"Auction records: {auction_count if auction_count is not None else 'N/A'}")
        
        # Run evaluation
        evaluate_county_current(county)