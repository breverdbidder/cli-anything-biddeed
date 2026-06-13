#!/usr/bin/env python3
"""
SHARD-7 County Status Verification
Check current A-J letter grades for highlands, volusia, miami_dade, columbia, madison

Usage:
  python shard7_verification.py
"""
import os
import json
from datetime import datetime

# Try to use httpx first, fall back to requests
try:
    import httpx as http_client
    print("Using httpx for HTTP requests")
except ImportError:
    try:
        import requests as http_client
        print("Using requests for HTTP requests")
    except ImportError:
        print("❌ Neither httpx nor requests available")
        exit(1)

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"

# SHARD-7 Target counties
SHARD7_COUNTIES = ['highlands', 'volusia', 'miami_dade', 'columbia', 'madison']

def get_headers():
    """Get Supabase API headers"""
    return {
        "apikey": SUPABASE_KEY, 
        "Authorization": f"Bearer {SUPABASE_KEY}", 
        "Content-Type": "application/json"
    }

def test_connection():
    """Test Supabase connection"""
    if not SUPABASE_KEY:
        print("❌ No SUPABASE_KEY environment variable found")
        return False
        
    try:
        if hasattr(http_client, 'get'):  # requests-style
            response = http_client.get(f"{BASE}/fl_counties", headers=get_headers(), params={"limit": "1"}, timeout=10)
            success = response.status_code == 200
        else:  # httpx-style
            with http_client.Client(timeout=10) as client:
                response = client.get(f"{BASE}/fl_counties", headers=get_headers(), params={"limit": "1"})
                success = response.status_code == 200
        
        if success:
            print("✅ Supabase connection successful")
            return True
        else:
            print(f"❌ Connection failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def evaluate_county(county_slug):
    """Evaluate a county using the pencil_dod_evaluate_county RPC function"""
    try:
        payload = {"county_slug_arg": county_slug}
        
        if hasattr(http_client, 'post'):  # requests-style
            response = http_client.post(
                f"{BASE}/rpc/pencil_dod_evaluate_county", 
                headers=get_headers(), 
                json=payload,
                timeout=30
            )
        else:  # httpx-style
            with http_client.Client(timeout=30) as client:
                response = client.post(
                    f"{BASE}/rpc/pencil_dod_evaluate_county", 
                    headers=get_headers(), 
                    json=payload
                )
        
        if response.status_code == 200:
            result = response.json()
            return result
        else:
            print(f"❌ Failed to evaluate {county_slug}: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error evaluating {county_slug}: {e}")
        return None

def main():
    print("=== SHARD-7 County Status Verification ===")
    print(f"Target counties: {', '.join(SHARD7_COUNTIES)}")
    print()
    
    if not test_connection():
        print("Database connection failed. Exiting.")
        return
    
    print("\n=== County Evaluations ===")
    
    for county in SHARD7_COUNTIES:
        print(f"\n--- {county.upper()} ---")
        result = evaluate_county(county)
        
        if result:
            pass_count = 0
            total_count = 0
            
            if isinstance(result, list):
                for item in result:
                    letter = item.get('letter', '?')
                    metric = item.get('metric')
                    passed = item.get('pass', False)
                    status = "PASS" if passed else "FAIL"
                    
                    print(f"  {letter}: {status} (metric={metric})")
                    
                    if passed:
                        pass_count += 1
                    total_count += 1
            else:
                print(f"  Unexpected result format: {result}")
            
            print(f"  Summary: {pass_count}/{total_count} letters passing")
        else:
            print(f"  Could not evaluate {county}")
    
    print(f"\n=== Verification Complete at {datetime.now().isoformat()} ===")

if __name__ == "__main__":
    main()