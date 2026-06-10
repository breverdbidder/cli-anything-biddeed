#!/usr/bin/env python3
"""
GOLD STANDARD County Bootstrap: indian_river, osceola, sarasota
Ensures our assigned counties have baseline data ingested before working on Letters G, I, J

Usage:
  python scripts/gold_standard_county_bootstrap.py
"""
import os
import sys
import subprocess
import httpx
from datetime import datetime

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# Target counties from fl_counties_manifest.yml
TARGET_COUNTIES = [
    {'name': 'Indian River', 'co_no': 41, 'slug': 'indian_river'},
    {'name': 'Osceola', 'co_no': 59, 'slug': 'osceola'},
    {'name': 'Sarasota', 'co_no': 68, 'slug': 'sarasota'}
]

def check_supabase_connection():
    """Verify we can connect to Supabase"""
    try:
        client = httpx.Client(timeout=30)
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        response = client.get(f"{SUPABASE_URL}/rest/v1/fl_counties?select=count&limit=1", headers=headers)
        response.raise_for_status()
        print("✅ Supabase connection verified")
        return True
    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")
        return False

def check_county_status(co_no, name, slug):
    """Check current ingestion status for a county"""
    try:
        client = httpx.Client(timeout=30)
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        # Check fl_counties
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/fl_counties?co_no=eq.{co_no}&select=*",
            headers=headers
        )
        fl_county = response.json()[0] if response.status_code == 200 and response.json() else None
        
        # Check zoning_assignments  
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/zoning_assignments?co_no=eq.{co_no}&select=count",
            headers=headers
        )
        zoning_count = len(response.json()) if response.status_code == 200 else 0
        
        # Check sample_properties
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/sample_properties?co_no=eq.{co_no}&select=count",
            headers=headers
        )
        sample_count = len(response.json()) if response.status_code == 200 else 0
        
        # Check multi_county_auctions
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.{slug}&select=count",
            headers=headers
        )
        auction_count = len(response.json()) if response.status_code == 200 else 0
        
        status = {
            'county': name,
            'co_no': co_no,
            'slug': slug,
            'fl_county_exists': fl_county is not None,
            'total_parcels': fl_county.get('total_parcels', 0) if fl_county else 0,
            'zoning_assignments': zoning_count,
            'sample_properties': sample_count,
            'auctions': auction_count,
            'needs_ingestion': zoning_count == 0
        }
        
        return status
        
    except Exception as e:
        print(f"❌ Error checking {name} status: {e}")
        return None

def run_county_ingestion(co_no, name):
    """Run the county ingestion script for a specific county"""
    print(f"\n📥 Starting ingestion for {name} (CO_NO={co_no})...")
    
    try:
        # First, just count parcels
        result = subprocess.run([
            'python3', 'scripts/ingest_county.py', '--county', str(co_no)
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode != 0:
            print(f"❌ Count failed for {name}: {result.stderr}")
            return False
        
        print(f"✅ Count completed for {name}")
        print(result.stdout)
        
        # Then do full ingestion
        print(f"📦 Starting full ingestion for {name}...")
        result = subprocess.run([
            'python3', 'scripts/ingest_county.py', '--county', str(co_no), '--full'
        ], capture_output=True, text=True, timeout=3600)  # 1 hour timeout
        
        if result.returncode != 0:
            print(f"❌ Full ingestion failed for {name}: {result.stderr}")
            return False
        
        print(f"✅ Full ingestion completed for {name}")
        print(result.stdout)
        return True
        
    except subprocess.TimeoutExpired:
        print(f"⏰ Ingestion timed out for {name}")
        return False
    except Exception as e:
        print(f"❌ Error running ingestion for {name}: {e}")
        return False

def main():
    print("=" * 60)
    print("GOLD STANDARD County Bootstrap")
    print("Target Counties: indian_river, osceola, sarasota")
    print("=" * 60)
    
    if not SUPABASE_KEY:
        print("❌ SUPABASE_KEY environment variable not set")
        sys.exit(1)
    
    if not check_supabase_connection():
        sys.exit(1)
    
    print("\n🔍 Checking current county status...")
    
    counties_status = []
    for county in TARGET_COUNTIES:
        status = check_county_status(county['co_no'], county['name'], county['slug'])
        if status:
            counties_status.append(status)
            print(f"  {status['county']:15s} | "
                  f"Parcels: {status['total_parcels']:>8,} | "
                  f"Zoning: {status['zoning_assignments']:>6} | "
                  f"Samples: {status['sample_properties']:>6} | "
                  f"Auctions: {status['auctions']:>5} | "
                  f"Status: {'NEEDS_INGESTION' if status['needs_ingestion'] else 'READY'}")
    
    # Identify counties that need ingestion
    counties_to_ingest = [s for s in counties_status if s['needs_ingestion']]
    
    if not counties_to_ingest:
        print("\n✅ All target counties already have data ingested!")
        print("\nNext steps:")
        print("  1. Run verified outcomes scraper: python scripts/scrape_verified_outcomes.py --all-counties")
        print("  2. Enable zoning KPI views for Letter G")
        print("  3. Work on property card completion for Letter I")
        return
    
    print(f"\n📋 Counties needing ingestion: {len(counties_to_ingest)}")
    for county in counties_to_ingest:
        print(f"  - {county['county']} (CO_NO={county['co_no']})")
    
    # Run ingestion for counties that need it
    for county in counties_to_ingest:
        co_no = county['co_no']
        name = county['county']
        
        success = run_county_ingestion(co_no, name)
        if success:
            print(f"✅ {name} ingestion completed successfully")
        else:
            print(f"❌ {name} ingestion failed - manual intervention required")
    
    print("\n🏆 County bootstrap complete!")
    print("\nVerify status with:")
    print("  python test_db_connection.py")

if __name__ == "__main__":
    main()