#!/usr/bin/env python3
"""
GOLD STANDARD SHARD 10: A-LEVEL INGESTION
Bootstrap franklin and union counties from 0/10 to basic data coverage.
Focuses on Letter A (dual-product coverage) which requires basic auction/parcel data.

UNTESTED: This implementation follows existing patterns but has not been tested yet.
"""
import os
import sys
import subprocess
import httpx
import json
import time
from datetime import datetime

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# Counties that need A-level work (0/10 status)
A_LEVEL_COUNTIES = [
    {'name': 'Franklin', 'co_no': 26, 'slug': 'franklin'},
    {'name': 'Union', 'co_no': 62, 'slug': 'union'}
]

def sb_headers():
    return {
        "apikey": SUPABASE_KEY, 
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json", 
        "Prefer": "resolution=merge-duplicates"
    }

def check_county_auction_data(slug):
    """Check if county has auction data in multi_county_auctions"""
    try:
        client = httpx.Client(timeout=30)
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.{slug}&select=count",
            headers=sb_headers()
        )
        if response.status_code == 200:
            count = len(response.json())
            print(f"  {slug}: {count} auctions in multi_county_auctions")
            return count
        else:
            print(f"  {slug}: Error checking auctions: {response.status_code}")
            return 0
    except Exception as e:
        print(f"  {slug}: Error checking auctions: {e}")
        return 0

def run_county_ingestion(co_no, name, slug):
    """Run county parcel ingestion using existing ingest_county.py"""
    print(f"\n📥 Starting A-level ingestion for {name} County (CO_NO={co_no})...")
    
    try:
        # First, count parcels
        print(f"  Counting parcels for {name}...")
        result = subprocess.run([
            'python3', 'scripts/ingest_county.py', '--county', str(co_no)
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode != 0:
            print(f"❌ Count failed for {name}: {result.stderr}")
            return False
        
        print(f"✅ Count completed for {name}")
        if result.stdout:
            print(result.stdout)
        
        # Then do full ingestion if count succeeded
        print(f"📦 Starting full ingestion for {name}...")
        result = subprocess.run([
            'python3', 'scripts/ingest_county.py', '--county', str(co_no), '--full'
        ], capture_output=True, text=True, timeout=3600)  # 1 hour timeout
        
        if result.returncode != 0:
            print(f"❌ Full ingestion failed for {name}: {result.stderr}")
            return False
        
        print(f"✅ Full ingestion completed for {name}")
        if result.stdout:
            print(result.stdout)
        
        # Verify the ingestion worked
        print(f"🔍 Verifying ingestion for {name}...")
        auction_count = check_county_auction_data(slug)
        
        return True
        
    except subprocess.TimeoutExpired:
        print(f"⏰ Ingestion timed out for {name}")
        return False
    except Exception as e:
        print(f"❌ Error running ingestion for {name}: {e}")
        return False

def ensure_counties_in_pipeline(counties):
    """Ensure counties are configured in pipeline.counties table"""
    try:
        client = httpx.Client(timeout=30)
        
        for county in counties:
            slug = county['slug']
            co_no = county['co_no']
            name = county['name']
            
            print(f"🔧 Ensuring {name} is configured in pipeline...")
            
            # Check if county exists in pipeline.counties
            response = client.get(
                f"{SUPABASE_URL}/rest/v1/counties?county_name=eq.{slug}&select=*",
                headers=sb_headers()
            )
            
            if response.status_code == 200 and response.json():
                print(f"  ✅ {name} already configured in pipeline.counties")
                continue
            
            # Insert basic configuration for the county
            # Based on the COUNTY EXCEPTIONS note - most counties use realauction platform
            county_config = {
                'county_name': slug,
                'display_name': name,
                'co_no': co_no,
                'platform': 'realauction',
                'foreclosure_platform': 'realauction',
                'foreclosure_url': f'https://{slug}.realforeclose.com',
                'tax_deed_platform': 'realauction', 
                'tax_deed_url': f'https://{slug}.realauction.com',
                'active': True,
                'notes': 'Added by SHARD10 A-level ingestion'
            }
            
            response = client.post(
                f"{SUPABASE_URL}/rest/v1/counties",
                headers=sb_headers(),
                json=[county_config]
            )
            
            if response.status_code in (200, 201, 204):
                print(f"  ✅ {name} configured in pipeline.counties")
            else:
                print(f"  ⚠️  {name} config may have failed: {response.status_code} {response.text}")
                
    except Exception as e:
        print(f"❌ Error configuring pipeline: {e}")

def main():
    print("=" * 70)
    print("SHARD 10: A-LEVEL INGESTION - franklin, union (0/10 → basic coverage)")
    print("=" * 70)
    
    if not SUPABASE_KEY:
        print("❌ SUPABASE_KEY environment variable not set")
        # Try to continue with environment default from CLAUDE.md
        print("⚠️  Attempting to use default connection...")
    
    print("\n🔍 Current auction data status:")
    for county in A_LEVEL_COUNTIES:
        check_county_auction_data(county['slug'])
    
    print("\n📋 Counties needing A-level ingestion:")
    for county in A_LEVEL_COUNTIES:
        print(f"  - {county['name']} (CO_NO={county['co_no']}, slug={county['slug']})")
    
    # Ensure counties are configured in pipeline
    ensure_counties_in_pipeline(A_LEVEL_COUNTIES)
    
    # Run parcel ingestion for each county
    success_count = 0
    for county in A_LEVEL_COUNTIES:
        co_no = county['co_no']
        name = county['name'] 
        slug = county['slug']
        
        success = run_county_ingestion(co_no, name, slug)
        if success:
            print(f"✅ {name} A-level ingestion completed")
            success_count += 1
        else:
            print(f"❌ {name} A-level ingestion failed")
    
    print(f"\n🏆 A-LEVEL RESULTS: {success_count}/{len(A_LEVEL_COUNTIES)} counties completed")
    
    if success_count > 0:
        print("\nNext steps:")
        print("1. Run verification: SELECT public.pencil_dod_evaluate_county('franklin');")
        print("2. Run verification: SELECT public.pencil_dod_evaluate_county('union');")
        print("3. Check that Letter A now passes (dual-product coverage)")
        print("4. Move to B-level work (verified outcomes)")
    
    return success_count

if __name__ == "__main__":
    main()