#!/usr/bin/env python3
"""
SHARD 9 County Status Check: leon, washington, marion, dixie, taylor
Quick assessment of current metrics and gaps for assigned counties
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

# Supabase connection
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
            print(f"✅ County evaluation for {county_slug}:")
            if isinstance(result, list) and len(result) > 0:
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    status = "✅" if letter_data.get('pass') else "❌"
                    print(f"  {letter}: {status} {metric}")
                return result
            else:
                print(f"  No evaluation data returned (county may need setup)")
                return None
        else:
            print(f"❌ Failed to evaluate county {county_slug}: {r.status_code} - {r.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return None

def check_county_data(county_slug, co_no):
    """Check what data exists for a county"""
    client = httpx.Client(timeout=30)
    
    print(f"\n=== Data check for {county_slug} (CO_NO={co_no}) ===")
    
    # Check fl_counties
    try:
        r = client.get(f"{SUPABASE_URL}/rest/v1/fl_counties?co_no=eq.{co_no}&select=*", headers=sb_headers())
        if r.status_code == 200 and r.json():
            county_data = r.json()[0]
            print(f"  FL Counties: ✅ {county_data.get('name')} - {county_data.get('total_parcels', 0):,} parcels")
        else:
            print(f"  FL Counties: ❌ No data for CO_NO={co_no}")
    except Exception as e:
        print(f"  FL Counties: ❌ Error: {e}")
    
    # Check multi_county_auctions
    try:
        r = client.get(f"{SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.{county_slug}&select=count", headers=sb_headers())
        if r.status_code == 200:
            auction_count = len(r.json()) if r.json() else 0
            print(f"  Auctions: {auction_count:,} records")
        else:
            print(f"  Auctions: ❌ Error checking auctions")
    except Exception as e:
        print(f"  Auctions: ❌ Error: {e}")
    
    # Check zoning_assignments
    try:
        r = client.get(f"{SUPABASE_URL}/rest/v1/zoning_assignments?co_no=eq.{co_no}&select=count", headers=sb_headers())
        if r.status_code == 200:
            zoning_count = len(r.json()) if r.json() else 0
            print(f"  Zoning: {zoning_count:,} assignments")
        else:
            print(f"  Zoning: ❌ Error checking zoning")
    except Exception as e:
        print(f"  Zoning: ❌ Error: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("SHARD 9 COUNTY STATUS CHECK")
    print("Assigned: leon, washington, marion, dixie, taylor")
    print("=" * 60)
    
    if not test_connection():
        sys.exit(1)
    
    # SHARD 9 assigned counties with CO_NO from manifest
    assigned_counties = [
        ('leon', 47),
        ('washington', 77), 
        ('marion', 52),
        ('dixie', 25),
        ('taylor', 72)
    ]
    
    print("\n=== DATA AVAILABILITY CHECK ===")
    for county_slug, co_no in assigned_counties:
        check_county_data(county_slug, co_no)
    
    print("\n=== CURRENT GOLD STANDARD METRICS ===")
    for county_slug, co_no in assigned_counties:
        print(f"\n--- {county_slug} ---")
        evaluate_county_current(county_slug)
    
    print("\n=== SUMMARY ===")
    print("Next steps:")
    print("1. Counties with 0/10 need baseline data ingestion")
    print("2. Counties with low scores need targeted letter fixes")
    print("3. All counties need slug assignment in multi_county_auctions")