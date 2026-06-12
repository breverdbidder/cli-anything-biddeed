#!/usr/bin/env python3
"""Simple test for SHARD-7 database connectivity and status check"""
import os

# Check if we have the required environment
print("SHARD-7 Environment Check")
print("=" * 50)

supabase_url = os.environ.get("SUPABASE_URL", "NOT_SET")
supabase_key = os.environ.get("SUPABASE_KEY", "NOT_SET")

print(f"SUPABASE_URL: {supabase_url}")
print(f"SUPABASE_KEY: {'SET' if supabase_key != 'NOT_SET' else 'NOT_SET'}")

# Check if we can import httpx
try:
    import httpx
    print("✅ httpx available")
except ImportError:
    print("❌ httpx not available")
    print("Run: pip install httpx")

# Basic connectivity test if we have credentials
if supabase_key != "NOT_SET":
    print("\nTesting database connection...")
    try:
        import httpx
        client = httpx.Client(timeout=30)
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
        }
        
        response = client.get(f"{supabase_url}/rest/v1/fl_counties?limit=1", headers=headers)
        print(f"Database response: {response.status_code}")
        if response.status_code == 200:
            print("✅ Database connection successful")
        else:
            print(f"❌ Database connection failed: {response.text[:200]}")
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
else:
    print("\n⚠️ Cannot test database - SUPABASE_KEY not set")

print("\nSHARD-7 Counties:")
counties = ['hillsborough', 'st_lucie', 'hernando', 'columbia', 'madison']
for i, county in enumerate(counties, 1):
    print(f"{i}. {county}")