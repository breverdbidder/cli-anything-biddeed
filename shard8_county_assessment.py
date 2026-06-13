#!/usr/bin/env python3
"""
SHARD-8 County Assessment: hillsborough, alachua, nassau, desoto, monroe
Quick test to check database connectivity and current Gold Standard status for assigned counties
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
    # NOTE: Nassau removed - assigned to SHARD-12 per PARALLEL-FLEET RULES
    assigned_counties = ['hillsborough', 'alachua', 'desoto', 'monroe']
    
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
                    
                # Count passes
                passes = sum(1 for x in result if x.get('pass'))
                print(f"  TOTAL: {passes}/10 letters passing")
                
            return result
        else:
            print(f"❌ Failed to evaluate county {county_slug}: {r.status_code} - {r.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return None

def get_county_auction_counts():
    """Get auction counts for assigned counties to understand scale"""
    assigned_counties = ['hillsborough', 'alachua', 'desoto', 'monroe']
    
    try:
        client = httpx.Client(timeout=30)
        
        for county in assigned_counties:
            # Get auction count for this county
            r = client.get(
                f"{SUPABASE_URL}/rest/v1/multi_county_auctions?select=count()&county=eq.{county}",
                headers=sb_headers()
            )
            
            if r.status_code == 200:
                count = r.json()[0]['count']
                print(f"{county}: {count:,} auctions")
            else:
                print(f"{county}: ERROR {r.status_code}")
                
    except Exception as e:
        print(f"❌ Error getting auction counts: {e}")

if __name__ == "__main__":
    print("=== SHARD-8 Database Connectivity Test ===")
    
    if not test_connection():
        sys.exit(1)
    
    print("\n=== Assigned Counties Auction Counts ===")
    get_county_auction_counts()
    
    print("\n=== Current Gold Standard Status ===")
    status = get_current_gold_standard_status()
    if status:
        for county, data in status.items():
            print(f"\n{county}:")
            print(f"  Loop run: {data.get('loop_run_id')}")
            print(f"  Pass count: {data.get('pass_count', 'N/A')}/10")
    
    print("\n=== Fresh County Evaluations (LIVE) ===")
    assigned_counties = ['hillsborough', 'alachua', 'desoto', 'monroe']
    county_results = {}
    
    for county in assigned_counties:
        print(f"\n--- {county} ---")
        result = evaluate_county_current(county)
        if result:
            county_results[county] = result
    
    # Summary for prioritization
    print("\n=== PRIORITIZATION ANALYSIS ===")
    for county, result in county_results.items():
        passes = sum(1 for x in result if x.get('pass')) if result else 0
        print(f"{county}: {passes}/10 letters passing")
        
        if passes == 0:
            print(f"  🎯 PRIORITY TARGET: {county} needs A-letter work (basic auction ingestion)")