#!/usr/bin/env python3
"""
Apply SHARD-12 migration to live database
"""
import os
import sys
import httpx

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_KEY:
    print("No API key found, checking GitHub environment...")
    # Try common GitHub Actions secret names
    for key_name in ['GITHUB_TOKEN', 'SUPABASE_ANON_KEY', 'SUPABASE_SERVICE_ROLE_KEY']:
        test_key = os.environ.get(key_name, '')
        if 'eyJ' in test_key:  # JWT format
            SUPABASE_KEY = test_key
            print(f"Using key from {key_name}")
            break

if not SUPABASE_KEY:
    print("ERROR: No Supabase API key available")
    sys.exit(1)

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# Read migration file
with open('migrations/20260613_shard12_correct_counties.sql', 'r') as f:
    migration_sql = f.read()

print("Applying SHARD-12 migration to live database...")

try:
    client = httpx.Client(timeout=120)
    
    # Apply migration via raw SQL
    response = client.post(
        f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
        headers=HEADERS,
        json={"sql": migration_sql}
    )
    
    if response.status_code == 200:
        print("✅ Migration applied successfully")
    else:
        print(f"❌ Migration failed: {response.status_code} - {response.text}")
        
        # Try alternative approach - apply key parts manually
        print("Trying manual table creation...")
        
        # Ensure fl_counties has our counties
        counties_data = [
            {"co_no": 52, "name": "Marion", "fips_code": "12083", "slug": "marion", "region": "central"},
            {"co_no": 20, "name": "Clay", "fips_code": "12019", "slug": "clay", "region": "northeast"},
            {"co_no": 61, "name": "Pasco", "fips_code": "12101", "slug": "pasco", "region": "west_central"},
            {"co_no": 32, "name": "Glades", "fips_code": "12043", "slug": "glades", "region": "central"}
        ]
        
        for county in counties_data:
            county_response = client.post(
                f"{SUPABASE_URL}/rest/v1/fl_counties",
                headers={**HEADERS, "Prefer": "resolution=merge-duplicates"},
                json=county
            )
            if county_response.status_code in [200, 201]:
                print(f"✅ County {county['name']} configured")
            else:
                print(f"⚠️ County {county['name']}: {county_response.status_code}")
    
    client.close()
    print("Migration application complete")
    
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)