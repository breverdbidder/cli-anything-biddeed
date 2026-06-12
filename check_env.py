#!/usr/bin/env python3
"""
Check environment variables and test basic connectivity
"""
import os
import sys

print("=== Environment Check ===")

# Check for Supabase credentials
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY") 
supabase_service_key = os.environ.get("SUPABASE_SERVICE_KEY")

print(f"SUPABASE_URL: {'✅' if supabase_url else '❌'} {supabase_url}")
print(f"SUPABASE_KEY: {'✅' if supabase_key else '❌'} {'Present' if supabase_key else 'Missing'}")
print(f"SUPABASE_SERVICE_KEY: {'✅' if supabase_service_key else '❌'} {'Present' if supabase_service_key else 'Missing'}")

# Try hardcoded connection as used in other scripts
print(f"\n=== Hardcoded Connection Test ===")
print("Using hardcoded URL: https://mocerqjnksmhcjzxrewo.supabase.co")

# Check available Python packages
try:
    import requests
    print("✅ requests available")
except ImportError:
    print("❌ requests not available")

try:
    import httpx  
    print("✅ httpx available")
except ImportError:
    print("❌ httpx not available")

# If we have at least one key, test basic connectivity
key = supabase_key or supabase_service_key
if key:
    print(f"\n=== Basic Connectivity Test ===")
    try:
        import requests
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }
        
        base_url = "https://mocerqjnksmhcjzxrewo.supabase.co/rest/v1"
        response = requests.get(f"{base_url}/fl_counties?select=count&limit=1", headers=headers, timeout=10)
        
        print(f"Response status: {response.status_code}")
        if response.status_code == 200:
            print("✅ Database connection successful!")
        else:
            print(f"❌ Connection failed: {response.text[:200]}")
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
else:
    print("❌ No API key available for connectivity test")