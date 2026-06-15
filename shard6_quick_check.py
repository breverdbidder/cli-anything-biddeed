#!/usr/bin/env python3
"""
Quick check of assigned counties for SHARD-6
"""
import os

print("SHARD-6 Environment Check")
print("="*40)

# Check environment variables
print(f"SUPABASE_URL available: {bool(os.environ.get('SUPABASE_URL'))}")
print(f"SUPABASE_KEY available: {bool(os.environ.get('SUPABASE_KEY'))}")
print(f"SUPABASE_SERVICE_KEY available: {bool(os.environ.get('SUPABASE_SERVICE_KEY'))}")

# Assigned counties
counties = ['hillsborough', 'bay', 'martin', 'calhoun', 'liberty']
print(f"\nAssigned counties: {counties}")

# Check if httpx is available
try:
    import httpx
    print("✅ httpx available")
    
    # If we have credentials, try a simple connection test
    key = os.environ.get('SUPABASE_KEY') or os.environ.get('SUPABASE_SERVICE_KEY')
    if key:
        print("✅ API key found")
        
        # Simple test
        try:
            url = "https://mocerqjnksmhcjzxrewo.supabase.co"
            headers = {
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json"
            }
            
            client = httpx.Client(timeout=10)
            r = client.get(f"{url}/rest/v1/fl_counties", headers=headers, params={'limit': 1})
            print(f"✅ DB connection test: {r.status_code}")
            
            if r.status_code == 200:
                print("✅ Database accessible")
            else:
                print(f"❌ Database error: {r.text[:100]}")
                
        except Exception as e:
            print(f"❌ Connection error: {e}")
    else:
        print("❌ No API key available")
        
except ImportError:
    print("❌ httpx not available")

print("\n" + "="*40)