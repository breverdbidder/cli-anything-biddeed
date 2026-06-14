#!/usr/bin/env python3
"""
SHARD-7 County Data Ingestion: columbia and madison baseline data
Uses the existing ingest_county.py to populate FL GIO baseline data

This handles the data ingestion part of criterion A setup:
- FL GIO parcel data ingestion 
- DOR_UC crosswalk for baseline zoning
- Populates multi_county_auctions table foundation

Usage:
  python scripts/shard7_ingest_counties.py --county columbia
  python scripts/shard7_ingest_counties.py --county madison  
  python scripts/shard7_ingest_counties.py --all
"""
import os
import sys
import subprocess
import time
from datetime import datetime
import argparse

# County mappings for shard 7
ZERO_STATE_COUNTIES = {
    'columbia': {'co_no': 12, 'name': 'Columbia'},
    'madison': {'co_no': 40, 'name': 'Madison'}
}

def log_with_timestamp(message):
    """Add timestamp to all log messages"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")

def run_county_count(co_no, name):
    """Run county parcel count to verify FL GIO access"""
    log_with_timestamp(f"📊 Counting parcels for {name} (CO_NO={co_no})...")
    
    try:
        result = subprocess.run([
            'python3', 'scripts/ingest_county.py', '--county', str(co_no)
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            log_with_timestamp(f"✅ Count completed for {name}")
            # Extract count from output if possible
            output_lines = result.stdout.strip().split('\n')
            for line in output_lines:
                if 'parcels' in line.lower() or 'count' in line.lower():
                    log_with_timestamp(f"   {line.strip()}")
            return True
        else:
            log_with_timestamp(f"❌ Count failed for {name}")
            log_with_timestamp(f"   Error: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        log_with_timestamp(f"⏰ Count timed out for {name}")
        return False
    except Exception as e:
        log_with_timestamp(f"❌ Error running count for {name}: {e}")
        return False

def run_county_ingestion(co_no, name):
    """Run full county data ingestion"""
    log_with_timestamp(f"📥 Starting full ingestion for {name} (CO_NO={co_no})...")
    log_with_timestamp(f"   Expected: ~30-60 minutes for complete ingestion")
    
    try:
        # Run with extended timeout for full ingestion
        start_time = time.time()
        
        result = subprocess.run([
            'python3', 'scripts/ingest_county.py', '--county', str(co_no), '--full'
        ], capture_output=True, text=True, timeout=3600)  # 1 hour timeout
        
        elapsed_time = time.time() - start_time
        
        if result.returncode == 0:
            log_with_timestamp(f"✅ Full ingestion completed for {name}")
            log_with_timestamp(f"   Duration: {elapsed_time/60:.1f} minutes")
            
            # Show key results from output
            output_lines = result.stdout.strip().split('\n')
            for line in output_lines[-10:]:  # Show last 10 lines
                if line.strip():
                    log_with_timestamp(f"   {line.strip()}")
            return True
        else:
            log_with_timestamp(f"❌ Full ingestion failed for {name}")
            log_with_timestamp(f"   Duration: {elapsed_time/60:.1f} minutes")
            log_with_timestamp(f"   Error: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        log_with_timestamp(f"⏰ Ingestion timed out for {name} (>1 hour)")
        return False
    except Exception as e:
        log_with_timestamp(f"❌ Error running ingestion for {name}: {e}")
        return False

def ingest_county(county_slug):
    """Run complete ingestion process for a county"""
    if county_slug not in ZERO_STATE_COUNTIES:
        log_with_timestamp(f"❌ Unknown county: {county_slug}")
        log_with_timestamp(f"Available counties: {', '.join(ZERO_STATE_COUNTIES.keys())}")
        return False
    
    county_info = ZERO_STATE_COUNTIES[county_slug]
    co_no = county_info['co_no']
    name = county_info['name']
    
    log_with_timestamp(f"🎯 Starting ingestion for {name} County ({county_slug})")
    log_with_timestamp(f"   CO_NO: {co_no}")
    log_with_timestamp(f"   Target: FL GIO baseline for criterion A")
    
    # Step 1: Count parcels first 
    log_with_timestamp(f"\n📋 STEP 1: Parcel count verification")
    count_success = run_county_count(co_no, name)
    if not count_success:
        log_with_timestamp(f"❌ Parcel count failed - cannot proceed with ingestion")
        return False
    
    # Step 2: Full ingestion
    log_with_timestamp(f"\n📋 STEP 2: Full data ingestion") 
    ingestion_success = run_county_ingestion(co_no, name)
    if not ingestion_success:
        log_with_timestamp(f"❌ Full ingestion failed")
        return False
    
    log_with_timestamp(f"✅ {name} County ingestion complete")
    log_with_timestamp(f"   Next: Verify data in multi_county_auctions table")
    
    return True

def main():
    parser = argparse.ArgumentParser(description='Ingest county data for Gold Standard zero-state counties')
    parser.add_argument('--county', help='County to ingest (columbia, madison)')
    parser.add_argument('--all', action='store_true', help='Ingest all zero-state counties')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without executing')
    
    args = parser.parse_args()
    
    log_with_timestamp("=" * 70)
    log_with_timestamp("SHARD-7 COUNTY INGESTION: FL GIO Baseline Data")
    log_with_timestamp("=" * 70)
    
    counties_to_ingest = []
    if args.all:
        counties_to_ingest = list(ZERO_STATE_COUNTIES.keys())
    elif args.county:
        counties_to_ingest = [args.county.lower()]
    else:
        log_with_timestamp("❌ Must specify --county or --all")
        sys.exit(1)
    
    log_with_timestamp(f"📋 Counties to ingest: {', '.join(counties_to_ingest)}")
    
    if args.dry_run:
        log_with_timestamp("🔍 DRY RUN - showing what would be executed:")
        for county_slug in counties_to_ingest:
            county_info = ZERO_STATE_COUNTIES[county_slug]
            log_with_timestamp(f"  {county_info['name']}: python3 scripts/ingest_county.py --county {county_info['co_no']} --full")
        return
    
    # Estimate total time
    total_estimated_minutes = len(counties_to_ingest) * 45  # ~45 min per county
    log_with_timestamp(f"⏱️  Estimated total time: {total_estimated_minutes} minutes")
    
    success_count = 0
    start_time = time.time()
    
    for i, county_slug in enumerate(counties_to_ingest, 1):
        log_with_timestamp(f"\n" + "=" * 50)
        log_with_timestamp(f"COUNTY {i}/{len(counties_to_ingest)}: {county_slug.upper()}")
        log_with_timestamp(f"=" * 50)
        
        success = ingest_county(county_slug)
        if success:
            success_count += 1
        
        # Show progress
        elapsed_minutes = (time.time() - start_time) / 60
        log_with_timestamp(f"\n⏱️  Progress: {i}/{len(counties_to_ingest)} counties | "
                          f"Elapsed: {elapsed_minutes:.1f} min | "
                          f"Success: {success_count}/{i}")
    
    total_elapsed = (time.time() - start_time) / 60
    log_with_timestamp(f"\n🏆 Ingestion complete: {success_count}/{len(counties_to_ingest)} counties")
    log_with_timestamp(f"   Total time: {total_elapsed:.1f} minutes")
    
    if success_count > 0:
        log_with_timestamp(f"\n📋 Next steps:")
        log_with_timestamp(f"  1. Verify data in database tables")
        log_with_timestamp(f"  2. Configure pipeline.counties for dual-product scraping") 
        log_with_timestamp(f"  3. Run pencil_dod_evaluate_county() to check criterion A")

if __name__ == "__main__":
    main()