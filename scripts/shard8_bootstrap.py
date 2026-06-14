#!/usr/bin/env python3
"""
SHARD-8 Bootstrap Script
Bootstrap counties with 0/10 scores: desoto (24) and monroe (54)
Then work on secondary targets: hillsborough (39), bay (13), nassau (55)
"""
import os
import sys
import subprocess
import time
from datetime import datetime

# County mappings from fl_counties_manifest.yml
COUNTY_MAP = {
    'desoto': 24,
    'monroe': 54,
    'hillsborough': 39,  
    'bay': 13,
    'nassau': 55
}

# Bootstrap targets (0/10 scores)
BOOTSTRAP_COUNTIES = ['desoto', 'monroe']

def run_command(cmd, description, timeout=3600):
    """Run a command with timeout and error handling"""
    print(f"\n🔄 {description}")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        start_time = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        duration = time.time() - start_time
        
        if result.returncode == 0:
            print(f"✅ Success ({duration:.1f}s)")
            if result.stdout:
                print(f"Output: {result.stdout[:500]}...")
            return True
        else:
            print(f"❌ Failed ({duration:.1f}s)")
            print(f"Error: {result.stderr[:500]}...")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"⏰ Timeout after {timeout}s")
        return False
    except Exception as e:
        print(f"💥 Exception: {e}")
        return False

def bootstrap_county(county_name):
    """Bootstrap a county from 0/10 to basic ingestion"""
    co_no = COUNTY_MAP[county_name]
    print(f"\n{'=' * 50}")
    print(f"BOOTSTRAPPING {county_name.upper()} (CO_NO={co_no})")
    print(f"{'=' * 50}")
    
    # Step 1: Count parcels
    if not run_command(
        ['python3', 'scripts/ingest_county.py', '--county', str(co_no)],
        f"Count parcels for {county_name}",
        timeout=300
    ):
        return False
    
    # Step 2: Full ingestion
    if not run_command(
        ['python3', 'scripts/ingest_county.py', '--county', str(co_no), '--full'],
        f"Full ingestion for {county_name}",
        timeout=3600  # 1 hour for full ingestion
    ):
        return False
    
    print(f"✅ {county_name.upper()} bootstrap complete!")
    return True

def main():
    print("=" * 60)
    print("SHARD-8 COUNTY BOOTSTRAP")
    print("Primary targets: desoto (CO_NO=24), monroe (CO_NO=54)")
    print("=" * 60)
    
    # Change to repo root
    if not os.path.exists('scripts/ingest_county.py'):
        print("❌ Must be run from repo root")
        sys.exit(1)
    
    success_count = 0
    total_count = len(BOOTSTRAP_COUNTIES)
    
    for county in BOOTSTRAP_COUNTIES:
        if bootstrap_county(county):
            success_count += 1
        else:
            print(f"❌ {county} bootstrap failed - continuing with others")
    
    # Summary
    print(f"\n{'=' * 60}")
    print("BOOTSTRAP SUMMARY")
    print(f"{'=' * 60}")
    print(f"Counties processed: {total_count}")
    print(f"Successful: {success_count}")
    print(f"Failed: {total_count - success_count}")
    
    if success_count == total_count:
        print("🎉 All bootstrap counties completed successfully!")
        print("\nNext steps:")
        print("1. Check updated metrics with scripts/shard8_county_check.py")
        print("2. Work on letter improvements for hillsborough, bay, nassau") 
    else:
        print("⚠️  Some counties failed - check logs and retry manually")
    
    return success_count == total_count

if __name__ == "__main__":
    main()