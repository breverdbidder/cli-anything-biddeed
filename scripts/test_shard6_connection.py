#!/usr/bin/env python3
"""
Test SHARD-6 database connection and basic functionality
"""

import os
import sys
import json
import httpx
from datetime import datetime, timezone

# Supabase configuration - same pattern as other scripts
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

print("SHARD-6 Connection Test")
print(f"Supabase URL: {SUPABASE_URL}")
print(f"Key available: {'✅' if SUPABASE_KEY else '❌'}")
print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")

# Test basic connection
try:
    client = httpx.Client(timeout=30)
    
    print("\n1. Testing basic connection...")
    response = client.get(f"{BASE}/", headers=HEADERS)
    print(f"Status: {response.status_code}")
    
    print("\n2. Testing counties table access...")
    response = client.get(f"{BASE}/counties", headers=HEADERS, params={'limit': 1})
    print(f"Counties table: {response.status_code}")
    
    print("\n3. Testing multi_county_auctions table...")
    response = client.get(f"{BASE}/multi_county_auctions", headers=HEADERS, params={'limit': 1})
    print(f"Multi county auctions: {response.status_code}")
    
    print("\n4. Testing RPC function...")
    try:
        # Try the evaluation function with a test county
        response = client.post(
            f"{BASE}/rpc/pencil_dod_evaluate_county",
            headers=HEADERS,
            json={'county_param': 'brevard'},  # Known working county
            timeout=60
        )
        print(f"RPC evaluation: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"Sample result: {type(result)} with {len(result) if isinstance(result, list) else 'N/A'} items")
        else:
            print(f"RPC error: {response.text[:200]}")
    except Exception as e:
        print(f"RPC test failed: {e}")
    
    print("\n✅ Connection test complete")
    
except Exception as e:
    print(f"❌ Connection test failed: {e}")
    sys.exit(1)