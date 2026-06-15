#!/usr/bin/env python3
"""
Test connectivity and environment setup for SHARD-28
"""
import os
import sys

def test_environment():
    """Test environment variables and dependencies"""
    print("=== SHARD-28 Environment Test ===")
    
    # Check Python version
    print(f"Python version: {sys.version}")
    
    # Check environment variables
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")
    
    print(f"SUPABASE_URL: {'SET' if supabase_url else 'NOT SET'}")
    print(f"SUPABASE_KEY: {'SET' if supabase_key else 'NOT SET'}")
    
    if supabase_url:
        print(f"URL value: {supabase_url}")
    
    # Check required modules
    modules_to_check = ['requests', 'json', 'datetime', 'subprocess']
    for module in modules_to_check:
        try:
            __import__(module)
            print(f"✅ {module} module available")
        except ImportError:
            print(f"❌ {module} module NOT available")
    
    # Test requests if available
    try:
        import requests
        # Simple test without authentication
        response = requests.get("https://httpbin.org/status/200", timeout=5)
        print(f"✅ HTTP requests working (status: {response.status_code})")
    except Exception as e:
        print(f"❌ HTTP requests failed: {e}")
    
    return supabase_url, supabase_key

if __name__ == "__main__":
    test_environment()