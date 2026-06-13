#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-8 Verification Script
Quick test to check database connectivity and current Gold Standard status for:
hillsborough, alachua, nassau, desoto, monroe
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

def get_current_gold_standard_status():
    """Get current Gold Standard metrics for our assigned counties"""
    assigned_counties = ['hillsborough', 'alachua', 'nassau', 'desoto', 'monroe']
    
    try:
        client = httpx.Client(timeout=30)
        
        # Try to get latest gold standard status for our counties
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
                    status = "✅" if letter_data.get('pass') else "❌"
                    print(f"  {letter}: {status} {metric}")
            return result
        else:
            print(f"❌ Failed to evaluate county {county_slug}: {r.status_code} - {r.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return None

def run_gold_standard_loop():
    """Run the gold standard loop evaluation - ONLY if no other session mid-flight"""
    print("\n=== Running Gold Standard Loop ===")
    try:
        client = httpx.Client(timeout=300)  # 5 minute timeout for the loop
        
        # First set statement timeout 
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
            headers=sb_headers(),
            json={"sql": "SET statement_timeout = 0;"}
        )
        
        # Run the gold standard loop
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/gold_standard_loop",
            headers=sb_headers(),
            json={}
        )
        
        if r.status_code == 200:
            result = r.json()
            print(f"✅ Gold Standard loop completed: {result}")
            return result
        else:
            print(f"❌ Failed to run gold standard loop: {r.status_code} - {r.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error running gold standard loop: {e}")
        return None

if __name__ == "__main__":
    print("=== SHARD-8 Database Connectivity Test ===")
    
    if not test_connection():
        sys.exit(1)
    
    print("\n=== Current Gold Standard Status ===")
    status = get_current_gold_standard_status()
    if status:
        for county, data in status.items():
            print(f"\n{county}:")
            print(f"  Loop run: {data.get('loop_run_id')}")
            print(f"  Pass count: {data.get('pass_count', 'N/A')}/10")
    
    print("\n=== Fresh County Evaluations ===")
    assigned_counties = ['hillsborough', 'alachua', 'nassau', 'desoto', 'monroe']
    county_evaluations = {}
    
    for county in assigned_counties:
        print(f"\n--- {county} ---")
        evaluation = evaluate_county_current(county)
        county_evaluations[county] = evaluation
    
    # Summary of current status
    print("\n=== SHARD-8 Current Status Summary ===")
    for county in assigned_counties:
        if county in county_evaluations and county_evaluations[county]:
            pass_count = sum(1 for letter in county_evaluations[county] if letter.get('pass'))
            print(f"{county}: {pass_count}/10 letters passing")
        else:
            print(f"{county}: No data available")