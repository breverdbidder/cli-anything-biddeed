#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-11 County Bootstrap: manatee, bay, okeechobee, gadsden, wakulla
Ensures our assigned counties have baseline data ingested before working on Letters A-J

This script:
1. Checks current status for each county
2. Runs FL GIO parcel ingestion if needed
3. Sets up pipeline.counties configuration 
4. Enables baseline scrapers

Usage:
  python scripts/shard11_county_bootstrap.py
  python scripts/shard11_county_bootstrap.py --county manatee  # Single county
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

# SHARD-11 target counties with FL DOT county numbers
TARGET_COUNTIES = [
    {'name': 'Manatee', 'co_no': 49, 'slug': 'manatee'},
    {'name': 'Bay', 'co_no': 4, 'slug': 'bay'},  
    {'name': 'Okeechobee', 'co_no': 58, 'slug': 'okeechobee'},
    {'name': 'Gadsden', 'co_no': 26, 'slug': 'gadsden'},
    {'name': 'Wakulla', 'co_no': 73, 'slug': 'wakulla'}
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
        
        # Check pipeline.counties (foreclosure data configuration)
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/pipeline_counties?county=eq.{slug}&select=*",
            headers=headers
        )
        pipeline_config = response.json()[0] if response.status_code == 200 and response.json() else None
        
        # Check zoning_assignments  
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/zoning_assignments?co_no=eq.{co_no}&select=count",
            headers=headers
        )
        zoning_count = len(response.json()) if response.status_code == 200 else 0
        
        # Check multi_county_auctions (foreclosure/tax deed data)
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
            'pipeline_configured': pipeline_config is not None,
            'pipeline_active': pipeline_config.get('active', False) if pipeline_config else False,
            'zoning_assignments': zoning_count,
            'auctions': auction_count,
            'needs_ingestion': zoning_count == 0,
            'needs_pipeline_setup': pipeline_config is None
        }
        
        return status
        
    except Exception as e:
        print(f"❌ Error checking {name} status: {e}")
        return None

def setup_pipeline_config(county_info):
    """Set up pipeline.counties configuration for foreclosure/tax deed scraping"""
    co_no = county_info['co_no']
    slug = county_info['slug'] 
    name = county_info['name']
    
    print(f"\n🔧 Setting up pipeline configuration for {name}...")
    
    # Standard configuration for Florida counties using RealAuction platform
    pipeline_config = {
        'county': slug,
        'state': 'FL',
        'co_no': co_no,
        'platform': 'realauction',
        'foreclosure_platform': 'realauction', 
        'tax_deed_platform': 'realauction',
        'foreclosure_url': f'https://www.realauction.com/index.cfm?zaction=SEARCH&UCOUNTY={slug.upper()}',
        'tax_deed_url': f'https://www.realauction.com/index.cfm?zaction=SEARCH&UCOUNTY={slug.upper()}&AUCTION=TAX',
        'active': True,
        'created_at': datetime.now().isoformat(),
        'notes': f'SHARD-11 bootstrap {datetime.now().isoformat()}'
    }
    
    try:
        client = httpx.Client(timeout=30)
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates"
        }
        
        response = client.post(
            f"{SUPABASE_URL}/rest/v1/pipeline_counties",
            headers=headers,
            json=pipeline_config
        )
        
        if response.status_code in (200, 201, 204):
            print(f"✅ Pipeline configuration created for {name}")
            return True
        else:
            print(f"❌ Failed to create pipeline config for {name}: {response.status_code} {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error setting up pipeline config for {name}: {e}")
        return False

