#!/usr/bin/env python3
"""
Minimal database connection check for Gold Standard Autopilot Run 17
Counties: brevard, duval
"""

import os
import sys

# Check for required dependencies
try:
    import httpx
    print("✅ httpx available")
except ImportError:
    print("❌ httpx not available")
    sys.exit(1)

# Database configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

print(f"Supabase URL: {SUPABASE_URL}")
print(f"Supabase key available: {bool(SUPABASE_KEY)}")

if not SUPABASE_KEY:
    print("❌ No Supabase key found in environment variables")
    print("Available environment keys:")
    for key in sorted(os.environ.keys()):
        if 'supabase' in key.lower() or 'sb_' in key.lower():
            print(f"  {key}: {'[SET]' if os.environ[key] else '[EMPTY]'}")
    sys.exit(1)

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

def test_connection():
    """Test basic database connectivity"""
    try:
        client = httpx.Client(timeout=30)
        
        print("\n=== Testing Database Connection ===")
        # Test basic REST API endpoint
        r = client.get(f"{SUPABASE_URL}/rest/v1/", headers=headers)
        print(f"REST API status: {r.status_code}")
        
        if r.status_code != 200:
            print(f"Connection failed: {r.text}")
            return False
            
        print("✅ Database connection successful")
        return True
        
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def get_county_metrics(county_slug):
    """Query current metrics for a county using the pencil_dod_evaluate_county function"""
    try:
        client = httpx.Client(timeout=60)
        
        # Call the evaluation RPC function
        print(f"\n=== Evaluating {county_slug} ===")
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=headers,
            json={"county_slug_arg": county_slug}
        )
        
        if r.status_code == 200:
            result = r.json()
            print(f"✅ Evaluation successful for {county_slug}")
            
            if isinstance(result, list):
                print(f"Letter results (total: {len(result)}):")
                for item in result:
                    letter = item.get('letter', '?')
                    metric = item.get('metric', 'N/A')
                    passed = item.get('pass', False)
                    status = "✅ PASS" if passed else "❌ FAIL"
                    print(f"  {letter}: {status} metric={metric}")
            else:
                print(f"Unexpected result format: {type(result)}")
            
            return result
        else:
            print(f"❌ Evaluation failed for {county_slug}: {r.status_code}")
            print(f"Response: {r.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error evaluating {county_slug}: {e}")
        return None

if __name__ == "__main__":
    print("GOLD STANDARD AUTOPILOT - Run 17 Database Check")
    print("Counties: brevard, duval")
    print("="*50)
    
    # Test connection first
    if not test_connection():
        sys.exit(1)
    
    # Get metrics for assigned counties
    counties = ['brevard', 'duval']
    results = {}
    
    for county in counties:
        result = get_county_metrics(county)
        if result:
            results[county] = result
    
    # Summary
    print(f"\n=== SUMMARY ===")
    for county, data in results.items():
        if data and isinstance(data, list):
            pass_count = sum(1 for item in data if item.get('pass', False))
            total_count = len(data)
            print(f"{county}: {pass_count}/{total_count} criteria passing")
        else:
            print(f"{county}: No data available")
    
    print("\nDatabase check complete. Ready for autopilot session.")