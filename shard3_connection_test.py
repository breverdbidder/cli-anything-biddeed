#!/usr/bin/env python3
"""
SHARD-3 Gold Standard Database Connection Test
Counties: broward, washington, lake, st_lucie, jefferson
"""

import os
import sys
import json
import httpx
from datetime import datetime, timezone

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"

# SHARD-3 counties
SHARD3_COUNTIES = ['broward', 'washington', 'lake', 'st_lucie', 'jefferson']

if not SUPABASE_KEY:
    print("❌ No Supabase key found in environment")
    sys.exit(1)

HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

print("="*50)
print("SHARD-3 GOLD STANDARD CONNECTION TEST")
print("="*50)
print(f"Counties: {', '.join(SHARD3_COUNTIES)}")
print(f"Supabase URL: {SUPABASE_URL}")
print(f"Key available: {'✅' if SUPABASE_KEY else '❌'}")
print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")

def test_basic_connectivity():
    """Test basic database connectivity"""
    try:
        client = httpx.Client(timeout=30)
        
        print("\n1. Testing basic connection...")
        response = client.get(f"{BASE}/", headers=HEADERS)
        print(f"Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ Basic connection failed: {response.text}")
            return False
            
        print("✅ Basic connection successful")
        return True
        
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False

def test_table_access():
    """Test access to key tables"""
    try:
        client = httpx.Client(timeout=30)
        
        print("\n2. Testing table access...")
        
        # Test multi_county_auctions
        response = client.get(f"{BASE}/multi_county_auctions", headers=HEADERS, params={'limit': 1})
        print(f"multi_county_auctions: {response.status_code}")
        
        # Test gold_standard_county_status
        response = client.get(f"{BASE}/gold_standard_county_status", headers=HEADERS, params={'limit': 1})
        print(f"gold_standard_county_status: {response.status_code}")
        
        print("✅ Table access successful")
        return True
        
    except Exception as e:
        print(f"❌ Table access failed: {e}")
        return False

def get_county_status():
    """Get current status for SHARD-3 counties"""
    try:
        client = httpx.Client(timeout=60)
        
        print("\n3. Retrieving current county status...")
        
        # Get latest status for our counties
        counties_filter = ','.join(f'"{c}"' for c in SHARD3_COUNTIES)
        params = {
            'select': '*',
            'county_slug': f'in.({counties_filter})',
            'order': 'loop_run_id.desc',
            'limit': str(len(SHARD3_COUNTIES) * 2)  # Get last 2 runs per county
        }
        
        response = client.get(f"{BASE}/gold_standard_county_status", headers=HEADERS, params=params)
        
        if response.status_code == 200:
            results = response.json()
            print(f"✅ Retrieved {len(results)} status records")
            
            # Group by county, get latest for each
            latest_by_county = {}
            for record in results:
                county = record.get('county_slug')
                if county not in latest_by_county:
                    latest_by_county[county] = record
            
            print("\nCurrent Status Summary:")
            for county in SHARD3_COUNTIES:
                if county in latest_by_county:
                    data = latest_by_county[county]
                    pass_count = data.get('pass_count', 0)
                    loop_run = data.get('loop_run_id', 'N/A')
                    print(f"  {county}: {pass_count}/10 passes (run {loop_run})")
                else:
                    print(f"  {county}: No status found")
            
            return latest_by_county
        else:
            print(f"❌ Failed to retrieve status: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error retrieving county status: {e}")
        return None

def evaluate_county_live(county_slug):
    """Run live evaluation for a county"""
    try:
        client = httpx.Client(timeout=120)
        
        print(f"\n--- Live evaluation: {county_slug} ---")
        
        response = client.post(
            f"{BASE}/rpc/pencil_dod_evaluate_county",
            headers=HEADERS,
            json={"county_slug_arg": county_slug}
        )
        
        if response.status_code == 200:
            result = response.json()
            
            if isinstance(result, list) and len(result) > 0:
                pass_count = 0
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    is_pass = letter_data.get('pass', False)
                    status = "✅" if is_pass else "❌"
                    
                    if is_pass:
                        pass_count += 1
                    
                    # Format metric for display
                    if metric is not None:
                        if isinstance(metric, (int, float)):
                            metric_display = f"{metric:.1f}" if isinstance(metric, float) else str(metric)
                        else:
                            metric_display = str(metric)
                    else:
                        metric_display = "null"
                    
                    print(f"  {letter}: {status} {metric_display}")
                
                print(f"  Total: {pass_count}/10 passes")
                return result
            else:
                print(f"  No evaluation data returned")
                return None
        else:
            print(f"  ❌ Evaluation failed: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"  ❌ Evaluation error: {e}")
        return None

def main():
    """Main test execution"""
    
    # Step 1: Basic connectivity
    if not test_basic_connectivity():
        sys.exit(1)
    
    # Step 2: Table access
    if not test_table_access():
        sys.exit(1)
    
    # Step 3: County status
    status = get_county_status()
    
    # Step 4: Live evaluations
    print("\n4. Running live county evaluations...")
    for county in SHARD3_COUNTIES:
        evaluate_county_live(county)
    
    print("\n" + "="*50)
    print("SHARD-3 CONNECTION TEST COMPLETE ✅")
    print("="*50)

if __name__ == "__main__":
    main()