#!/usr/bin/env python3
"""
SHARD-9 Gold Standard Status Verification: leon, clay, okaloosa, dixie, taylor
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
    """Get current Gold Standard metrics for SHARD-9 counties"""
    assigned_counties = ['leon', 'clay', 'okaloosa', 'dixie', 'taylor']
    
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

def check_county_ingestion_status():
    """Check basic data availability for our counties"""
    assigned_counties = ['leon', 'clay', 'okaloosa', 'dixie', 'taylor']
    
    print("\n=== County Data Ingestion Status ===")
    
    for county in assigned_counties:
        try:
            client = httpx.Client(timeout=30)
            
            # Check multi_county_auctions
            r = client.get(
                f"{SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.{county}&select=count&head=true",
                headers=sb_headers()
            )
            auction_count = int(r.headers.get('Content-Range', '0-0/0').split('/')[-1]) if r.status_code == 206 else 0
            
            # Check zoning_assignments (using co_no lookup)
            county_co_mapping = {
                'leon': 38,
                'clay': 15, 
                'okaloosa': 57,
                'dixie': 23,
                'taylor': 79
            }
            
            co_no = county_co_mapping.get(county)
            zoning_count = 0
            if co_no:
                r = client.get(
                    f"{SUPABASE_URL}/rest/v1/zoning_assignments?co_no=eq.{co_no}&select=count&head=true",
                    headers=sb_headers()
                )
                zoning_count = int(r.headers.get('Content-Range', '0-0/0').split('/')[-1]) if r.status_code == 206 else 0
            
            print(f"{county:12s} | Auctions: {auction_count:>6,} | Zoning: {zoning_count:>8,} | CO_NO: {co_no or 'N/A'}")
            
        except Exception as e:
            print(f"{county:12s} | Error: {e}")

if __name__ == "__main__":
    print("=== SHARD-9 Database Status Check ===")
    print("Counties: leon, clay, okaloosa, dixie, taylor")
    
    if not test_connection():
        sys.exit(1)
    
    check_county_ingestion_status()
    
    print("\n=== Current Gold Standard Status ===")
    status = get_current_gold_standard_status()
    if status:
        for county, data in status.items():
            print(f"\n{county}:")
            print(f"  Loop run: {data.get('loop_run_id')}")
            print(f"  Pass count: {data.get('pass_count', 'N/A')}/10")
    
    print("\n=== Fresh County Evaluations ===")
    assigned_counties = ['leon', 'clay', 'okaloosa', 'dixie', 'taylor']
    for county in assigned_counties:
        print(f"\n--- {county} ---")
        evaluate_county_current(county)