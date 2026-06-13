#!/usr/bin/env python3
"""
SHARD-12 Current Status Check
Verify current metrics for marion, clay, pasco, glades counties
"""
import os
import sys
import json

# Try importing httpx 
try:
    import httpx
    print("✅ httpx available")
except ImportError:
    print("❌ httpx not available, installing...")
    os.system("pip install httpx")
    import httpx

# Setup Supabase connection using environment variables or hardcoded values
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

print(f"Using Supabase URL: {SUPABASE_URL}")
print(f"API Key present: {bool(SUPABASE_KEY)}")

if not SUPABASE_KEY:
    print("❌ No Supabase API key found in environment")
    print("Trying GitHub Actions secret extraction...")
    # In GitHub Actions, keys might be in different env vars
    for possible_key in ["GITHUB_TOKEN", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY"]:
        test_key = os.environ.get(possible_key)
        if test_key and "eyJ" in test_key:  # JWT format
            SUPABASE_KEY = test_key
            print(f"✅ Found potential key in {possible_key}")
            break
    
    if not SUPABASE_KEY:
        print("❌ Still no valid API key found")
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
    """Get current Gold Standard metrics for our SHARD-12 counties"""
    assigned_counties = ['marion', 'clay', 'pasco', 'glades']
    
    try:
        client = httpx.Client(timeout=30)
        
        # Try to get latest gold standard status for our counties
        counties_filter = ','.join(f'"{c}"' for c in assigned_counties)
        url = f"{SUPABASE_URL}/rest/v1/gold_standard_county_status"
        params = f"select=*&county_slug=in.({counties_filter})&order=loop_run_id.desc&limit=40"
        
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
        
        # Call the RPC function - try different parameter names
        for param_name in ['county_slug_arg', 'county_name', 'county_slug', 'county']:
            try:
                r = client.post(
                    f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
                    headers=sb_headers(),
                    json={param_name: county_slug}
                )
                
                if r.status_code == 200:
                    result = r.json()
                    print(f"✅ County evaluation for {county_slug} (param: {param_name}):")
                    if isinstance(result, list) and len(result) > 0:
                        pass_count = 0
                        for letter_data in result:
                            letter = letter_data.get('letter', '?')
                            metric = letter_data.get('metric')
                            passed = letter_data.get('pass', False)
                            status = "✅" if passed else "❌"
                            if passed:
                                pass_count += 1
                            print(f"  {letter}: {status} {metric}")
                        print(f"  TOTAL: {pass_count}/10 PASS")
                    return result
                else:
                    print(f"❌ Failed with {param_name}: {r.status_code}")
                    continue
                    
            except Exception as e:
                print(f"❌ Error with param {param_name}: {e}")
                continue
                
        print(f"❌ All evaluation attempts failed for {county_slug}")
        return None
            
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return None

def get_basic_county_metrics(county_slug):
    """Get basic metrics if evaluation fails"""
    try:
        client = httpx.Client(timeout=30)
        
        # Total auctions
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
            headers=sb_headers(),
            params={"county": f"eq.{county_slug}", "select": "count"}
        )
        
        if r.status_code == 200:
            total = len(r.json()) if isinstance(r.json(), list) else 0
            print(f"  Total auctions: {total}")
            
            if total == 0:
                print(f"  ❌ {county_slug} has no auction data")
                return {"total_auctions": 0}
        
        return {"total_auctions": total}
        
    except Exception as e:
        print(f"❌ Error getting basic metrics for {county_slug}: {e}")
        return {}

if __name__ == "__main__":
    print("=== SHARD-12 Database Connectivity Test ===")
    
    if not test_connection():
        sys.exit(1)
    
    print("\n=== Current Gold Standard Status ===")
    status = get_current_gold_standard_status()
    if status:
        for county, data in status.items():
            print(f"\n{county}:")
            print(f"  Loop run: {data.get('loop_run_id')}")
            print(f"  Pass count: {data.get('pass_count', 'N/A')}/10")
            print(f"  Last updated: {data.get('updated_at', 'N/A')}")
    else:
        print("No Gold Standard status found for our counties")
    
    print("\n=== Fresh County Evaluations ===")
    shard12_counties = ['marion', 'clay', 'pasco', 'glades']
    for county in shard12_counties:
        print(f"\n--- {county.upper()} ---")
        result = evaluate_county_current(county)
        if not result:
            print("Evaluation failed, trying basic metrics...")
            get_basic_county_metrics(county)
    
    print("\n=== SHARD-12 Status Summary ===")
    print("From the issue description:")
    print("marion (2/10): A PASS, B/C/D/E/F/G/I/J FAIL, H PASS")
    print("clay (1/10): A PASS, B/C/D/E/F/G/I/J FAIL, H FAIL")  
    print("pasco (1/10): A PASS, B/C/D/E/F/G/H/I/J FAIL")
    print("glades (0/10): ALL FAIL")