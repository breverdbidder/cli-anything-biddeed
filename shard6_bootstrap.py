#!/usr/bin/env python3
"""
SHARD-6 BOOTSTRAP PROTOCOL
Bootstrap counties: calhoun (17), liberty (49), hendry (36), then highlands (38), st_johns (65)

Based on issue analysis:
- calhoun: 0/10 passed - completely cold start
- liberty: 0/10 passed - completely cold start  
- hendry: 1/10 passed - needs basic ingestion
- highlands: 2/10 passed - has some data, needs improvements
- st_johns: 2/10 passed - has some data, needs improvements

Strategy: Start with complete cold start counties, then move to counties with some data
"""
import os
import sys
import subprocess
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# County mappings from fl_counties_manifest.yml  
SHARD6_COUNTIES = {
    'calhoun': {'co_no': 17, 'priority': 1, 'status': 'cold_start'},
    'liberty': {'co_no': 49, 'priority': 2, 'status': 'cold_start'}, 
    'hendry': {'co_no': 36, 'priority': 3, 'status': 'minimal_data'},
    'highlands': {'co_no': 38, 'priority': 4, 'status': 'partial_data'},
    'st_johns': {'co_no': 65, 'priority': 5, 'status': 'partial_data'}
}

def run_county_ingestion(county_name: str, co_no: int, full: bool = False) -> Dict:
    """Run county ingestion using existing scripts/ingest_county.py"""
    logger.info(f"🏔️ Starting {'full' if full else 'count'} ingestion for {county_name} (CO_NO={co_no})")
    
    start_time = time.time()
    
    try:
        # Build command
        cmd = ['python3', 'scripts/ingest_county.py', '--county', str(co_no)]
        if full:
            cmd.append('--full')
        
        # Run ingestion with timeout
        timeout = 3600 if full else 300  # 1 hour for full, 5 min for count
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        elapsed = time.time() - start_time
        
        if result.returncode == 0:
            logger.info(f"✅ {county_name} ingestion completed in {elapsed:.1f}s")
            
            # Parse output for metrics
            output_lines = result.stdout.split('\n')
            parcel_count = None
            for line in output_lines:
                if 'parcels' in line.lower() and any(char.isdigit() for char in line):
                    # Try to extract parcel count
                    import re
                    numbers = re.findall(r'[\d,]+', line)
                    if numbers:
                        parcel_count = int(numbers[-1].replace(',', ''))
                        break
            
            return {
                'status': 'success',
                'county': county_name,
                'co_no': co_no,
                'elapsed_time': elapsed,
                'parcel_count': parcel_count,
                'stdout': result.stdout,
                'stderr': result.stderr
            }
        else:
            logger.error(f"❌ {county_name} ingestion failed: {result.stderr}")
            return {
                'status': 'failed',
                'county': county_name,
                'co_no': co_no,
                'elapsed_time': elapsed,
                'error': result.stderr,
                'stdout': result.stdout
            }
    
    except subprocess.TimeoutExpired:
        logger.error(f"⏰ {county_name} ingestion timed out after {timeout}s")
        return {
            'status': 'timeout',
            'county': county_name,
            'co_no': co_no,
            'elapsed_time': timeout,
            'error': f'Timed out after {timeout}s'
        }
    except Exception as e:
        logger.error(f"❌ {county_name} ingestion exception: {e}")
        return {
            'status': 'exception',
            'county': county_name,
            'co_no': co_no,
            'error': str(e)
        }

def bootstrap_cold_start_counties():
    """Bootstrap the counties with 0/10 letters passing"""
    logger.info("🥶 BOOTSTRAPPING COLD START COUNTIES")
    
    cold_start_counties = [name for name, info in SHARD6_COUNTIES.items() 
                          if info['status'] == 'cold_start']
    
    results = []
    
    for county_name in sorted(cold_start_counties, key=lambda x: SHARD6_COUNTIES[x]['priority']):
        co_no = SHARD6_COUNTIES[county_name]['co_no']
        
        logger.info(f"\n📋 PROCESSING: {county_name.upper()} (CO_NO={co_no})")
        
        # Step 1: Count parcels
        logger.info(f"Step 1: Counting parcels for {county_name}...")
        count_result = run_county_ingestion(county_name, co_no, full=False)
        results.append(count_result)
        
        if count_result['status'] != 'success':
            logger.error(f"❌ Count failed for {county_name}, skipping full ingestion")
            continue
        
        # Step 2: Full ingestion if count succeeded
        logger.info(f"Step 2: Full ingestion for {county_name}...")
        full_result = run_county_ingestion(county_name, co_no, full=True)
        results.append(full_result)
        
        # Log progress
        if full_result['status'] == 'success':
            parcel_count = full_result.get('parcel_count', 'Unknown')
            logger.info(f"🎉 {county_name} BOOTSTRAP COMPLETE: {parcel_count} parcels ingested")
        else:
            logger.warning(f"⚠️ {county_name} full ingestion had issues: {full_result.get('error', 'Unknown')}")
    
    return results

