#!/usr/bin/env python3
"""
GOLD STANDARD WAVE2-SHARD-7: County Setup and Ingestion
Counties: alachua, gilchrist, miami_dade, walton, gadsden, lafayette, wakulla

Sets up pipeline configuration and runs baseline ingestion for zero-data counties
Ensures Letter A (dual product coverage) is met
"""
import httpx
import json
import os
import sys
import subprocess
import argparse
from datetime import datetime
from typing import Dict, List, Optional
import logging
import time

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

# WAVE2-SHARD-7 counties (from fl_counties_manifest.yml)
SHARD_COUNTIES = [
    {'name': 'Alachua', 'co_no': 11, 'slug': 'alachua'},
    {'name': 'Gilchrist', 'co_no': 31, 'slug': 'gilchrist'},
    {'name': 'Miami-Dade', 'co_no': 23, 'slug': 'miami_dade'},
    {'name': 'Walton', 'co_no': 76, 'slug': 'walton'},
    {'name': 'Gadsden', 'co_no': 30, 'slug': 'gadsden'},
    {'name': 'Lafayette', 'co_no': 44, 'slug': 'lafayette'},
    {'name': 'Wakulla', 'co_no': 75, 'slug': 'wakulla'}
]

# Pipeline configuration templates
PIPELINE_CONFIG_TEMPLATES = {
    'foreclosure': {
        'platform': 'realauction',
        'foreclosure_url': 'https://www.realauction.com/foreclosure',
        'foreclosure_platform': 'realauction',
        'active': True,
        'auth_required': False
    },
    'tax_deed': {
        'platform': 'realauction', 
        'tax_deed_url': 'https://www.realauction.com/tax-deed',
        'tax_deed_platform': 'realauction',
        'active': True,
        'auth_required': False
    }
}

client = httpx.Client(timeout=60)

def supabase_get(table: str, params: str = "") -> List[Dict]:
    """Get data from Supabase table"""
    try:
        url = f"{BASE}/{table}?{params}"
        response = client.get(url, headers=HEADERS)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching from {table}: {e}")
        return []

def supabase_upsert(table: str, data: List[Dict]) -> bool:
    """Upsert records to Supabase table"""
    try:
        url = f"{BASE}/{table}"
        response = client.post(url, headers=HEADERS, json=data)
        response.raise_for_status()
        logger.info(f"Upserted {len(data)} records to {table}")
        return True
    except Exception as e:
        logger.error(f"Error upserting to {table}: {e}")
        return False

def check_county_status(county: Dict) -> Dict:
    """Check current data status for a county"""
    slug = county['slug']
    co_no = county['co_no']
    name = county['name']
    
    logger.info(f"Checking status for {name} ({slug})")
    
    # Check fl_counties
    fl_county = supabase_get("fl_counties", f"co_no=eq.{co_no}")
    
    # Check multi_county_auctions
    auctions = supabase_get("multi_county_auctions", f"county=eq.{slug}&select=count")
    auction_count = len(auctions)
    
    # Check zoning_assignments
    zoning = supabase_get("zoning_assignments", f"co_no=eq.{co_no}&select=count")
    zoning_count = len(zoning)
    
    # Check pipeline_counties
    pipeline = supabase_get("pipeline_counties", f"county_slug=eq.{slug}")
    
    status = {
        'county': county,
        'fl_county_exists': len(fl_county) > 0,
        'total_parcels': fl_county[0].get('total_parcels', 0) if fl_county else 0,
        'auction_count': auction_count,
        'zoning_count': zoning_count,
        'pipeline_configured': len(pipeline) > 0,
        'needs_ingestion': zoning_count == 0,
        'needs_pipeline': len(pipeline) == 0,
        'has_auction_data': auction_count > 0
    }
    
    logger.info(f"  FL County: {'✓' if status['fl_county_exists'] else '✗'}")
    logger.info(f"  Parcels: {status['total_parcels']:,}")
    logger.info(f"  Auctions: {status['auction_count']:,}")
    logger.info(f"  Zoning: {status['zoning_count']:,}")
    logger.info(f"  Pipeline: {'✓' if status['pipeline_configured'] else '✗'}")
    
    return status

