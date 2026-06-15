#!/usr/bin/env python3
"""Simple check for Supabase environment variables"""
import os

print("=== ENVIRONMENT CHECK ===")
print(f"SUPABASE_URL: {os.environ.get('SUPABASE_URL', 'NOT SET')}")
print(f"SUPABASE_KEY: {'SET' if os.environ.get('SUPABASE_KEY') else 'NOT SET'}")
print(f"SUPABASE_SERVICE_ROLE_KEY: {'SET' if os.environ.get('SUPABASE_SERVICE_ROLE_KEY') else 'NOT SET'}")
print(f"SUPABASE_SERVICE_KEY: {'SET' if os.environ.get('SUPABASE_SERVICE_KEY') else 'NOT SET'}")

# Show all env vars that contain 'supabase' (case insensitive)
print("\n=== SUPABASE-RELATED ENV VARS ===")
for key, value in os.environ.items():
    if 'supabase' in key.lower():
        print(f"{key}: {'SET' if value else 'NOT SET'}")

print("\n=== OTHER DB VARS ===")
for key in ['DB_PASSWORD', 'DB_POOLER', 'DATABASE_URL']:
    value = os.environ.get(key)
    print(f"{key}: {'SET' if value else 'NOT SET'}")