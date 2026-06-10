#!/usr/bin/env python3
"""
Test database connection and check gold standard status
"""
import httpx
import json
import os
import sys
from datetime import datetime

def main():
    # Get database credentials
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
    
    if not SUPABASE_KEY:
        print("❌ No SUPABASE_KEY found in environment")
        return 1
        
    print(f"🔗 Connecting to: {SUPABASE_URL}")
    
    # Test connection with a simple query
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        client = httpx.Client(timeout=30)
        
        # Test basic connection with a simple query
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/gold_standard_scoreboard?select=county_slug,pass_count,gold_standard&order=pass_count.desc",
            headers=headers
        )
        
        if response.status_code != 200:
            print(f"❌ Database connection failed: {response.status_code}")
            print(f"Response: {response.text}")
            return 1
            
        data = response.json()
        print(f"✅ Database connection successful!")
        print(f"📊 Current Gold Standard Status:")
        
        for county in data[:10]:  # Top 10 counties
            gold_status = "🏆 GOLD" if county.get('gold_standard', False) else f"   {county.get('pass_count', 0)}/10"
            print(f"   {county['county_slug']:<15} {gold_status}")
            
        return 0
        
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())