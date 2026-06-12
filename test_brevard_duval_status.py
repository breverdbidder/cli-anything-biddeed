#!/usr/bin/env python3
"""
Test database connectivity and get current Gold Standard status for brevard + duval
GOLD STANDARD AUTOPILOT-BD Session - 08:00Z wave
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
    print("⚠️  Note: This test requires SUPABASE_KEY env var for live DB access")
    print("⚠️  Proceeding with read-only operations if possible...")
    # Don't exit - try to proceed with limited access

def sb_headers():
    return {
        "apikey": SUPABASE_KEY, 
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def test_connection():
    """Test basic connection to Supabase"""
    if not SUPABASE_KEY:
        print("❌ Cannot test connection without API key")
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
                    details = letter_data.get('details', '')
                    print(f"  {letter}: {status} metric={metric} [{details}]")
            return result
        else:
            print(f"❌ Failed to evaluate county {county_slug}: {r.status_code} - {r.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return None

def get_gold_standard_scoreboard():
    """Get current scoreboard data"""
    try:
        client = httpx.Client(timeout=30)
        
        # Get brevard and duval from gold_standard_county_status
        counties_filter = '"brevard","duval"'
        url = f"{SUPABASE_URL}/rest/v1/gold_standard_county_status"
        params = f"select=*&county_slug=in.({counties_filter})&order=loop_run_id.desc&limit=10"
        
        r = client.get(f"{url}?{params}", headers=sb_headers())
        
        if r.status_code == 200:
            results = r.json()
            print(f"✅ Retrieved {len(results)} scoreboard records")
            
            # Group by county and get latest for each
            latest_by_county = {}
            for record in results:
                county = record.get('county_slug')
                if county not in latest_by_county:
                    latest_by_county[county] = record
                    
            return latest_by_county
        else:
            print(f"❌ Failed to retrieve scoreboard: {r.status_code} - {r.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error retrieving scoreboard: {e}")
        return None

if __name__ == "__main__":
    print("=== GOLD STANDARD AUTOPILOT-BD: brevard + duval Status ===")
    
    if not test_connection():
        sys.exit(1)
    
    print("\n=== Current Scoreboard Status ===")
    status = get_gold_standard_scoreboard()
    if status:
        for county, data in status.items():
            print(f"\n{county}:")
            print(f"  Loop run: {data.get('loop_run_id')}")
            print(f"  Pass count: {data.get('pass_count', 'N/A')}/10")
            print(f"  Last updated: {data.get('updated_at')}")
    
    print("\n=== Fresh County Evaluations (VERIFICATION REQUIRED) ===")
    assigned_counties = ['brevard', 'duval']
    evaluation_results = {}
    
    for county in assigned_counties:
        print(f"\n--- {county} ---")
        result = evaluate_county_current(county)
        evaluation_results[county] = result
        
    print("\n=== SUMMARY FOR SESSION PLANNING ===")
    for county, results in evaluation_results.items():
        if results:
            pass_count = sum(1 for r in results if r.get('pass', False))
            fail_letters = [r.get('letter') for r in results if not r.get('pass', False)]
            print(f"{county}: {pass_count}/10 passing, failing letters: {fail_letters}")