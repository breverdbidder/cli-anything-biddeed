#!/usr/bin/env python3
"""
SHARD-7 Gold Standard County Check
Check current metrics for: highlands, baker, miami_dade, columbia, madison
"""
import os
import sys
import httpx
from datetime import datetime

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# My assigned counties
SHARD7_COUNTIES = ['highlands', 'baker', 'miami_dade', 'columbia', 'madison']

def check_supabase_connection():
    """Verify we can connect to Supabase"""
    try:
        client = httpx.Client(timeout=30)
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        response = client.get(f"{SUPABASE_URL}/rest/v1/fl_counties?select=count&limit=1", headers=headers)
        response.raise_for_status()
        print("✅ Supabase connection verified")
        return True, client, headers
    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")
        return False, None, None

def call_rpc_function(client, headers, function_name, params=None):
    """Call a Supabase RPC function"""
    try:
        response = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/{function_name}",
            headers=headers,
            json=params or {}
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ RPC call failed for {function_name}: {e}")
        return None

def check_county_status(client, headers, county_slug):
    """Check gold standard status for a county"""
    print(f"\n{'='*50}")
    print(f"CHECKING: {county_slug.upper()}")
    print(f"{'='*50}")
    
    # Call pencil_dod_evaluate_county function
    result = call_rpc_function(client, headers, 'pencil_dod_evaluate_county', county_slug)
    
    if result:
        print("Current Gold Standard Status:")
        for row in result:
            letter = row.get('letter', 'N/A')
            pass_status = "✅ PASS" if row.get('pass') else "❌ FAIL"
            metric = row.get('metric', 0)
            detail = row.get('detail', '')
            threshold = row.get('threshold', '')
            
            print(f"  {letter}: {pass_status} | {metric} | {detail} | {threshold}")
    else:
        print("❌ Could not get status for this county")
        
    # Check if there are any auctions for this county
    try:
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.{county_slug}&select=count",
            headers=headers
        )
        auction_count = len(response.json()) if response.status_code == 200 else 0
        print(f"\nAuction count in multi_county_auctions: {auction_count}")
    except Exception as e:
        print(f"Could not check auction count: {e}")

def main():
    print("SHARD-7 GOLD STANDARD CHECK")
    print(f"Target Counties: {', '.join(SHARD7_COUNTIES)}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    if not SUPABASE_KEY:
        print("❌ SUPABASE_KEY environment variable not set")
        sys.exit(1)
    
    connected, client, headers = check_supabase_connection()
    if not connected:
        sys.exit(1)
    
    # Check each county
    for county in SHARD7_COUNTIES:
        check_county_status(client, headers, county)
    
    print(f"\n{'='*50}")
    print("CHECK COMPLETE")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()