#!/usr/bin/env python3
"""
GOLD STANDARD WAVE2-SHARD-1 Complete Pipeline
Run ingestion for all assigned counties: st_johns, baker, hendry, nassau, bradford, glades, levy

This script executes the GOLD STANDARD canon A-J pipeline for all SHARD-1 counties:
A. Dual-product coverage (foreclosures + tax deeds)
B. Verified INDEPENDENT outcomes >=95% of closed sales
C-J. Other gold standard metrics

Following CLAUDE.md SHIP-TO-MAIN mandate and autonomous operation principles.
"""
import os, sys, time
import subprocess
from datetime import datetime, timezone

# SHARD-1 assigned counties 
SHARD1_COUNTIES = ['st_johns', 'baker', 'hendry', 'nassau', 'bradford', 'glades', 'levy']

def log(msg):
    timestamp = datetime.now(timezone.utc).strftime('%H:%M:%S')
    print(f"[{timestamp}] {msg}")

def run_command(cmd, description):
    """Execute command and capture output"""
    log(f"Running: {description}")
    log(f"Command: {cmd}")
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            log(f"✅ SUCCESS: {description}")
            if result.stdout.strip():
                log(f"Output: {result.stdout.strip()}")
            return True
        else:
            log(f"❌ FAILED: {description}")
            log(f"Error: {result.stderr.strip()}")
            return False
    except subprocess.TimeoutExpired:
        log(f"⏱️  TIMEOUT: {description} (300s)")
        return False
    except Exception as e:
        log(f"❌ ERROR: {description} - {e}")
        return False

def main():
    log("=== GOLD STANDARD WAVE2-SHARD-1 PIPELINE START ===")
    log(f"Counties: {', '.join(SHARD1_COUNTIES)}")
    
    # Phase 1: Run foreclosure scraping for all counties
    log("\n=== Phase 1: Foreclosure Data Collection ===")
    for county in SHARD1_COUNTIES:
        success = run_command(
            f"python scripts/cairn_multi_county_scraper.py --county {county} --limit 100",
            f"Scrape foreclosure data for {county}"
        )
        if success:
            log(f"✅ {county} foreclosure scraping completed")
        else:
            log(f"❌ {county} foreclosure scraping failed")
        time.sleep(2)  # Rate limiting
    
    # Phase 2: Run parcel ingestion for counties with zero data  
    log("\n=== Phase 2: Parcel Ingestion (bradford, glades, levy) ===")
    zero_data_counties = ['bradford', 'glades', 'levy']  # From issue: 0/10 scores
    
    for county in zero_data_counties:
        # First get county co_no from fl_counties table
        success = run_command(
            f"python scripts/ingest_county.py --county {county}",
            f"Count parcels for {county}"
        )
        if success:
            # Run full ingestion
            success = run_command(
                f"python scripts/ingest_county.py --county {county} --full",
                f"Full parcel ingestion for {county}"  
            )
            if success:
                log(f"✅ {county} parcel ingestion completed")
            else:
                log(f"❌ {county} parcel ingestion failed")
        time.sleep(5)  # Longer delay for heavy operations
    
    # Phase 3: Evaluate all counties
    log("\n=== Phase 3: County Evaluation ===")
    success = run_command(
        "python test_shard1_counties.py",
        "Evaluate all SHARD-1 counties"
    )
    
    log("\n=== SHARD-1 PIPELINE COMPLETE ===")

if __name__ == "__main__":
    main()