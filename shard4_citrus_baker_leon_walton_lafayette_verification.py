#!/usr/bin/env python3
"""
SHARD-4 verification script for the assigned counties from Issue #7801
Counties: citrus, baker, leon, walton, lafayette
Based on the Gold Standard brief metrics in the issue
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
    print("Attempting to use CLAUDE.md provided connection info...")

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
                pass_count = sum(1 for item in result if item.get('pass'))
                print(f"  Overall: {pass_count}/10 letters passing")
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    status = "✅" if letter_data.get('pass') else "❌"
                    brief_info = letter_data.get('brief_info', '')
                    print(f"  {letter}: {status} {metric} {brief_info}")
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
        
        # Query multi_county_auctions for the county
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions?select=count&county_slug=eq.{county_slug}",
            headers=sb_headers()
        )
        
        if r.status_code == 200:
            result = r.json()
            count = len(result) if isinstance(result, list) else 0
            print(f"  Multi-county auctions for {county_slug}: {count}")
            return count
        else:
            print(f"❌ Failed to get auction count for {county_slug}: {r.status_code}")
            return 0
            
    except Exception as e:
        print(f"❌ Error getting auction count for {county_slug}: {e}")
        return 0

if __name__ == "__main__":
    print("=== SHARD-4 ASSIGNED COUNTIES VERIFICATION ===")
    print("Counties: citrus, baker, leon, walton, lafayette")
    print("From Issue #7801 Gold Standard brief")
    print()
    
    # These are the metrics from the issue brief for verification
    issue_metrics = {
        'citrus': {'pass_count': 2, 'letters': 'A,E'},
        'baker': {'pass_count': 1, 'letters': 'A'},
        'leon': {'pass_count': 1, 'letters': 'A'}, 
        'walton': {'pass_count': 1, 'letters': 'A'},
        'lafayette': {'pass_count': 0, 'letters': 'none'}
    }
    
    if SUPABASE_KEY and test_connection():
        print("\n=== Fresh County Evaluations ===")
        assigned_counties = ['citrus', 'baker', 'leon', 'walton', 'lafayette']
        
        for county in assigned_counties:
            print(f"\n--- {county} (Expected: {issue_metrics[county]['pass_count']}/10, {issue_metrics[county]['letters']}) ---")
            result = evaluate_county_current(county)
            get_multi_county_auctions_count(county)
            
    else:
        print("\n❌ Cannot connect to database - manual verification needed")
        print("\nExpected metrics from issue brief:")
        for county, data in issue_metrics.items():
            print(f"{county}: {data['pass_count']}/10 ({data['letters']})")