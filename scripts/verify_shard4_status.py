#!/usr/bin/env python3
"""
Quick verification of shard-4 county status
Tests database connectivity and evaluates current gold standard metrics
"""
import os
import httpx

SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

def verify_connection():
    """Test basic Supabase connectivity"""
    if not SUPABASE_KEY:
        print("ERROR: SUPABASE_KEY not set")
        return False
        
    try:
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        client = httpx.Client(timeout=30)
        response = client.get(f"{SUPABASE_URL}/rest/v1/fl_counties?select=count", headers=headers)
        
        if response.status_code == 200:
            print("✅ Supabase connection verified")
            return True
        else:
            print(f"❌ Connection failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def check_shard4_counties():
    """Check basic auction data for shard-4 counties"""
    counties = ['citrus', 'st_johns', 'hendry', 'walton', 'lafayette']
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    client = httpx.Client(timeout=30)
    
    print("\n=== SHARD-4 COUNTY STATUS ===")
    
    for county in counties:
        try:
            # Check auction count
            response = client.get(
                f"{SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.{county}&select=count",
                headers=headers
            )
            
            auction_count = 0
            if response.status_code == 200:
                data = response.json()
                auction_count = len(data) if data else 0
            
            # Check parcel linkage
            response2 = client.get(
                f"{SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.{county}&parcel_id=not.is.null&select=count",
                headers=headers
            )
            
            linked_count = 0
            if response2.status_code == 200:
                data2 = response2.json()
                linked_count = len(data2) if data2 else 0
                
            linkage_pct = (linked_count / auction_count * 100) if auction_count > 0 else 0
            
            print(f"{county:12s} | Auctions: {auction_count:5d} | Linked: {linked_count:5d} | Linkage: {linkage_pct:5.1f}%")
            
        except Exception as e:
            print(f"{county:12s} | ERROR: {e}")

if __name__ == "__main__":
    print("SHARD-4 Status Verification")
    print("=" * 40)
    
    if verify_connection():
        check_shard4_counties()
    else:
        print("Cannot proceed without database connection")