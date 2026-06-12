#!/usr/bin/env python3
"""
SHARD-14 County Bootstrap: osceola, bay, okeechobee, hamilton
Ensures SHARD-14 counties have baseline data ingested before Gold Standard work

Usage:
  python scripts/shard14_county_bootstrap.py
  python scripts/shard14_county_bootstrap.py --county hamilton
"""
import os
import sys
import subprocess
import httpx
import argparse
from datetime import datetime

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# SHARD-14 target counties (with correct co_no from fl_counties_manifest.yml)
TARGET_COUNTIES = [
    {'name': 'Osceola', 'co_no': 59, 'slug': 'osceola'},
    {'name': 'Bay', 'co_no': 13, 'slug': 'bay'},
    {'name': 'Okeechobee', 'co_no': 57, 'slug': 'okeechobee'},  
    {'name': 'Hamilton', 'co_no': 34, 'slug': 'hamilton'}
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
        
        # Check if county slug exists
        if not fl_county or fl_county.get('slug') != slug:
            print(f"⚠️ County {name} (co_no={co_no}) not properly set up in fl_counties")
            print(f"   Expected slug: {slug}, Actual: {fl_county.get('slug') if fl_county else 'NOT FOUND'}")
        
        # Check zoning_assignments (primary indicator of ingestion)
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
            'slug_correct': fl_county and fl_county.get('slug') == slug,
            'total_parcels': fl_county.get('total_parcels', 0) if fl_county else 0,
            'zoning_assignments': zoning_count,
            'sample_properties': sample_count,
            'auctions': auction_count,
            'needs_ingestion': zoning_count == 0,
            'needs_auction_data': auction_count == 0,
            'bootstrap_priority': 'HIGH' if auction_count == 0 else 'LOW'
        }
        
        return status
        
    except Exception as e:
        print(f"❌ Error checking {name} status: {e}")
        return None

def run_county_ingestion(co_no, name):
    """Run the county ingestion script for a specific county"""
    print(f"\n📥 Starting ingestion for {name} (CO_NO={co_no})...")
    
    try:
        # First, just count parcels to verify connectivity
        print(f"🔍 Checking parcel count for {name}...")
        result = subprocess.run([
            'python3', 'scripts/ingest_county.py', '--county', str(co_no)
        ], capture_output=True, text=True, timeout=300, cwd='/home/runner/work/cli-anything-biddeed/cli-anything-biddeed')
        
        if result.returncode != 0:
            print(f"❌ Count check failed for {name}: {result.stderr}")
            return False
        
        print(f"✅ Count completed for {name}")
        print(result.stdout)
        
        # Then do full ingestion
        print(f"📦 Starting full ingestion for {name}...")
        result = subprocess.run([
            'python3', 'scripts/ingest_county.py', '--county', str(co_no), '--full'
        ], capture_output=True, text=True, timeout=3600, cwd='/home/runner/work/cli-anything-biddeed/cli-anything-biddeed')
        
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

def setup_auction_data_pipeline(county_slug):
    """Set up auction data pipeline for a county that needs it"""
    print(f"\n🔗 Setting up auction data pipeline for {county_slug}...")
    
    # This would normally involve:
    # 1. Configuring the county in pipeline.counties table
    # 2. Setting up scraper endpoints 
    # 3. Running initial auction data scrape
    
    print(f"⚠️ Auction data setup for {county_slug} requires manual configuration")
    print(f"   Steps needed:")
    print(f"   1. Add {county_slug} to pipeline.counties with appropriate endpoints")
    print(f"   2. Configure RealAuction or alternative scraper source")
    print(f"   3. Run initial historical data scrape")
    
    return False  # Manual intervention needed

def main():
    parser = argparse.ArgumentParser(description='SHARD-14 County Bootstrap')
    parser.add_argument('--county', help='Bootstrap specific county only (slug)')
    args = parser.parse_args()
    
    print("=" * 60)
    print("SHARD-14 COUNTY BOOTSTRAP")
    print("Target Counties: osceola, bay, okeechobee, hamilton")
    print("=" * 60)
    
    if not SUPABASE_KEY:
        print("❌ SUPABASE_KEY environment variable not set")
        sys.exit(1)
    
    if not check_supabase_connection():
        sys.exit(1)
    
    # Filter counties if specific one requested
    target_counties = TARGET_COUNTIES
    if args.county:
        target_counties = [c for c in TARGET_COUNTIES if c['slug'] == args.county]
        if not target_counties:
            print(f"❌ County '{args.county}' not found in SHARD-14")
            sys.exit(1)
    
    print(f"\n🔍 Checking status of {len(target_counties)} counties...")
    
    counties_status = []
    for county in target_counties:
        status = check_county_status(county['co_no'], county['name'], county['slug'])
        if status:
            counties_status.append(status)
            print(f"  {status['county']:12s} | "
                  f"Setup: {'✅' if status['slug_correct'] else '❌'} | "
                  f"Parcels: {status['total_parcels']:>8,} | "
                  f"Zoning: {status['zoning_assignments']:>6} | "
                  f"Auctions: {status['auctions']:>5} | "
                  f"Priority: {status['bootstrap_priority']}")
    
    # Identify counties that need work
    counties_needing_ingestion = [s for s in counties_status if s['needs_ingestion']]
    counties_needing_auctions = [s for s in counties_status if s['needs_auction_data']]
    
    print(f"\n📊 BOOTSTRAP ANALYSIS:")
    print(f"Counties needing parcel ingestion: {len(counties_needing_ingestion)}")
    print(f"Counties needing auction data: {len(counties_needing_auctions)}")
    
    if not counties_needing_ingestion and not counties_needing_auctions:
        print("\n✅ All SHARD-14 counties have basic data!")
        print("\nReady for Gold Standard Letter improvements:")
        print("  B: Run verified outcomes scrapers")
        print("  I: Property card enrichment")
        print("  J: Deal thesis pipeline")
        return
    
    # Handle parcel ingestion first (higher priority)
    if counties_needing_ingestion:
        print(f"\n🚀 PARCEL INGESTION NEEDED:")
        for county in counties_needing_ingestion:
            print(f"  - {county['county']} (CO_NO={county['co_no']})")
        
        for county in counties_needing_ingestion:
            co_no = county['co_no']
            name = county['county']
            
            success = run_county_ingestion(co_no, name)
            if success:
                print(f"✅ {name} parcel ingestion completed")
            else:
                print(f"❌ {name} parcel ingestion failed")
    
    # Handle auction data setup
    if counties_needing_auctions:
        print(f"\n📈 AUCTION DATA SETUP NEEDED:")
        for county in counties_needing_auctions:
            print(f"  - {county['county']} ({county['slug']}) - {county['bootstrap_priority']} priority")
        
        print(f"\n⚠️ Auction data setup requires manual configuration for new counties")
        print(f"For Hamilton county specifically:")
        print(f"  1. Check if Hamilton County has online auction data")
        print(f"  2. Configure appropriate scraper endpoint")
        print(f"  3. May need manual data entry if no online source")
    
    print(f"\n🎯 NEXT STEPS FOR GOLD STANDARD:")
    print(f"1. Complete any failed ingestions manually")
    print(f"2. Set up auction data sources for 0-auction counties")
    print(f"3. Focus on Letters B, I, J for counties with existing data")

if __name__ == "__main__":
    main()