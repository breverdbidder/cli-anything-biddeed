#!/usr/bin/env python3
"""
Simple SHARD-14 County Status Checker
Checks current state using REST API only

Usage:
  python scripts/shard14_county_status_simple.py
"""
import os
import sys
import httpx
from datetime import datetime

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# SHARD-14 target counties 
TARGET_COUNTIES = [
    {'name': 'Osceola', 'co_no': 59, 'slug': 'osceola'},
    {'name': 'Bay', 'co_no': 13, 'slug': 'bay'}, 
    {'name': 'Okeechobee', 'co_no': 57, 'slug': 'okeechobee'},
    {'name': 'Hamilton', 'co_no': 34, 'slug': 'hamilton'}
]

def check_county_basic_status(county):
    """Check basic auction counts and county setup for a county"""
    try:
        client = httpx.Client(timeout=30)
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        name = county['name']
        co_no = county['co_no']
        slug = county['slug']
        
        # Check fl_counties
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/fl_counties?co_no=eq.{co_no}&select=*",
            headers=headers
        )
        
        fl_county_exists = False
        if response.status_code == 200 and response.json():
            fl_county = response.json()[0]
            fl_county_exists = True
            actual_slug = fl_county.get('slug')
        else:
            actual_slug = None
        
        # Check multi_county_auctions count
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.{slug}&select=case_number",
            headers=headers
        )
        
        auction_count = 0
        if response.status_code == 200:
            auction_count = len(response.json())
        
        # Check closed auctions count
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.{slug}&auction_status=in.(sold,no_sale,canceled)&select=case_number",
            headers=headers
        )
        
        closed_count = 0
        if response.status_code == 200:
            closed_count = len(response.json())
            
        return {
            'name': name,
            'co_no': co_no,
            'expected_slug': slug,
            'actual_slug': actual_slug,
            'fl_county_exists': fl_county_exists,
            'slug_matches': actual_slug == slug,
            'total_auctions': auction_count,
            'closed_auctions': closed_count,
            'has_data': auction_count > 0
        }
        
    except Exception as e:
        return {
            'name': name,
            'co_no': co_no,
            'expected_slug': slug,
            'error': str(e),
            'fl_county_exists': False,
            'total_auctions': 0,
            'closed_auctions': 0,
            'has_data': False
        }

def check_table_exists(table_name):
    """Check if a table exists by trying to query it"""
    try:
        client = httpx.Client(timeout=30)
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/{table_name}?limit=1",
            headers=headers
        )
        
        return response.status_code == 200
        
    except:
        return False

def main():
    print("🔍 SHARD-14 COUNTY STATUS (SIMPLE CHECK)")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print()
    
    # Check environment
    if not SUPABASE_KEY:
        print("❌ SUPABASE_KEY environment variable not set")
        
        # Try to continue with empty key for testing
        print("⚠️ Continuing with empty key for debugging...")
    
    # Basic connection test
    try:
        client = httpx.Client(timeout=10)
        response = client.get(f"{SUPABASE_URL}/rest/v1/", timeout=10)
        if response.status_code in [200, 400, 401]:  # Any response means connection works
            print("✅ Supabase URL reachable")
        else:
            print(f"⚠️ Supabase responded with HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")
        sys.exit(1)
    
    print()
    print("COUNTY STATUS:")
    print("-" * 40)
    
    total_auctions = 0
    counties_with_data = 0
    
    for county in TARGET_COUNTIES:
        status = check_county_basic_status(county)
        name = status['name']
        
        if 'error' in status:
            print(f"❌ {name:12s} ERROR: {status['error']}")
        else:
            co_no = status['co_no']
            slug_status = "✅" if status['slug_matches'] else "❌"
            data_status = "✅" if status['has_data'] else "❌"
            auctions = status['total_auctions']
            closed = status['closed_auctions']
            
            total_auctions += auctions
            if auctions > 0:
                counties_with_data += 1
            
            print(f"{slug_status} {name:12s} co_no={co_no:2d}  {auctions:5d} auctions ({closed:4d} closed)  {data_status}")
    
    print()
    print("TABLE STATUS:")
    print("-" * 40)
    
    required_tables = [
        'fl_counties',
        'multi_county_auctions', 
        'tax_deed_outcomes',
        'foreclosure_outcomes',
        'bid_decisions'
    ]
    
    for table in required_tables:
        exists = check_table_exists(table)
        status = "✅" if exists else "❌"
        print(f"{status} {table}")
    
    print()
    print("SUMMARY:")
    print("-" * 40)
    print(f"Counties with data: {counties_with_data}/4")
    print(f"Total auctions: {total_auctions}")
    print()
    
    # Priority recommendations
    print("PRIORITY ANALYSIS:")
    print("-" * 40)
    
    counties_by_data = []
    for county in TARGET_COUNTIES:
        status = check_county_basic_status(county)
        if 'error' not in status:
            counties_by_data.append((status['name'], status['total_auctions'], status['has_data']))
    
    counties_by_data.sort(key=lambda x: x[1])  # Sort by auction count
    
    for name, auction_count, has_data in counties_by_data:
        if auction_count == 0:
            priority = "BOOTSTRAP NEEDED"
        elif auction_count < 1000:
            priority = "LOW DATA"
        else:
            priority = "ACTIVE"
        
        print(f"{name:12s} {auction_count:5d} auctions  {priority}")
    
    print()
    print("NEXT STEPS:")
    print("-" * 40)
    print("1. Apply SHARD-14 migration to ensure table structure")
    print("2. Check if counties with 0 auctions need data ingestion") 
    print("3. For counties with data, run Gold Standard evaluation")
    print("4. Focus on Letters B, I, J improvements for highest leverage")

if __name__ == "__main__":
    main()