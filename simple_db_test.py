#!/usr/bin/env python3
"""
Simple database connection test for GitHub Actions environment
"""
import os

# Check environment variables
print("=== Environment Check ===")
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")

print(f"SUPABASE_URL present: {bool(supabase_url)}")
if supabase_url:
    print(f"SUPABASE_URL: {supabase_url}")
print(f"SUPABASE_KEY present: {bool(supabase_key)}")
if supabase_key:
    print(f"SUPABASE_KEY length: {len(supabase_key)}")

# Try basic connection
if supabase_url and supabase_key:
    try:
        import requests
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{supabase_url}/rest/v1/audit_log?limit=1",
            headers=headers,
            timeout=10
        )
        
        print(f"Connection test status: {response.status_code}")
        if response.status_code == 200:
            print("✅ Connection successful!")
        else:
            print(f"❌ Connection failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
else:
    print("❌ Missing credentials - cannot test connection")

# Try the evaluation function with a simple county
if supabase_url and supabase_key:
    try:
        print("\n=== Testing evaluation function ===")
        payload = {"county_name": "brevard"}
        response = requests.post(
            f"{supabase_url}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        print(f"Evaluation test status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Evaluation successful! Result type: {type(result)}, length: {len(result) if isinstance(result, list) else 'N/A'}")
            if isinstance(result, list) and len(result) > 0:
                print(f"Sample result: {result[0]}")
        else:
            print(f"❌ Evaluation failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Evaluation error: {e}")