def bootstrap_minimal_data_counties():
    """Bootstrap counties with minimal data (like hendry with 1/10)"""
    logger.info("📊 BOOTSTRAPPING MINIMAL DATA COUNTIES")
    
    minimal_counties = [name for name, info in SHARD6_COUNTIES.items() 
                       if info['status'] == 'minimal_data']
    
    results = []
    
    for county_name in sorted(minimal_counties, key=lambda x: SHARD6_COUNTIES[x]['priority']):
        co_no = SHARD6_COUNTIES[county_name]['co_no']
        
        logger.info(f"\n📋 PROCESSING: {county_name.upper()} (CO_NO={co_no})")
        
        # For minimal data counties, try full ingestion to ensure complete baseline
        logger.info(f"Running full ingestion for {county_name} to ensure complete baseline...")
        full_result = run_county_ingestion(county_name, co_no, full=True)
        results.append(full_result)
        
        if full_result['status'] == 'success':
            parcel_count = full_result.get('parcel_count', 'Unknown')
            logger.info(f"🎉 {county_name} BASELINE COMPLETE: {parcel_count} parcels")
        
    return results

def main():
    """Execute SHARD-6 bootstrap protocol"""
    logger.info("🚀 SHARD-6 BOOTSTRAP PROTOCOL EXECUTION")
    logger.info("Target: calhoun (17), liberty (49), hendry (36), highlands (38), st_johns (65)")
    
    start_time = time.time()
    all_results = []
    
    try:
        # Phase 1: Cold start counties (calhoun, liberty)
        logger.info("\n" + "="*60)
        logger.info("PHASE 1: COLD START COUNTIES")
        logger.info("="*60)
        
        cold_results = bootstrap_cold_start_counties()
        all_results.extend(cold_results)
        
        # Phase 2: Minimal data counties (hendry)
        logger.info("\n" + "="*60)
        logger.info("PHASE 2: MINIMAL DATA COUNTIES")
        logger.info("="*60)
        
        minimal_results = bootstrap_minimal_data_counties()
        all_results.extend(minimal_results)
        
        # Summary
        elapsed_total = time.time() - start_time
        
        logger.info("\n" + "="*60)
        logger.info("SHARD-6 BOOTSTRAP COMPLETION REPORT")
        logger.info("="*60)
        logger.info(f"⏱️ Total time: {elapsed_total:.1f} seconds ({elapsed_total/60:.1f} minutes)")
        
        # Results by county
        counties_processed = {}
        for result in all_results:
            county = result['county']
            if county not in counties_processed:
                counties_processed[county] = []
            counties_processed[county].append(result)
        
        logger.info(f"\n📊 COUNTIES PROCESSED: {len(counties_processed)}")
        
        for county, county_results in counties_processed.items():
            co_no = SHARD6_COUNTIES[county]['co_no']
            logger.info(f"\n  {county.upper()} (CO_NO={co_no}):")
            
            for i, result in enumerate(county_results, 1):
                status = result['status']
                elapsed = result.get('elapsed_time', 0)
                operation = 'FULL' if i > 1 else 'COUNT'
                
                if status == 'success':
                    parcel_count = result.get('parcel_count', 'N/A')
                    logger.info(f"    {operation}: ✅ {status.upper()} ({elapsed:.1f}s, {parcel_count} parcels)")
                else:
                    error = result.get('error', 'Unknown error')[:100]
                    logger.info(f"    {operation}: ❌ {status.upper()} ({elapsed:.1f}s) - {error}")
        
        # Success criteria
        successful_counties = len([c for c, results in counties_processed.items() 
                                 if any(r['status'] == 'success' for r in results)])
        
        logger.info(f"\n🎯 BOOTSTRAP SUCCESS: {successful_counties}/{len(SHARD6_COUNTIES)} counties have successful ingestion")
        
        if successful_counties >= 3:  # At least 3 counties successful
            logger.info("✅ BOOTSTRAP PROTOCOL: SUFFICIENT PROGRESS")
            logger.info("Ready to proceed to Letter B/I/J improvements")
        else:
            logger.warning("⚠️ BOOTSTRAP PROTOCOL: PARTIAL SUCCESS")
            logger.info("Some counties may need manual intervention")
        
        return {
            'protocol_success': successful_counties >= 3,
            'counties_processed': successful_counties,
            'total_counties': len(SHARD6_COUNTIES),
            'results': all_results,
            'elapsed_time': elapsed_total
        }
        
    except Exception as e:
        logger.error(f"❌ Bootstrap protocol failed: {e}")
        return {
            'protocol_success': False,
            'error': str(e),
            'results': all_results,
            'elapsed_time': time.time() - start_time
        }

if __name__ == "__main__":
    result = main()
    sys.exit(0 if result.get('protocol_success') else 1)