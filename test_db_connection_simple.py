#!/usr/bin/env python3
"""
Simple database connection test for SHARD-11
"""
import os
import requests
import json

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"

print(f"Testing connection to: {SUPABASE_URL}")
print(f"API key available: {'Yes' if SUPABASE_KEY else 'No'}")

if not SUPABASE_KEY:
    print("❌ No SUPABASE_KEY found in environment")
    exit(1)

HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}", 
    "Content-Type": "application/json"
}

try:
    response = requests.get(f"{BASE}/audit_log", headers=HEADERS, params={"limit": "1"}, timeout=10)
    print(f"Response status: {response.status_code}")
    
    if response.status_code == 200:
        print("✅ Database connection successful")
        data = response.json()
        print(f"Query returned {len(data)} rows")
    else:
        print(f"❌ Connection failed: {response.status_code}")
        print(f"Response: {response.text}")
        
except Exception as e:
    print(f"❌ Connection error: {e}")