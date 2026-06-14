#!/usr/bin/env python3
"""
Simple test to verify database access for SHARD-3 session
"""
import os
import sys

print(f"Python version: {sys.version}")
print(f"Working directory: {os.getcwd()}")

# Check environment
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")

print(f"SUPABASE_URL: {'✅ Set' if supabase_url else '❌ Not set'}")
print(f"SUPABASE_KEY: {'✅ Set' if supabase_key else '❌ Not set'}")

if supabase_url:
    print(f"URL: {supabase_url}")
if supabase_key:
    print(f"Key: {supabase_key[:20]}..." if len(supabase_key) > 20 else supabase_key)

# Test httpx import
try:
    import httpx
    print("✅ httpx available")
except ImportError:
    print("❌ httpx not available - attempting install")
    import subprocess
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx"])
        import httpx
        print("✅ httpx installed and imported")
    except Exception as e:
        print(f"❌ Failed to install httpx: {e}")
        sys.exit(1)

# Test basic connection if credentials available
if supabase_url and supabase_key:
    try:
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json"
        }
        
        client = httpx.Client(timeout=30)
        response = client.get(f"{supabase_url}/rest/v1/fl_counties?select=count&limit=1", headers=headers)
        
        print(f"Connection test: {response.status_code}")
        if response.status_code == 200:
            print("✅ Database connection successful")
            
            # Quick test of pencil_dod_evaluate_county for charlotte
            test_response = client.post(
                f"{supabase_url}/rest/v1/rpc/pencil_dod_evaluate_county",
                headers=headers,
                json={"county_slug_arg": "charlotte"}
            )
            
            if test_response.status_code == 200:
                result = test_response.json()
                if result:
                    passed = sum(1 for item in result if item.get('pass', False))
                    print(f"✅ Charlotte evaluation: {passed}/10 letters passing")
                else:
                    print("⚠️ Charlotte evaluation returned no data")
            else:
                print(f"❌ Charlotte evaluation failed: {test_response.status_code}")
        else:
            print(f"❌ Connection failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
else:
    print("⚠️ Missing credentials - cannot test connection")

print("Test completed")