#!/usr/bin/env python3
"""Simple environment and connectivity test"""
import os
import sys

print("=== Environment Variables Test ===")
print(f"SUPABASE_URL: {'✅ Set' if os.environ.get('SUPABASE_URL') else '❌ Not set'}")
print(f"SUPABASE_KEY: {'✅ Set' if os.environ.get('SUPABASE_KEY') else '❌ Not set'}")

print("\n=== Python Import Test ===")
try:
    import httpx
    print("✅ httpx available")
except ImportError:
    print("❌ httpx not available")
    sys.exit(1)

print("\n=== Basic Connectivity Test ===")
try:
    # Minimal test using hardcoded connection per CLAUDE.md
    url = "https://mocerqjnksmhcjzxrewo.supabase.co"
    key = os.environ.get('SUPABASE_KEY', '')
    
    if not key:
        print("❌ No API key - testing with basic request")
        # Just test if the URL is reachable
        import httpx
        client = httpx.Client(timeout=10)
        response = client.get(url)
        print(f"URL reachable: {response.status_code}")
    else:
        print("✅ API key available, testing authenticated request")
        import httpx
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }
        client = httpx.Client(timeout=10)
        response = client.get(f"{url}/rest/v1/", headers=headers)
        print(f"Auth test: {response.status_code}")
        
except Exception as e:
    print(f"❌ Connection error: {e}")

print("\n=== Ready for Gold Standard Work ===")
print("Counties assigned: citrus, baker, leon, walton, lafayette")
print("Expected current status from issue brief:")
print("- citrus: 2/10 (A,E pass)")
print("- baker: 1/10 (A pass)")
print("- leon: 1/10 (A pass)")
print("- walton: 1/10 (A pass)")
print("- lafayette: 0/10 (all fail)")