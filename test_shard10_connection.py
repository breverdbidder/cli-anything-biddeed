#!/usr/bin/env python3
"""
Test database connection and get current status for SHARD-10 counties
"""
import os
import requests
import json

# Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

TARGET_COUNTIES = ['manatee', 'alachua', 'martin', 'franklin', 'union']

def test_connection():
    """Test basic connection"""
    if not SUPABASE_KEY:
        print("❌ No API key available")
        print("Available env vars:", [k for k in os.environ.keys() if 'SUPABASE' in k or 'KEY' in k])
        return False
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/fl_counties?select=count&limit=1",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ Database connection successful")
            print(f"Response: {response.text}")
            return True
        else:
            print(f"❌ Connection failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def quick_county_check():
    """Quick check of auction data for target counties"""
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    print("\n=== Quick County Data Check ===")
    for county in TARGET_COUNTIES:
        try:
            response = requests.get(
                f"{SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.{county}&select=count",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                count = len(response.json())
                print(f"{county}: {count} auction records")
            else:
                print(f"{county}: Error {response.status_code}")
        except Exception as e:
            print(f"{county}: Exception {e}")

if __name__ == "__main__":
    print("=== SHARD-10 Database Connection Test ===")
    print(f"Target counties: {', '.join(TARGET_COUNTIES)}")
    print(f"Supabase URL: {SUPABASE_URL}")
    print(f"API Key present: {bool(SUPABASE_KEY)}")
    
    if test_connection():
        quick_county_check()
    else:
        print("❌ Cannot proceed without database connection")