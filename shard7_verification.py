#!/usr/bin/env python3
"""
SHARD-7 Database Verification - Counties: leon, clay, miami_dade, columbia, madison
Tests connection and evaluates current Gold Standard status
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
                pass_count = 0
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    status = "✅" if letter_data.get('pass') else "❌"
                    if letter_data.get('pass'):
                        pass_count += 1
                    print(f"  {letter}: {status} {metric}")
                print(f"  Pass count: {pass_count}/10")
            return result
        else:
            print(f"❌ Failed to evaluate county {county_slug}: {r.status_code} - {r.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return None

def get_county_auction_counts():
    """Get basic auction counts for our assigned counties"""
    assigned_counties = ['leon', 'clay', 'miami_dade', 'columbia', 'madison']
    
    try:
        client = httpx.Client(timeout=30)
        
        for county in assigned_counties:
            # Get auction count
            r = client.get(
                f"{SUPABASE_URL}/rest/v1/multi_county_auctions?select=count&county={county}",
                headers=sb_headers()
            )
            
            if r.status_code == 200:
                result = r.json()
                count = len(result) if isinstance(result, list) else 0
                print(f"  {county}: {count} auctions")
            else:
                print(f"  {county}: error getting count")
                
    except Exception as e:
        print(f"❌ Error getting auction counts: {e}")

if __name__ == "__main__":
    print("=== SHARD-7 Database Connectivity Test ===")
    
    if not test_connection():
        sys.exit(1)
    
    print("\n=== Auction Counts ===")
    get_county_auction_counts()
    
    print("\n=== Fresh County Evaluations ===")
    assigned_counties = ['leon', 'clay', 'miami_dade', 'columbia', 'madison']
    for county in assigned_counties:
        print(f"\n--- {county} ---")
        evaluate_county_current(county)