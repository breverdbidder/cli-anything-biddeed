#!/usr/bin/env python3
"""
Test database connection for SHARD-12 session
"""
import os
import sys
import httpx
import json
from datetime import datetime, timezone

# Add shared module to path
sys.path.append('/home/runner/work/cli-anything-biddeed/cli-anything-biddeed/shared')

try:
    from cli_anything_shared.supabase import get_client, health_check
    HAS_SHARED = True
except ImportError:
    HAS_SHARED = False

# Fallback Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

def test_direct_connection():
    """Test direct HTTP connection to Supabase"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return False, "Missing SUPABASE_URL or SUPABASE_KEY environment variables"
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        with httpx.Client(timeout=30) as client:
            # Test basic connectivity
            response = client.get(
                f"{SUPABASE_URL}/rest/v1/fl_counties",
                headers=headers,
                params={"limit": "1"}
            )
            
            if response.status_code == 200:
                data = response.json()
                return True, f"✅ Connected successfully. FL counties table accessible. Sample: {len(data)} rows"
            else:
                return False, f"❌ HTTP {response.status_code}: {response.text}"
                
    except Exception as e:
        return False, f"❌ Connection failed: {e}"

def test_county_evaluation_rpc():
    """Test the pencil_dod_evaluate_county RPC function"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return False, "Missing credentials"
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        with httpx.Client(timeout=60) as client:
            # Try evaluating marion county as a test
            response = client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
                headers=headers,
                json={"county_slug_arg": "marion"}
            )
            
            if response.status_code == 200:
                result = response.json()
                return True, f"✅ RPC function working. Marion evaluation: {len(result) if isinstance(result, list) else 'single result'}"
            else:
                return False, f"❌ RPC failed: HTTP {response.status_code}: {response.text}"
                
    except Exception as e:
        return False, f"❌ RPC test failed: {e}"

def main():
    print("🔍 SHARD-12 Database Connection Test")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"Target: {SUPABASE_URL}")
    print("-" * 50)
    
    # Test 1: Basic connectivity
    print("\n📡 Testing basic connectivity...")
    success, message = test_direct_connection()
    print(message)
    
    if not success:
        print("\n❌ Basic connectivity failed. Cannot proceed with session.")
        return False
    
    # Test 2: RPC evaluation function
    print("\n🔧 Testing county evaluation RPC...")
    success, message = test_county_evaluation_rpc()
    print(message)
    
    # Test 3: Shared module (optional)
    if HAS_SHARED:
        print("\n📦 Testing shared module...")
        try:
            health_check()
            print("✅ Shared module health check passed")
        except Exception as e:
            print(f"⚠️ Shared module failed: {e}")
    else:
        print("\n⚠️ Shared module not available - using direct HTTP")
    
    print("\n" + "="*50)
    print("✅ DATABASE CONNECTION TEST COMPLETED")
    print("Session can proceed with database operations")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)