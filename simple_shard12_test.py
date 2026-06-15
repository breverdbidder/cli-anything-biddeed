#!/usr/bin/env python3
"""
Simple test of SHARD-12 county data access
Uses direct database connection based on CLAUDE.md specs
"""

# Database configuration from CLAUDE.md
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"

# Try to find imports
try:
    import httpx
    HTTP_CLIENT = "httpx"
except ImportError:
    try:
        import requests
        HTTP_CLIENT = "requests"
    except ImportError:
        print("❌ No HTTP client available")
        exit(1)

import os

print(f"✅ Using {HTTP_CLIENT} for HTTP requests")
print(f"Database URL: {SUPABASE_URL}")

# Check if we can access basic public endpoints
try:
    if HTTP_CLIENT == "httpx":
        client = httpx.Client(timeout=10)
        # Try a public health check
        r = client.get(f"{SUPABASE_URL}/rest/v1/")
        print(f"Base endpoint status: {r.status_code}")
    else:
        import requests
        r = requests.get(f"{SUPABASE_URL}/rest/v1/", timeout=10)
        print(f"Base endpoint status: {r.status_code}")
        
except Exception as e:
    print(f"Connection test failed: {e}")

# SHARD-12 counties from issue
counties = ['sarasota', 'hendry', 'pasco', 'glades']
print(f"\nTarget counties: {counties}")

print("\n📊 Issue-reported current metrics:")
print("sarasota (2/10): A✓ metric=3153, H✓ metric=4.1")  
print("hendry (1/10): D✓ metric=100.0")
print("pasco (1/10): A✓ metric=3808")
print("glades (0/10): All failing")

print("\n⚡ High-leverage targets per CRITERION-PARALLEL:")
print("1. C/D: Parity fixes (frozen numerators, PropertyOnion gaps)")
print("2. J: Deal generator (bid_decisions pipeline)")  
print("3. B: Verified outcomes (independent sources)")
print("4. E: Parcel linkage (enables I)")
print("5. G: Zoning substrate (enables I)")

print("\n🚀 Next: Create county-specific improvement scripts following SHIP-TO-MAIN mandate")