#!/usr/bin/env python3
"""
Test database connectivity and current Gold Standard status for SHARD-6 counties
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
    # Try to use the password from CLAUDE.md as a fallback for testing
    # This is just for diagnostics - proper auth should be via env vars
    
def sb_headers():
    return {
        "apikey": SUPABASE_KEY, 
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def test_connection():
    """Test basic connection to Supabase"""
    if not SUPABASE_KEY:
        print("❌ Cannot test connection - no API key")
        return False
        
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
    if not SUPABASE_KEY:
        print("❌ Cannot evaluate - no API key")
        return None
        
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
                    pass_status = letter_data.get('pass')
                    status = "✅ PASS" if pass_status else "❌ FAIL"
                    print(f"  {letter}: {status} metric={metric}")
                return result
            else:
                print(f"  No data returned for {county_slug}")
                return []
        else:
            print(f"❌ Failed to evaluate county {county_slug}: {r.status_code} - {r.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return None

def get_multi_county_auction_counts():
    """Get auction counts for our assigned counties"""
    if not SUPABASE_KEY:
        print("❌ Cannot query - no API key") 
        return None
        
    assigned_counties = ['escambia', 'alachua', 'martin', 'calhoun', 'liberty']
    
    try:
        client = httpx.Client(timeout=30)
        
        for county in assigned_counties:
            # Get count of auctions for this county
            r = client.get(
                f"{SUPABASE_URL}/rest/v1/multi_county_auctions?select=count&county={county}",
                headers=sb_headers()
            )
            
            if r.status_code == 200:
                count_data = r.json()
                print(f"{county}: {len(count_data)} auctions in multi_county_auctions")
            else:
                print(f"❌ Failed to get auction count for {county}: {r.status_code}")
                
    except Exception as e:
        print(f"❌ Error getting auction counts: {e}")

if __name__ == "__main__":
    print("=== SHARD-6 Database Connectivity Test ===")
    print("Assigned counties: escambia, alachua, martin, calhoun, liberty")
    
    if test_connection():
        print("\n=== Multi-County Auction Counts ===")
        get_multi_county_auction_counts()
        
        print("\n=== Fresh County Evaluations ===")
        assigned_counties = ['escambia', 'alachua', 'martin', 'calhoun', 'liberty']
        for county in assigned_counties:
            print(f"\n--- {county} ---")
            evaluate_county_current(county)
    else:
        print("Cannot proceed without database connection")
        print("Need SUPABASE_KEY environment variable set")