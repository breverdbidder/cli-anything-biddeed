#!/usr/bin/env python3
"""
Test database connectivity and get current Gold Standard status for brevard and duval counties
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
    # For GitHub Actions, try using hardcoded values from CLAUDE.md
    print("Attempting to retrieve from secrets...")
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
                    passed = letter_data.get('pass', False)
                    if passed:
                        pass_count += 1
                    status = "✅" if passed else "❌"
                    print(f"  {letter}: {status} {metric}")
                print(f"  Overall: {pass_count}/10 criteria passing")
            return result
        else:
            print(f"❌ Failed to evaluate county {county_slug}: {r.status_code} - {r.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return None

def get_current_auction_counts(county_slug):
    """Get current auction counts for analysis"""
    try:
        client = httpx.Client(timeout=30)
        
        # Get basic auction counts
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions?select=count()&county_slug=eq.{county_slug}",
            headers=sb_headers()
        )
        
        if r.status_code == 200:
            result = r.json()
            if result and len(result) > 0:
                count = result[0].get('count', 0)
                print(f"  Total auctions: {count}")
                return count
        
        return None
    except Exception as e:
        print(f"❌ Error getting auction counts for {county_slug}: {e}")
        return None

if __name__ == "__main__":
    print("=== Database Connectivity Test ===")
    
    if not test_connection():
        print("Trying alternative connection method...")
        # Could add fallback logic here if needed
        sys.exit(1)
    
    print("\n=== Assigned Counties Evaluation ===")
    assigned_counties = ['brevard', 'duval']  # As specified in the issue
    
    results = {}
    for county in assigned_counties:
        print(f"\n--- {county} ---")
        evaluation = evaluate_county_current(county)
        auction_count = get_current_auction_counts(county)
        results[county] = {
            'evaluation': evaluation,
            'auction_count': auction_count
        }
    
    print("\n=== Summary ===")
    for county, data in results.items():
        print(f"{county}:")
        if data['evaluation']:
            pass_count = sum(1 for item in data['evaluation'] if item.get('pass', False))
            print(f"  Status: {pass_count}/10 criteria passing")
        if data['auction_count']:
            print(f"  Auctions: {data['auction_count']}")