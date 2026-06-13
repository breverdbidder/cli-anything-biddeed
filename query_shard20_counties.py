#!/usr/bin/env python3
"""
Query current metrics for SHARD 20: charlotte, citrus, broward
Gold Standard Autopilot Session - Session 20
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

# Setup Supabase connection using environment variables
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
            print(f"\n=== {county_slug.upper()} EVALUATION ===")
            if isinstance(result, list) and len(result) > 0:
                passes = 0
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    pass_status = letter_data.get('pass', False)
                    if pass_status:
                        passes += 1
                    status = "✅ PASS" if pass_status else "❌ FAIL"
                    print(f"  {letter}: {status} - {metric}")
                print(f"  TOTAL: {passes}/10")
            return result
        else:
            print(f"❌ Failed to evaluate county {county_slug}: {r.status_code} - {r.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return None

def get_gold_standard_status():
    """Get current Gold Standard metrics for assigned counties"""
    assigned_counties = ['charlotte', 'citrus', 'broward']
    
    try:
        client = httpx.Client(timeout=30)
        
        # Get latest gold standard status for our counties
        counties_filter = ','.join(f'"{c}"' for c in assigned_counties)
        url = f"{SUPABASE_URL}/rest/v1/gold_standard_county_status"
        params = f"select=*&county_slug=in.({counties_filter})&order=loop_run_id.desc&limit=30"
        
        r = client.get(f"{url}?{params}", headers=sb_headers())
        
        if r.status_code == 200:
            results = r.json()
            print(f"✅ Retrieved {len(results)} Gold Standard records")
            
            # Group by county and get latest for each
            latest_by_county = {}
            for record in results:
                county = record.get('county_slug')
                if county not in latest_by_county:
                    latest_by_county[county] = record
                    
            return latest_by_county
        else:
            print(f"❌ Failed to retrieve Gold Standard status: {r.status_code} - {r.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error retrieving Gold Standard status: {e}")
        return None

if __name__ == "__main__":
    print("=== SHARD 20 GOLD STANDARD STATUS ===")
    print("Counties: charlotte, citrus, broward")
    
    if not test_connection():
        sys.exit(1)
    
    print("\n=== FRESH COUNTY EVALUATIONS (VERIFICATION PROTOCOL) ===")
    assigned_counties = ['charlotte', 'citrus', 'broward']
    
    all_results = {}
    for county in assigned_counties:
        result = evaluate_county_current(county)
        all_results[county] = result
    
    print("\n=== RAW JSON RESULTS ===")
    for county, data in all_results.items():
        print(f"\n{county}: {json.dumps(data, indent=2)}")
    
    print("\n=== HISTORICAL STATUS ===")
    status = get_gold_standard_status()
    if status:
        for county, data in status.items():
            print(f"\n{county}:")
            print(f"  Loop run: {data.get('loop_run_id')}")
            print(f"  Pass count: {data.get('pass_count', 'N/A')}/10")
            print(f"  Last updated: {data.get('updated_at')}")