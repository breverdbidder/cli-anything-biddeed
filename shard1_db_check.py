#!/usr/bin/env python3
"""
SHARD-1 Database connectivity and status check for assigned counties:
charlotte, palm_beach, clay, pasco, hardee

Verifies current Gold Standard metrics for autonomous session planning
"""
import os
import sys
import httpx
import json
from typing import Optional, List, Dict

# Assigned counties for SHARD-1
ASSIGNED_COUNTIES = ['charlotte', 'palm_beach', 'clay', 'pasco', 'hardee']

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def test_connection() -> bool:
    """Test basic Supabase connection"""
    try:
        client = httpx.Client(timeout=30)
        r = client.get(f"{SUPABASE_URL}/rest/v1/fl_counties?select=count&limit=1", headers=sb_headers())
        if r.status_code == 200:
            print("✅ Database connection successful")
            return True
        else:
            print(f"❌ Database connection failed: {r.status_code} - {r.text}")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def evaluate_county_current(county_slug: str) -> Optional[Dict]:
    """Run pencil_dod_evaluate_county for a single county"""
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
            print(f"\n✅ County evaluation for {county_slug}:")
            if isinstance(result, list) and len(result) > 0:
                pass_count = 0
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    status = "✅" if letter_data.get('pass') else "❌"
                    if letter_data.get('pass'):
                        pass_count += 1
                    print(f"  {letter}: {status} {metric}")
                print(f"  SCORE: {pass_count}/10")
            return result
        else:
            print(f"❌ Failed to evaluate county {county_slug}: {r.status_code} - {r.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return None

def get_multi_county_auctions_count(county: str) -> Optional[int]:
    """Get count of auctions for a county"""
    try:
        client = httpx.Client(timeout=30)
        # Use proper filter syntax for Supabase
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions?select=count()&county=eq.{county}",
            headers=sb_headers()
        )
        
        if r.status_code == 200:
            result = r.json()
            if result and len(result) > 0:
                count = result[0].get('count', 0)
                print(f"  Auctions in multi_county_auctions: {count}")
                return count
        return None
    except Exception as e:
        print(f"  Error getting auction count: {e}")
        return None

def main():
    print("=== SHARD-1 Gold Standard Status Check ===")
    print(f"Assigned Counties: {', '.join(ASSIGNED_COUNTIES)}")
    print(f"Supabase URL: {SUPABASE_URL}")
    print(f"API Key present: {bool(SUPABASE_KEY)}")
    
    if not SUPABASE_KEY:
        print("❌ No Supabase API key found in environment")
        sys.exit(1)
    
    if not test_connection():
        sys.exit(1)
    
    print("\n=== Current County Status ===")
    county_results = {}
    
    for county in ASSIGNED_COUNTIES:
        print(f"\n--- {county.upper()} ---")
        get_multi_county_auctions_count(county)
        result = evaluate_county_current(county)
        county_results[county] = result
    
    print("\n=== Summary ===")
    for county, result in county_results.items():
        if result:
            pass_count = sum(1 for item in result if item.get('pass'))
            print(f"{county}: {pass_count}/10 letters passing")
        else:
            print(f"{county}: Evaluation failed")

if __name__ == "__main__":
    main()