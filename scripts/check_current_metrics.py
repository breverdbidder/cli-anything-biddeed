#!/usr/bin/env python3
"""
Check Current Gold Standard Metrics for brevard and duval
ULTRALOOP Session 19 - Live Database Query
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

if not SUPABASE_KEY:
    print("❌ No Supabase key found in environment")
    sys.exit(1)

HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

def check_county_metrics(county_name):
    """Check current metrics for a specific county"""
    print(f"\n📊 CHECKING METRICS FOR: {county_name.upper()}")
    print("=" * 60)
    
    try:
        client = httpx.Client(timeout=120)
        
        # Call the evaluation function
        response = client.post(
            f"{BASE}/rpc/pencil_dod_evaluate_county",
            headers=HEADERS,
            json={'county_param': county_name},
            timeout=120
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Status Code: {response.status_code}")
            
            if result:
                print("\n📈 CURRENT METRICS:")
                print("-" * 40)
                
                # Parse the result 
                if isinstance(result, list) and len(result) > 0:
                    metrics = result[0] if isinstance(result[0], dict) else {}
                elif isinstance(result, dict):
                    metrics = result
                else:
                    print(f"Raw result: {result}")
                    return result
                
                # Display key metrics from the brief
                letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']
                
                for letter in letters:
                    # Try different possible key patterns
                    metric_key = None
                    for key in metrics.keys():
                        if key.lower().startswith(f'letter_{letter.lower()}') or key.lower() == f'{letter.lower()}_metric':
                            metric_key = key
                            break
                    
                    if metric_key:
                        value = metrics[metric_key]
                        status = "✅ PASS" if value and str(value).replace('.', '').isdigit() and float(value) >= 95 else "❌ FAIL"
                        print(f"{letter}: {value} {status}")
                    else:
                        print(f"{letter}: No metric found")
                
                # Show all available keys for debugging
                print(f"\nAvailable metric keys: {list(metrics.keys())}")
                
            else:
                print("No results returned from evaluation")
                
            return result
            
        else:
            print(f"❌ Query failed with status {response.status_code}")
            print(f"Error: {response.text[:500]}")
            return None
            
    except Exception as e:
        print(f"❌ Error checking {county_name} metrics: {e}")
        return None

def main():
    """Main function to check both target counties"""
    
    print("🚀 GOLD STANDARD METRICS CHECK")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"Database: {SUPABASE_URL}")
    
    target_counties = ['brevard', 'duval']
    results = {}
    
    for county in target_counties:
        result = check_county_metrics(county)
        results[county] = result
    
    print("\n" + "=" * 80)
    print("📋 SUMMARY")
    print("=" * 80)
    
    for county, result in results.items():
        status = "✅ SUCCESS" if result is not None else "❌ FAILED"
        print(f"{county.upper():15s} {status}")
    
    # Save raw results for analysis
    results_file = f"/tmp/metrics_check_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    try:
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n💾 Raw results saved to: {results_file}")
    except Exception as e:
        print(f"⚠️ Could not save results: {e}")
    
    return results

if __name__ == "__main__":
    main()