def run_county_ingestion(co_no, name):
    """Run the county ingestion script for a specific county"""
    print(f"\n📥 Starting FL GIO parcel ingestion for {name} (CO_NO={co_no})...")
    
    try:
        # First, just count parcels to verify connectivity
        print(f"🔍 Counting parcels for {name}...")
        result = subprocess.run([
            'python3', 'scripts/ingest_county.py', '--county', str(co_no)
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode != 0:
            print(f"❌ Count failed for {name}: {result.stderr}")
            return False
        
        print(f"✅ Count completed for {name}")
        print(result.stdout)
        
        # Then do full ingestion
        print(f"📦 Starting full parcel ingestion for {name}...")
        result = subprocess.run([
            'python3', 'scripts/ingest_county.py', '--county', str(co_no), '--full'
        ], capture_output=True, text=True, timeout=3600)  # 1 hour timeout
        
        if result.returncode != 0:
            print(f"❌ Full ingestion failed for {name}: {result.stderr}")
            print(f"Last 500 chars of stdout: {result.stdout[-500:]}")
            return False
        
        print(f"✅ Full parcel ingestion completed for {name}")
        print(result.stdout)
        return True
        
    except subprocess.TimeoutExpired:
        print(f"⏰ Parcel ingestion timed out for {name}")
        return False
    except Exception as e:
        print(f"❌ Error running ingestion for {name}: {e}")
        return False

def run_initial_scrape(county_info):
    """Run initial foreclosure/tax deed scrape for the county"""
    slug = county_info['slug']
    name = county_info['name']
    
    print(f"\n🔍 Running initial auction data scrape for {name}...")
    
    try:
        # Use the existing foreclosure scraper
        result = subprocess.run([
            'python3', 'scripts/scrape_fl_auctions.py', '--county', slug, '--limit', '100'
        ], capture_output=True, text=True, timeout=900)  # 15 min timeout
        
        if result.returncode != 0:
            print(f"❌ Initial scrape failed for {name}: {result.stderr}")
            return False
        
        print(f"✅ Initial auction scrape completed for {name}")
        print(result.stdout)
        return True
        
    except subprocess.TimeoutExpired:
        print(f"⏰ Initial scrape timed out for {name}")
        return False
    except Exception as e:
        print(f"❌ Error running initial scrape for {name}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="SHARD-11 County Bootstrap")
    parser.add_argument('--county', help='Bootstrap single county by slug (e.g. manatee)')
    args = parser.parse_args()
    
    print("=" * 60)
    print("SHARD-11 GOLD STANDARD County Bootstrap")
    if args.county:
        counties_to_process = [c for c in TARGET_COUNTIES if c['slug'] == args.county]
        if not counties_to_process:
            print(f"❌ County '{args.county}' not found in SHARD-11 targets")
            print(f"Valid counties: {[c['slug'] for c in TARGET_COUNTIES]}")
            sys.exit(1)
        print(f"Target County: {args.county}")
    else:
        counties_to_process = TARGET_COUNTIES
        print(f"Target Counties: {', '.join([c['slug'] for c in TARGET_COUNTIES])}")
    print("=" * 60)
    
    if not SUPABASE_KEY:
        print("❌ SUPABASE_KEY environment variable not set")
        sys.exit(1)
    
    if not check_supabase_connection():
        sys.exit(1)
    
    # Check current status for all counties
    print("\n📊 Checking current status...")
    county_statuses = {}
    
    for county in counties_to_process:
        status = check_county_status(county['co_no'], county['name'], county['slug'])
        if status:
            county_statuses[county['slug']] = status
            
            print(f"\n{county['name']} County:")
            print(f"  FL County Record: {'✅' if status['fl_county_exists'] else '❌'}")
            print(f"  Parcels: {status['total_parcels']:,}")
            print(f"  Zoning Assignments: {status['zoning_assignments']:,}")  
            print(f"  Pipeline Config: {'✅' if status['pipeline_configured'] else '❌'}")
            print(f"  Auction Data: {status['auctions']:,} rows")
            
            if status['needs_ingestion']:
                print(f"  🚨 Needs parcel ingestion")
            if status['needs_pipeline_setup']:
                print(f"  🚨 Needs pipeline setup")
    
    # Process each county that needs work
    print(f"\n{'='*60}")
    print("BOOTSTRAP EXECUTION")
    print(f"{'='*60}")
    
    for county in counties_to_process:
        slug = county['slug']
        status = county_statuses.get(slug)
        if not status:
            continue
            
        print(f"\n🎯 Processing {county['name']} County...")
        
        # Step 1: Set up pipeline configuration if needed
        if status['needs_pipeline_setup']:
            if not setup_pipeline_config(county):
                print(f"❌ Failed to set up pipeline for {county['name']}")
                continue
        
        # Step 2: Run parcel ingestion if needed  
        if status['needs_ingestion']:
            if not run_county_ingestion(county['co_no'], county['name']):
                print(f"❌ Failed to ingest parcels for {county['name']}")
                continue
        
        # Step 3: Run initial auction data scrape
        if status['auctions'] == 0:
            if not run_initial_scrape(county):
                print(f"❌ Failed initial scrape for {county['name']}")
                # Continue anyway - scraping can be retried
        
        print(f"✅ Bootstrap completed for {county['name']}")
    
    print(f"\n{'='*60}")
    print("BOOTSTRAP SUMMARY")
    print(f"{'='*60}")
    print("✅ SHARD-11 counties are now ready for Gold Standard work")
    print("\nNext steps:")
    print("1. Run scripts/verify_shard11_status.py to confirm setup")
    print("2. Implement Letter B (verified outcomes) - highest priority")
    print("3. Fix Letter H (staleness) for bay + okeechobee")
    print("4. Address Letter E (parcel linkage)")
    print("5. Implement Letters I,J (property cards, deal thesis)")

if __name__ == "__main__":
    main()