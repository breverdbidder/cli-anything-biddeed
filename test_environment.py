#!/usr/bin/env python3
"""
Simple environment and connectivity test
"""
import os
import sys

print("🔍 Environment Check")
print("===================")

# Check critical environment variables
critical_envs = [
    "SUPABASE_URL", 
    "SUPABASE_KEY", 
    "SUPABASE_SERVICE_KEY",
    "GITHUB_TOKEN",
    "RUNNER_OS"
]

print("\n📋 Environment Variables:")
for env in critical_envs:
    value = os.environ.get(env, "NOT SET")
    if env in ["SUPABASE_KEY", "SUPABASE_SERVICE_KEY", "GITHUB_TOKEN"] and value != "NOT SET":
        # Mask sensitive values
        masked_value = value[:8] + "..." + value[-4:] if len(value) > 12 else "***"
        print(f"  {env}: {masked_value}")
    else:
        print(f"  {env}: {value}")

print(f"\n🐍 Python Version: {sys.version}")
print(f"📁 Working Directory: {os.getcwd()}")
print(f"🔗 Python Path: {':'.join(sys.path[:3])}...")

# Test imports
print("\n📦 Testing Imports:")
try:
    import httpx
    print("  ✅ httpx available")
except ImportError:
    print("  ❌ httpx not available")

try:
    import supabase
    print("  ✅ supabase available")
except ImportError:
    print("  ❌ supabase not available")

# Test Supabase URL
supabase_url = os.environ.get("SUPABASE_URL")
if supabase_url:
    print(f"\n🔗 Supabase URL: {supabase_url}")
    if "mocerqjnksmhcjzxrewo" in supabase_url:
        print("  ✅ Correct project URL")
    else:
        print("  ⚠️  Unexpected project URL")
else:
    print("\n❌ SUPABASE_URL not set")

print("\n" + "="*50)