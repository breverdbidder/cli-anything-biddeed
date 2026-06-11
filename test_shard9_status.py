#!/usr/bin/env python3
"""
Test database connectivity and check current Gold Standard status for SHARD-9 counties
Assigned counties: leon, washington, marion, dixie, taylor
"""
import os
import sys
import json
from typing import Dict, List, Optional

# Try importing httpx 
try:
    import httpx
    print("✅ httpx available")
except ImportError:
    print("❌ httpx not available")
    sys.exit(1)

# Setup Supabase connection using environment variables or hardcoded values
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

print(f"Using Supabase URL: {SUPABASE_URL}")
print(f"API Key present: {bool(SUPABASE_KEY)}")

# SHARD-9 assigned counties
ASSIGNED_COUNTIES = ['leon', 'washington', 'marion', 'dixie', 'taylor']

if not SUPABASE_KEY:
    print("❌ No Supabase API key found in environment")
    # For CI/CD environments, let's try to continue without key for now
    print("⚠️ Attempting to continue without API key for analysis...")

def sb_headers():
    return {
        "apikey": SUPABASE_KEY, 
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def test_connection() -> bool:
    """Test basic connection to Supabase"""
    if not SUPABASE_KEY:
        print("⚠️ Skipping connection test - no API key")
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

def get_current_gold_standard_status() -> Optional[Dict]:
    """Get current Gold Standard metrics for SHARD-9 counties"""
    if not SUPABASE_KEY:
        print("⚠️ Skipping status retrieval - no API key")
        return None
        
    try:
        client = httpx.Client(timeout=30)
        
        # Try to get latest gold standard status for our counties
        counties_filter = ','.join(f'"{c}"' for c in ASSIGNED_COUNTIES)
        url = f"{SUPABASE_URL}/rest/v1/gold_standard_county_status"
        params = f"select=*&county_slug=in.({counties_filter})&order=loop_run_id.desc&limit=50"
        
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

def evaluate_county_current(county_slug: str) -> Optional[List]:
    """Run the pencil_dod_evaluate_county function for a single county"""
    if not SUPABASE_KEY:
        print(f"⚠️ Skipping evaluation for {county_slug} - no API key")
        return None
        
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
                    details = letter_data.get('details', '')
                    print(f"  {letter}: {status} {metric} {details}")
            return result
        else:
            print(f"❌ Failed to evaluate county {county_slug}: {r.status_code} - {r.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return None

def analyze_priority_targets() -> Dict[str, int]:
    """
    Analyze SHARD-9 counties and return priority scores
    Based on the issue description:
    - leon (2/10): has some progress 
    - washington (2/10): has some progress
    - marion (1/10): minimal progress
    - dixie (0/10): no progress
    - taylor (0/10): no progress
    """
    
    priorities = {
        'leon': 8,      # Has 2/10, good potential for quick wins
        'washington': 8, # Has 2/10, good potential  
        'marion': 6,    # Has 1/10, needs more work
        'dixie': 4,     # 0/10, start from scratch
        'taylor': 4     # 0/10, start from scratch
    }
    
    return priorities

if __name__ == "__main__":
    print("=== SHARD-9 Database Connectivity Test ===")
    print(f"Assigned counties: {', '.join(ASSIGNED_COUNTIES)}")
    
    connection_ok = test_connection()
    
    print("\n=== Current Gold Standard Status ===")
    status = get_current_gold_standard_status()
    if status:
        for county in ASSIGNED_COUNTIES:
            if county in status:
                data = status[county]
                print(f"\n{county}:")
                print(f"  Loop run: {data.get('loop_run_id')}")
                print(f"  Pass count: {data.get('pass_count', 'N/A')}/10")
                print(f"  Last updated: {data.get('updated_at', 'N/A')}")
            else:
                print(f"\n{county}: ❌ No status data found")
    
    print("\n=== Fresh County Evaluations ===")
    for county in ASSIGNED_COUNTIES:
        print(f"\n--- {county} ---")
        evaluate_county_current(county)
    
    print("\n=== Priority Analysis ===")
    priorities = analyze_priority_targets()
    sorted_counties = sorted(priorities.items(), key=lambda x: x[1], reverse=True)
    
    print("Recommended work order (highest priority first):")
    for county, priority in sorted_counties:
        print(f"  {county}: priority {priority}/10")
    
    print("\n=== Recommendations ===")
    print("Based on the issue description and current status:")
    print("1. Focus on leon and washington first (both 2/10, highest leverage)")
    print("2. Work on critical letters B, I, J which are failing across all counties")
    print("3. Build infrastructure that benefits multiple counties simultaneously")
    print("4. Reserve dixie and taylor for later in session (0/10, needs ground-up work)")