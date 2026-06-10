#!/usr/bin/env python3
"""
SHARD-1 Status Verification Script
Uses httpx to query Supabase and verify current county status

SHIP GATE compliance: Provides SQL verification evidence for gold standard metrics
"""

import os
import sys
import json
from datetime import datetime, timezone

try:
    import httpx
except ImportError:
    print("ERROR: httpx not available. Run: pip install httpx")
    sys.exit(1)

# Database configuration (from CLAUDE.md) 
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_ROLE", "")

SHARD1_COUNTIES = ['st_johns', 'baker', 'hendry', 'nassau', 'bradford', 'glades', 'levy']

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def query_auction_counts():
    """Query auction counts for SHARD-1 counties from multi_county_auctions"""
    print("=== AUCTION COUNTS BY COUNTY ===")
    
    client = httpx.Client(timeout=30)
    results = {}
    
    for county in SHARD1_COUNTIES:
        try:
            r = client.get(
                f"{SUPABASE_URL}/rest/v1/multi_county_auctions?select=count&county_name=eq.{county}",
                headers=sb_headers()
            )
            
            if r.status_code == 200:
                data = r.json()
                count = data[0].get('count', 0) if data else 0
                results[county] = count
                print(f"{county}: {count:,} auctions")
            else:
                print(f"{county}: ERROR {r.status_code} - {r.text[:100]}")
                results[county] = None
                
        except Exception as e:
            print(f"{county}: EXCEPTION - {e}")
            results[county] = None
    
    client.close()
    return results

def run_county_evaluation(county):
    """Run pencil_dod_evaluate_county RPC function"""
    client = httpx.Client(timeout=60)
    
    try:
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=sb_headers(),
            json={"county_slug_arg": county}
        )
        
        if r.status_code == 200:
            result = r.json()
            return result
        else:
            print(f"RPC Error for {county}: {r.status_code} - {r.text[:200]}")
            return None
            
    except Exception as e:
        print(f"Exception evaluating {county}: {e}")
        return None
    finally:
        client.close()

def main():
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    print(f"=== SHARD-1 STATUS VERIFICATION ===")
    print(f"Timestamp: {timestamp}")
    print(f"Database: {SUPABASE_URL}")
    print(f"API Key: {'✅ Present' if SUPABASE_KEY else '❌ Missing'}")
    
    if not SUPABASE_KEY:
        print("\nERROR: No Supabase API key found")
        print("Set SUPABASE_KEY or SUPABASE_SERVICE_ROLE environment variable")
        sys.exit(1)
    
    # Test connection
    try:
        client = httpx.Client(timeout=10)
        r = client.get(f"{SUPABASE_URL}/rest/v1/fl_counties?select=count&limit=1", headers=sb_headers())
        if r.status_code == 200:
            print("✅ Database connection successful")
        else:
            print(f"❌ Database connection failed: {r.status_code}")
            sys.exit(1)
        client.close()
    except Exception as e:
        print(f"❌ Connection error: {e}")
        sys.exit(1)
    
    # Query auction counts
    auction_counts = query_auction_counts()
    
    print("\n=== COUNTY EVALUATIONS ===")
    for county in SHARD1_COUNTIES:
        print(f"\n--- {county.upper()} ---")
        print(f"Auction count: {auction_counts.get(county, 'N/A')}")
        
        evaluation = run_county_evaluation(county)
        if evaluation:
            pass_count = sum(1 for item in evaluation if item.get('pass', False))
            print(f"Gold Standard: {pass_count}/10 letters passing")
            
            for item in evaluation:
                letter = item.get('letter', '?')
                metric = item.get('metric')
                passed = "✅" if item.get('pass', False) else "❌"
                explanation = item.get('explanation', '')
                print(f"  {letter}: {passed} {metric} - {explanation}")
        else:
            print("  Evaluation failed")
    
    print(f"\n=== SQL VERIFICATION ===")
    print(f"-- Timestamp: {timestamp}")
    print("-- SHARD-1 Auction Counts Query:")
    print("SELECT county_name, COUNT(*) as auction_count")
    print("FROM public.multi_county_auctions") 
    print("WHERE county_name IN ('st_johns', 'baker', 'hendry', 'nassau', 'bradford', 'glades', 'levy')")
    print("GROUP BY county_name ORDER BY county_name;")
    print("")
    print("-- Expected results:")
    for county, count in auction_counts.items():
        if count is not None:
            print(f"-- {county}: {count:,} rows")
    
    print(f"\n=== VERIFICATION COMPLETE ===")

if __name__ == "__main__":
    main()