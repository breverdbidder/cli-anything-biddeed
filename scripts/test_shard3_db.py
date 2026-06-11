#!/usr/bin/env python3
"""
Simple database connection test for SHARD-3 session
"""
import os
import sys

# Try to import httpx and requests  
try:
    import httpx
    print("✅ httpx available")
except ImportError:
    try:
        import requests
        print("✅ requests available (fallback)")
        httpx = None
    except ImportError:
        print("❌ Neither httpx nor requests available")
        sys.exit(1)

# Supabase configuration - check multiple possible env var names
SUPABASE_URL = os.environ.get("SUPABASE_URL") or "https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_KEY = (os.environ.get("SUPABASE_KEY") or 
                os.environ.get("SUPABASE_SERVICE_KEY") or 
                os.environ.get("SUPABASE_ANON_KEY") or "")

print(f"Environment check:")
print(f"  SUPABASE_URL: {SUPABASE_URL}")
print(f"  Key available: {'Yes' if SUPABASE_KEY else 'No'}")
print(f"  Key starts with: {SUPABASE_KEY[:10]}..." if SUPABASE_KEY else "  Key: None")

# Try basic connection without auth first
print(f"\n=== Testing Basic Connection ===")
try:
    if httpx:
        client = httpx.Client(timeout=10)
        r = client.get(SUPABASE_URL)
    else:
        r = requests.get(SUPABASE_URL, timeout=10)
    
    print(f"Status: {r.status_code}")
    print(f"Response length: {len(r.text)} chars")
    
    if r.status_code == 200:
        print("✅ Basic connection successful")
    else:
        print(f"⚠️ Non-200 response, but connection works")
    
except Exception as e:
    print(f"❌ Connection error: {e}")
    print("This might be normal - Supabase requires auth for most endpoints")

# Try with auth if we have a key
if SUPABASE_KEY:
    print(f"\n=== Testing Authenticated Connection ===")
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        # Try the multi_county_auctions table which should exist
        url = f"{SUPABASE_URL}/rest/v1/multi_county_auctions"
        params = {"select": "county", "limit": "5"}
        
        if httpx:
            client = httpx.Client(timeout=10)
            r = client.get(url, headers=headers, params=params)
        else:
            r = requests.get(url, headers=headers, params=params, timeout=10)
        
        print(f"Multi-county auctions test: {r.status_code}")
        
        if r.status_code == 200:
            data = r.json()
            print(f"✅ Authenticated connection successful - got {len(data)} records")
            
            # Show available counties
            counties = set(item.get('county') for item in data if item.get('county'))
            print(f"Sample counties: {sorted(counties)}")
            
        else:
            print(f"❌ Auth failed: {r.status_code} - {r.text[:200]}")
            
    except Exception as e:
        print(f"❌ Authenticated connection error: {e}")
else:
    print(f"\n=== No API Key Available ===")
    print("Skipping authenticated tests")

print(f"\n=== Environment Variables ===")
env_vars = [k for k in os.environ.keys() if any(x in k.upper() for x in ['SUPABASE', 'DB', 'API', 'KEY'])]
print(f"Relevant env vars found: {env_vars}")