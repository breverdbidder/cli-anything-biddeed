#!/usr/bin/env python3
"""
Test what environment variables are available in this session
"""
import os

# Check for Supabase environment variables
supabase_vars = [
    "SUPABASE_URL",
    "SUPABASE_KEY", 
    "SUPABASE_SERVICE_KEY"
]

print("=== SUPABASE ENVIRONMENT CHECK ===")
for var in supabase_vars:
    value = os.environ.get(var, "")
    if value:
        print(f"{var}: {'*' * min(10, len(value))} (length: {len(value)})")
    else:
        print(f"{var}: NOT SET")

# Check for other relevant environment variables
other_vars = [
    "GH_PAT",
    "GH_TOKEN", 
    "GITHUB_TOKEN"
]

print("\n=== GITHUB ENVIRONMENT CHECK ===")
for var in other_vars:
    value = os.environ.get(var, "")
    if value:
        print(f"{var}: {'*' * min(10, len(value))} (length: {len(value)})")
    else:
        print(f"{var}: NOT SET")

# Try to import required packages
print("\n=== PACKAGE AVAILABILITY CHECK ===")
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

try:
    from supabase import create_client
    print("✅ supabase client available")
except ImportError:
    print("❌ supabase client not available")