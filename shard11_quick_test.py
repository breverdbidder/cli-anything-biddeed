#!/usr/bin/env python3
"""
SHARD-11 Quick connectivity test
"""
import os
import sys

print("=== Environment Check ===")
print(f"SUPABASE_URL: {os.environ.get('SUPABASE_URL', 'NOT_SET')}")
print(f"SUPABASE_SERVICE_KEY present: {bool(os.environ.get('SUPABASE_SERVICE_KEY'))}")
print(f"SUPABASE_KEY present: {bool(os.environ.get('SUPABASE_KEY'))}")

# Try httpx
try:
    import httpx
    print("✅ httpx available")
    
    # Test basic connection
    url = os.environ.get('SUPABASE_URL', 'https://mocerqjnksmhcjzxrewo.supabase.co')
    key = os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('SUPABASE_KEY')
    
    if key:
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
        }
        
        print(f"Testing connection to {url}...")
        
        with httpx.Client(timeout=10) as client:
            response = client.get(f"{url}/rest/v1/", headers=headers)
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                print("✅ Database connection works!")
            else:
                print(f"❌ Connection failed: {response.text}")
                
    else:
        print("❌ No API key available")
        
except ImportError:
    print("❌ httpx not available")
except Exception as e:
    print(f"❌ Connection test failed: {e}")