#!/usr/bin/env python3
"""
Quick database test with minimal dependencies
"""
import os
import json
from urllib.request import urlopen, Request
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

def test_db_access():
    """Simple test using standard library only"""
    if not SUPABASE_KEY:
        print("❌ No SUPABASE_KEY found")
        return False
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        # Test basic connection
        url = f"{SUPABASE_URL}/rest/v1/fl_counties?select=count&limit=1"
        req = Request(url, headers=headers)
        
        with urlopen(req, timeout=10) as response:
            if response.status == 200:
                print("✅ Database connection successful")
                return True
            else:
                print(f"❌ Connection failed: {response.status}")
                return False
                
    except (HTTPError, URLError) as e:
        print(f"❌ Connection error: {e}")
        return False

def quick_county_check(county):
    """Quick check of county auction count"""
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        url = f"{SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.{county}&select=count"
        req = Request(url, headers=headers)
        
        with urlopen(req, timeout=15) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                count = len(data) if isinstance(data, list) else 0
                print(f"📊 {county}: {count} auctions")
                return count
            else:
                print(f"⚠️ {county}: HTTP {response.status}")
                return None
                
    except Exception as e:
        print(f"⚠️ {county}: Error - {e}")
        return None

def main():
    print("🔍 Quick Database Test (SHARD-11)")
    print(f"URL: {SUPABASE_URL}")
    print(f"Key available: {'Yes' if SUPABASE_KEY else 'No'}")
    
    if not test_db_access():
        return False
    
    print("\n📊 SHARD-11 County Quick Check:")
    counties = ['manatee', 'washington', 'miami_dade', 'gadsden', 'wakulla']
    
    for county in counties:
        quick_county_check(county)
    
    return True

if __name__ == "__main__":
    success = main()
    print(f"\n{'✅' if success else '❌'} Quick test {'completed' if success else 'failed'}")