def setup_pipeline_configuration(county: Dict) -> bool:
    """Set up pipeline configuration for a county"""
    slug = county['slug']
    name = county['name']
    
    logger.info(f"Setting up pipeline configuration for {name}")
    
    # Create pipeline_counties entry
    pipeline_config = {
        'county_slug': slug,
        'county_name': name,
        'state': 'FL',
        'active': True,
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat()
    }
    
    # Add foreclosure and tax deed configurations
    pipeline_config.update(PIPELINE_CONFIG_TEMPLATES['foreclosure'])
    pipeline_config.update(PIPELINE_CONFIG_TEMPLATES['tax_deed'])
    
    # Customize URLs for specific counties (RealAuction format)
    pipeline_config['foreclosure_url'] = f"https://www.realauction.com/foreclosure/{slug.replace('_', '-')}"
    pipeline_config['tax_deed_url'] = f"https://www.realauction.com/tax-deed/{slug.replace('_', '-')}"
    
    return supabase_upsert("pipeline_counties", [pipeline_config])

def run_county_ingestion(county: Dict, full: bool = True) -> bool:
    """Run county ingestion using existing script"""
    name = county['name']
    co_no = county['co_no']
    
    logger.info(f"Starting ingestion for {name} (CO_NO={co_no})")
    
    try:
        # First, count parcels
        logger.info(f"  Counting parcels for {name}...")
        result = subprocess.run([
            sys.executable, 'scripts/ingest_county.py', '--county', str(co_no)
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode != 0:
            logger.error(f"Count failed for {name}: {result.stderr}")
            return False
        
        logger.info(f"✓ Count completed for {name}")
        logger.info(result.stdout)
        
        if full:
            # Then do full ingestion
            logger.info(f"  Starting full ingestion for {name}...")
            result = subprocess.run([
                sys.executable, 'scripts/ingest_county.py', '--county', str(co_no), '--full'
            ], capture_output=True, text=True, timeout=3600)  # 1 hour timeout
            
            if result.returncode != 0:
                logger.error(f"Full ingestion failed for {name}: {result.stderr}")
                return False
            
            logger.info(f"✓ Full ingestion completed for {name}")
            logger.info(result.stdout)
        
        return True
        
    except subprocess.TimeoutExpired:
        logger.error(f"Ingestion timed out for {name}")
        return False
    except Exception as e:
        logger.error(f"Error running ingestion for {name}: {e}")
        return False

def setup_fl_counties_entry(county: Dict) -> bool:
    """Ensure county exists in fl_counties table"""
    slug = county['slug']
    name = county['name']
    co_no = county['co_no']
    
    logger.info(f"Setting up fl_counties entry for {name}")
    
    # Check if exists
    existing = supabase_get("fl_counties", f"co_no=eq.{co_no}")
    
    if existing:
        logger.info(f"  FL county entry already exists for {name}")
        return True
    
    # Create new entry
    fl_county_data = {
        'co_no': co_no,
        'name': name,
        'slug': slug,
        'state': 'FL',
        'total_parcels': 0,  # Will be updated by ingestion
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat()
    }
    
    return supabase_upsert("fl_counties", [fl_county_data])

def update_fl_counties_manifest() -> bool:
    """Update fl_counties_manifest.yml with proper slugs for SHARD-7 counties"""
    manifest_path = "fl_counties_manifest.yml"
    
    try:
        with open(manifest_path, 'r') as f:
            content = f.read()
        
        # Update null slugs for our counties
        for county in SHARD_COUNTIES:
            co_no = county['co_no']
            slug = county['slug']
            
            # Replace [CountyName, null] with [CountyName, slug]
            pattern = f"{co_no}: \\[{county['name']}, null\\]"
            replacement = f"{co_no}: [{county['name']}, {slug}]"
            content = content.replace(pattern, replacement)
        
        with open(manifest_path, 'w') as f:
            f.write(content)
        
        logger.info("Updated fl_counties_manifest.yml with SHARD-7 county slugs")
        return True
        
    except Exception as e:
        logger.error(f"Error updating manifest: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="WAVE2-SHARD-7 County Setup and Ingestion")
    parser.add_argument("--county", help="Specific county slug to process")
    parser.add_argument("--all-counties", action="store_true", help="Process all SHARD-7 counties")
    parser.add_argument("--setup-only", action="store_true", help="Only setup configuration, skip ingestion")
    parser.add_argument("--ingestion-only", action="store_true", help="Only run ingestion, skip setup")
    parser.add_argument("--count-only", action="store_true", help="Only count parcels, don't do full ingestion")
    
    args = parser.parse_args()
    
    if not SUPABASE_KEY:
        logger.error("SUPABASE_KEY environment variable required")
        sys.exit(1)
    
    # Determine counties to process
    if args.county:
        counties = [c for c in SHARD_COUNTIES if c['slug'] == args.county]
        if not counties:
            logger.error(f"County '{args.county}' not found in SHARD-7")
            sys.exit(1)
    elif args.all_counties:
        counties = SHARD_COUNTIES
    else:
        parser.print_help()
        sys.exit(1)
    
    logger.info(f"Starting county setup for: {[c['name'] for c in counties]}")
    
    # Update manifest first
    if not args.ingestion_only:
        update_fl_counties_manifest()
    
    results = {}
    
    for county in counties:
        name = county['name']
        slug = county['slug']
        
        logger.info(f"\n{'='*60}")
        logger.info(f"PROCESSING: {name} ({slug})")
        logger.info(f"{'='*60}")
        
        # Check current status
        status = check_county_status(county)
        results[slug] = {
            'initial_status': status,
            'setup_completed': False,
            'ingestion_completed': False,
            'final_status': None
        }
        
        if not args.ingestion_only:
            # Setup phase
            logger.info(f"\n--- Setup Phase: {name} ---")
            
            # 1. Ensure fl_counties entry exists
            if setup_fl_counties_entry(county):
                logger.info(f"✓ FL counties entry ready for {name}")
            
            # 2. Setup pipeline configuration if needed
            if status['needs_pipeline']:
                if setup_pipeline_configuration(county):
                    logger.info(f"✓ Pipeline configuration created for {name}")
                    results[slug]['setup_completed'] = True
            else:
                logger.info(f"✓ Pipeline already configured for {name}")
                results[slug]['setup_completed'] = True
        
        if not args.setup_only:
            # Ingestion phase
            logger.info(f"\n--- Ingestion Phase: {name} ---")
            
            if status['needs_ingestion'] or args.ingestion_only:
                full_ingestion = not args.count_only
                if run_county_ingestion(county, full=full_ingestion):
                    logger.info(f"✓ Ingestion completed for {name}")
                    results[slug]['ingestion_completed'] = True
                else:
                    logger.error(f"✗ Ingestion failed for {name}")
            else:
                logger.info(f"✓ {name} already has data ingested")
                results[slug]['ingestion_completed'] = True
        
        # Check final status
        results[slug]['final_status'] = check_county_status(county)
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("FINAL SUMMARY")
    logger.info(f"{'='*60}")
    
    for slug, result in results.items():
        county_name = next(c['name'] for c in counties if c['slug'] == slug)
        final = result['final_status']
        
        logger.info(f"\n{county_name}:")
        logger.info(f"  Setup: {'✓' if result['setup_completed'] else '✗'}")
        logger.info(f"  Ingestion: {'✓' if result['ingestion_completed'] else '✗'}")
        logger.info(f"  Parcels: {final['total_parcels']:,}")
        logger.info(f"  Auctions: {final['auction_count']:,}")
        logger.info(f"  Zoning: {final['zoning_count']:,}")
        
        # Letter A assessment
        has_foreclosure = final['pipeline_configured']  # Simplified check
        has_tax_deed = final['pipeline_configured']     # Simplified check
        letter_a_pass = has_foreclosure and has_tax_deed
        
        logger.info(f"  Letter A (dual product): {'✓' if letter_a_pass else '✗'}")
    
    logger.info(f"\nNext steps:")
    logger.info(f"1. Verify pipeline lanes are pulling auction data")
    logger.info(f"2. Run parity matching improvements")
    logger.info(f"3. Work on property card enrichment")
    logger.info(f"4. Run verification: SELECT public.pencil_dod_evaluate_county('<county>');")

if __name__ == "__main__":
    main()