#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-8 database connectivity test
Counties: hillsborough, volusia, miami_dade, desoto, monroe
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

# Setup Supabase connection using environment variables or hardcoded values from CLAUDE.md
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

print(f"Using Supabase URL: {SUPABASE_URL}")
print(f"API Key present: {bool(SUPABASE_KEY)}")

# SHARD-8 assigned counties from briefing
SHARD8_COUNTIES = ['hillsborough', 'volusia', 'miami_dade', 'desoto', 'monroe']

def sb_headers():
    return {
        "apikey": SUPABASE_KEY, 
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def test_connection():
    """Test basic connection to Supabase"""
    if not SUPABASE_KEY:
        print("❌ No Supabase API key found in environment")
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
    """Run the pencil_dod_evaluate_county function for a single county - per briefing verification protocol"""
    try:
        client = httpx.Client(timeout=60)
        
        # Call the RPC function as specified in briefing
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
                    pass_status = letter_data.get('pass')
                    if pass_status:
                        pass_count += 1
                    status = "✅" if pass_status else "❌"
                    print(f"  {letter}: {status} metric={metric}")
                print(f"  TOTAL: {pass_count}/10 PASS")
            return result
        else:
            print(f"❌ Failed to evaluate county {county_slug}: {r.status_code} - {r.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return None

def check_table_exists(table_name):
    """Check if a key table exists"""
    try:
        client = httpx.Client(timeout=30)
        r = client.get(f"{SUPABASE_URL}/rest/v1/{table_name}?select=count&limit=1", headers=sb_headers())
        if r.status_code == 200:
            print(f"✅ Table {table_name} exists and accessible")
            return True
        else:
            print(f"❌ Table {table_name} check failed: {r.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error checking table {table_name}: {e}")
        return False

if __name__ == "__main__":
    print("=== SHARD-8 GOLD STANDARD SESSION START ===")
    print(f"Assigned counties: {', '.join(SHARD8_COUNTIES)}")
    
    print("\n=== Database Connectivity Test ===")
    if not test_connection():
        sys.exit(1)
    
    print("\n=== Key Tables Accessibility ===")
    key_tables = ['multi_county_auctions', 'gold_standard_county_status', 'pipeline']
    for table in key_tables:
        check_table_exists(table)
    
    print("\n=== SHARD-8 County Current Metrics (VERIFIED) ===")
    all_results = {}
    for county in SHARD8_COUNTIES:
        print(f"\n--- {county} ---")
        result = evaluate_county_current(county)
        if result:
            all_results[county] = result
    
    print("\n=== SHARD-8 SUMMARY ===")
    for county, result in all_results.items():
        if result:
            pass_count = sum(1 for item in result if item.get('pass'))
            print(f"{county}: {pass_count}/10 PASS")
    
    print("=== Ready to proceed with targeted fixes ===")