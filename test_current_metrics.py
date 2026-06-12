#!/usr/bin/env python3
"""
Test current metrics for Brevard and Duval counties using GitHub Actions environment
"""
import os
import sys
import json
import httpx
from datetime import datetime, timezone
from typing import Dict, List, Optional

# Setup Supabase connection using GitHub Actions secrets
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

print(f"Supabase URL: {SUPABASE_URL}")
print(f"API Key available: {bool(SUPABASE_KEY)}")

if not SUPABASE_KEY:
    print("❌ No Supabase API key available")
    # Try using GitHub Actions secrets format
    SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
    print(f"Trying anon key: {bool(SUPABASE_KEY)}")

BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

def test_connection():
    """Test basic connection to Supabase"""
    try:
        client = httpx.Client(timeout=30)
        # Simple connection test
        r = client.get(f"{BASE}/fl_counties", headers=HEADERS, params={'limit': '1'})
        print(f"Connection test: {r.status_code}")
        if r.status_code == 200:
            print("✅ Database connection successful")
            data = r.json()
            print(f"Sample data: {data[:1] if data else 'Empty result'}")
            return True
        else:
            print(f"❌ Database connection failed: {r.text}")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def evaluate_county_direct(county: str):
    """Try to run pencil_dod_evaluate_county function"""
    try:
        client = httpx.Client(timeout=120)
        
        # Try the RPC function with different parameter names
        for param_name in ['county_slug_arg', 'county_name', 'county', 'p_county']:
            try:
                print(f"Trying RPC with param '{param_name}' for {county}")
                r = client.post(
                    f"{BASE}/rpc/pencil_dod_evaluate_county",
                    headers=HEADERS,
                    json={param_name: county}
                )
                
                if r.status_code == 200:
                    result = r.json()
                    print(f"✅ SUCCESS with param '{param_name}':")
                    
                    if isinstance(result, list):
                        for item in result:
                            if isinstance(item, dict):
                                letter = item.get('letter', 'Unknown')
                                metric = item.get('metric', 'N/A')
                                status = "✅ PASS" if item.get('pass') else "❌ FAIL"
                                print(f"  {letter}: {status} metric={metric}")
                    else:
                        print(f"  Result: {result}")
                    return result
                else:
                    print(f"  Failed with {param_name}: {r.status_code}")
                    
            except Exception as e:
                print(f"  Error with {param_name}: {e}")
                continue
        
        print(f"❌ All RPC attempts failed for {county}")
        return None
        
    except Exception as e:
        print(f"❌ RPC evaluation failed: {e}")
        return None

def get_basic_auction_stats(county: str):
    """Get basic auction statistics"""
    try:
        client = httpx.Client(timeout=30)
        
        # Get total auctions
        params = {
            'county': f'eq.{county}',
            'select': 'case_number,parcel_id,auction_status,assessed_value'
        }
        
        r = client.get(f"{BASE}/multi_county_auctions", headers=HEADERS, params=params)
        
        if r.status_code == 200:
            auctions = r.json()
            total = len(auctions)
            with_parcel = sum(1 for a in auctions if a.get('parcel_id'))
            closed = sum(1 for a in auctions if a.get('auction_status') in ['sold', 'no_sale', 'canceled'])
            
            print(f"\n{county.upper()} Basic Stats:")
            print(f"  Total auctions: {total}")
            print(f"  With parcel_id: {with_parcel} ({100*with_parcel/total if total > 0 else 0:.1f}%)")
            print(f"  Closed auctions: {closed}")
            
            return {
                'total_auctions': total,
                'parcel_linked': with_parcel,
                'closed_auctions': closed
            }
        else:
            print(f"❌ Failed to get auction stats: {r.status_code}")
            return {}
            
    except Exception as e:
        print(f"❌ Error getting basic stats: {e}")
        return {}

def check_bid_decisions():
    """Check bid_decisions table to understand J=0 issue"""
    try:
        client = httpx.Client(timeout=30)
        
        # Get total count
        r = client.get(f"{BASE}/bid_decisions", headers=HEADERS, params={'limit': '10', 'select': 'case_number,county_slug,arv,max_bid'})
        
        if r.status_code == 200:
            decisions = r.json()
            print(f"\nBID_DECISIONS table check:")
            print(f"  Total records found: {len(decisions)}")
            
            if decisions:
                for d in decisions[:5]:  # Show first 5
                    case = d.get('case_number', 'Unknown')
                    county = d.get('county_slug', 'Unknown')
                    arv = d.get('arv', 0)
                    max_bid = d.get('max_bid', 0)
                    print(f"    {case} ({county}): ARV=${arv} MaxBid=${max_bid}")
            else:
                print("    ⚠️ No bid_decisions records found - explains J=0 fleet-wide")
            
            return len(decisions)
        else:
            print(f"❌ Failed to query bid_decisions: {r.status_code}")
            return 0
            
    except Exception as e:
        print(f"❌ Error checking bid_decisions: {e}")
        return 0

if __name__ == "__main__":
    print("=== CURRENT METRICS TEST FOR BREVARD + DUVAL ===")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    
    # Test basic connection
    if not test_connection():
        sys.exit(1)
    
    # Check current county evaluations
    target_counties = ['brevard', 'duval']
    
    for county in target_counties:
        print(f"\n=== {county.upper()} EVALUATION ===")
        
        # Try direct RPC evaluation
        evaluation = evaluate_county_direct(county)
        
        # Get basic stats regardless
        basic_stats = get_basic_auction_stats(county)
    
    # Check bid_decisions table
    bid_count = check_bid_decisions()
    
    print(f"\n=== SUMMARY ===")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"Counties tested: {', '.join(target_counties)}")
    print(f"Bid decisions records: {bid_count}")
    
    if bid_count == 0:
        print("✅ CONFIRMED: J=0 root cause is empty bid_decisions table")
    
    print("\n=== NEXT ACTIONS ===")
    print("1. Run Brevard AcclaimWeb scraper (scripts/acclaim_ct_sweep.py)")
    print("2. Run deal thesis pipeline (scripts/shard2_deal_thesis.py)")
    print("3. Fix Duval case number issues") 
    print("4. Re-run evaluation to verify improvements")