#!/usr/bin/env python3
"""Test database connection for Gold Standard Campaign"""
import os
import sys

# Check for Supabase environment variables
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")
supabase_db_url = os.environ.get("SUPABASE_DB_URL")

print("=== SUPABASE ENVIRONMENT CHECK ===")
print(f"SUPABASE_URL: {'✓ SET' if supabase_url else '✗ NOT SET'}")
print(f"SUPABASE_KEY: {'✓ SET' if supabase_key else '✗ NOT SET'}")
print(f"SUPABASE_DB_URL: {'✓ SET' if supabase_db_url else '✗ NOT SET'}")

if supabase_url:
    print(f"URL: {supabase_url[:50]}..." if len(supabase_url) > 50 else supabase_url)

if not any([supabase_url, supabase_key, supabase_db_url]):
    print("\n❌ No Supabase credentials found in environment")
    sys.exit(1)
else:
    print("\n✅ Some Supabase credentials found")

# Try to import required libraries
try:
    import httpx
    print("✓ httpx available")
except ImportError:
    print("✗ httpx not available")

try:
    import psycopg2
    print("✓ psycopg2 available")
except ImportError:
    print("✗ psycopg2 not available")
    try:
        import psycopg
        print("✓ psycopg (v3) available")
    except ImportError:
        print("✗ No PostgreSQL driver available")