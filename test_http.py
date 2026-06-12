#!/usr/bin/env python3
"""
Minimal HTTP test for SHARD-11 database access
"""
import os
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

def test_basic_connection():
    """Test basic Supabase connection"""
    print(f"Testing connection to: {SUPABASE_URL}")
    print(f"API key available: {'Yes' if SUPABASE_KEY else 'No'}")
    
    if not SUPABASE_KEY:
        print("❌ No API key - cannot test")
        return False
    
    try:
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        }
        
        url = f"{SUPABASE_URL}/rest/v1/fl_counties?select=count&limit=1"
        req = Request(url, headers=headers)
        
        with urlopen(req, timeout=10) as response:
            if response.status == 200:
                print("✅ Connection successful")
                return True
            else:
                print(f"❌ HTTP {response.status}")
                return False
                
    except (HTTPError, URLError) as e:
        print(f"❌ Connection failed: {e}")
        return False

def test_manatee_auctions():
    """Test querying manatee auctions"""
    if not SUPABASE_KEY:
        return False
        
    try:
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        }
        
        url = f"{SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.manatee&select=count&limit=1"
        req = Request(url, headers=headers)
        
        with urlopen(req, timeout=15) as response:
            if response.status == 200:
                print("✅ Manatee auctions accessible")
                return True
            else:
                print(f"❌ Manatee query HTTP {response.status}")
                return False
                
    except Exception as e:
        print(f"❌ Manatee query failed: {e}")
        return False

if __name__ == "__main__":
    print("🔍 SHARD-11 HTTP Test")
    
    success1 = test_basic_connection()
    success2 = test_manatee_auctions() if success1 else False
    
    if success1 and success2:
        print("\n✅ HTTP tests passed - ready for SHARD-11 fixes")
    else:
        print("\n❌ HTTP tests failed - check environment")