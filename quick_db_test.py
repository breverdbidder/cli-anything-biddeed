#!/usr/bin/env python3
import os
import requests

SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co" 
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

print(f"URL: {SUPABASE_URL}")
print(f"Key present: {bool(SUPABASE_KEY)}")

if not SUPABASE_KEY:
    # The issue description mentioned these as hardcoded in CLAUDE.md
    print("No SUPABASE_KEY in env - checking if we need to hardcode credentials")
    print("From CLAUDE.md, it mentions SUPABASE_URL and SUPABASE_KEY should be available")
    exit(1)

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

try:
    r = requests.get(f"{SUPABASE_URL}/rest/v1/audit_log", headers=headers, params={"limit": "1"}, timeout=10)
    print(f"Response: {r.status_code}")
    if r.status_code == 200:
        print("✅ Connection success")
    else:
        print(f"❌ Failed: {r.text[:200]}")
except Exception as e:
    print(f"❌ Error: {e}")