#!/usr/bin/env python3
"""
SHARD-14 County Status Verification
Check current A-J letter grades for osceola, gilchrist, seminole, hamilton

Usage:
  python scripts/verify_shard14_status.py
"""
import os
import httpx
import json
from datetime import datetime

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}", 
    "Content-Type": "application/json"
}

# Target counties for SHARD-14
SHARD14_COUNTIES = ['osceola', 'gilchrist', 'seminole', 'hamilton']

def test_connection():
    """Test Supabase connection"""
    try:
        with httpx.Client(timeout=10) as client:
            response = client.get(f"{BASE}/audit_log", headers=HEADERS, params={"limit": "1"})
            if response.status_code == 200:
                print("✅ Supabase connection successful")
                return True
            else:
                print(f"❌ Connection failed: {response.status_code} - {response.text}")
                return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def get_county_evaluation(county_slug):
    """Get evaluation for a specific county using pencil_dod_evaluate_county function"""
    try:
        # Use RPC call to the evaluation function - try both parameter names
        with httpx.Client(timeout=30) as client:
            for param_name in ["county_slug_arg", "county_name"]:
                payload = {param_name: county_slug}
                response = client.post(
                    f"{BASE}/rpc/pencil_dod_evaluate_county", 
                    headers=HEADERS, 
                    json=payload
                )
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✅ Evaluation for {county_slug} (using {param_name}):")
                    
                    if isinstance(result, list) and len(result) > 0:
                        passes = 0
                        for letter_data in result:
                            letter = letter_data.get('letter', '?')
                            metric = letter_data.get('metric')
                            is_pass = letter_data.get('pass', False)
                            status = "✅ PASS" if is_pass else "❌ FAIL"
                            print(f"  {letter}: {status} metric={metric}")
                            if is_pass:
                                passes += 1
                        
                        print(f"  SUMMARY: {passes}/10 letters passing")
                        return result, passes
                    else:
                        print(f"  No evaluation data returned")
                        return None, 0
            
            print(f"❌ Failed to evaluate {county_slug}: {response.status_code} - {response.text}")
            return None, 0
        
    except Exception as e:
        print(f"❌ Error evaluating {county_slug}: {e}")
        return None, 0

def get_gold_standard_status():
    """Get current gold standard status from database"""
    try:
        with httpx.Client(timeout=30) as client:
            # Get latest gold standard county status
            response = client.get(
                f"{BASE}/gold_standard_county_status", 
                headers=HEADERS,
                params={
                    "select": "*",
                    "county_slug": f"in.({','.join(SHARD14_COUNTIES)})",
                    "order": "loop_run_id.desc",
                    "limit": "20"
                }
            )
            
            if response.status_code == 200:
                results = response.json()
                print(f"✅ Retrieved {len(results)} gold standard records")
                
                # Get latest for each county
                latest_by_county = {}
                for record in results:
                    county = record.get('county_slug')
                    if county not in latest_by_county:
                        latest_by_county[county] = record
                        
                return latest_by_county
            else:
                print(f"❌ Failed to get gold standard status: {response.status_code} - {response.text}")
                return {}
            
    except Exception as e:
        print(f"❌ Error getting gold standard status: {e}")
        return {}

if __name__ == "__main__":
    print("=== SHARD-14 County Status Verification ===")
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    print(f"Counties: {', '.join(SHARD14_COUNTIES)}")
    
    if not SUPABASE_KEY:
        print("❌ No Supabase API key found in environment")
        exit(1)
    
    # Test connection
    if not test_connection():
        exit(1)
    
    print("\n=== Current Gold Standard Status ===")
    gold_status = get_gold_standard_status()
    
    if gold_status:
        for county in SHARD14_COUNTIES:
            if county in gold_status:
                data = gold_status[county]
                print(f"\n{county}:")
                print(f"  Loop run: {data.get('loop_run_id', 'N/A')}")
                print(f"  Pass count: {data.get('pass_count', 'N/A')}/10")
                print(f"  Last updated: {data.get('updated_at', 'N/A')}")
            else:
                print(f"\n{county}: No gold standard data found")
    
    print("\n=== Fresh Live Evaluations ===")
    all_results = {}
    total_passes = 0
    
    for county in SHARD14_COUNTIES:
        print(f"\n--- {county} ---")
        result, passes = get_county_evaluation(county)
        all_results[county] = result
        total_passes += passes
    
    print(f"\n=== SHARD-14 SUMMARY ===")
    print(f"Total passes across all counties: {total_passes}/40")
    print(f"Average: {total_passes/4:.1f} passes per county")
    
    # Priority analysis based on issue brief
    print(f"\n=== PRIORITY ANALYSIS ===")
    for county in SHARD14_COUNTIES:
        if county in all_results and all_results[county]:
            result = all_results[county]
            failing_letters = [item for item in result if not item.get('pass', False)]
            failing_letter_names = [item.get('letter', '?') for item in failing_letters]
            print(f"{county}: {len(failing_letters)} failing letters: {', '.join(failing_letter_names)}")