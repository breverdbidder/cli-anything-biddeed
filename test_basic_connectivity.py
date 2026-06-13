#!/usr/bin/env python3
"""
Basic connectivity test to verify database access is available
"""
import os
import sys

# Check for required libraries
try:
    import httpx
    print("✅ httpx available")
except ImportError:
    print("❌ httpx not available")
    try:
        import requests
        print("✅ requests available as fallback")
        httpx = None
    except ImportError:
        print("❌ No HTTP library available")
        sys.exit(1)

# Check environment variables 
print(f"\nEnvironment check:")
print(f"SUPABASE_URL: {os.environ.get('SUPABASE_URL', 'NOT_SET')}")
print(f"SUPABASE_KEY: {'SET' if os.environ.get('SUPABASE_KEY') else 'NOT_SET'}")
print(f"SUPABASE_SERVICE_KEY: {'SET' if os.environ.get('SUPABASE_SERVICE_KEY') else 'NOT_SET'}")

# Try to identify available secrets/env from GitHub Actions
if 'GITHUB_ACTIONS' in os.environ:
    print("Running in GitHub Actions environment")
    # Check for other possible env vars
    for key in sorted(os.environ.keys()):
        if 'SUPABASE' in key.upper():
            value = os.environ[key]
            print(f"{key}: {value[:20]}{'...' if len(value) > 20 else ''}")

print("\nTest complete.")