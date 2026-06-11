#!/usr/bin/env python3
"""
SHARD-10 County Bootstrap: franklin, union counties
Sets up baseline data ingestion for counties with 0/10 Gold Standard status

Target counties:
- franklin: CO_NO=29 (currently 0/10)
- union: CO_NO=73 (currently 0/10)

This script runs:
1. FL GIO parcel ingestion via ingest_county.py 
2. Pipeline.counties configuration setup
3. Baseline auction data verification
4. Initial gold standard evaluation

Usage:
  python scripts/shard10_county_bootstrap.py
  python scripts/shard10_county_bootstrap.py --county franklin
  python scripts/shard10_county_bootstrap.py --county union
"""
import os
import sys
import subprocess
import httpx
import json
from datetime import datetime
import argparse

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# SHARD-10 zero-data counties from fl_counties_manifest.yml
TARGET_COUNTIES = [
    {'name': 'Franklin', 'co_no': 29, 'slug': 'franklin'},
    {'name': 'Union', 'co_no': 73, 'slug': 'union'}
]

def log(msg):
    """Log with timestamp"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

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
        log("✅ Supabase connection verified")
        return True
    except Exception as e:
        log(f"❌ Supabase connection failed: {e}")
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
        
        # Check pipeline.counties configuration
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/counties?slug=eq.{slug}&select=*",
            headers=headers
        )
        pipeline_configured = len(response.json()) > 0 if response.status_code == 200 else False
        
        status = {
            'county': name,
            'co_no': co_no,
            'slug': slug,
            'fl_county_exists': fl_county is not None,
            'total_parcels': fl_county.get('total_parcels', 0) if fl_county else 0,
            'sample_properties': sample_count,
            'auctions': auction_count,
            'pipeline_configured': pipeline_configured,
            'needs_ingestion': sample_count == 0,
            'has_baseline_data': auction_count > 0 or sample_count > 0
        }
        
        return status
        
    except Exception as e:
        log(f"❌ Error checking {name} status: {e}")
        return None

def run_county_ingestion(co_no, name):
    """Run FL GIO parcel ingestion for a county"""
    log(f"🚀 Starting county ingestion for {name} (CO_NO={co_no})")
    
    try:
        # First run count to estimate size
        log(f"Getting parcel count for {name}...")
        result = subprocess.run([
            sys.executable, "scripts/ingest_county.py", 
            "--county", str(co_no)
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            log(f"✅ Count successful for {name}")
            log(result.stdout[-500:])  # Show last 500 chars
            
            # Run full ingestion
            log(f"Running full ingestion for {name} (this may take 30-60 minutes)...")
            result_full = subprocess.run([
                sys.executable, "scripts/ingest_county.py",
                "--county", str(co_no), "--full"
            ], capture_output=True, text=True, timeout=3600)  # 1 hour timeout
            
            if result_full.returncode == 0:
                log(f"✅ Full ingestion completed for {name}")
                log(result_full.stdout[-500:])
                return True
            else:
                log(f"❌ Full ingestion failed for {name}")
                log(f"Error: {result_full.stderr}")
                return False
        else:
            log(f"❌ Count failed for {name}")
            log(f"Error: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        log(f"❌ County ingestion timeout for {name}")
        return False
    except Exception as e:
        log(f"❌ County ingestion error for {name}: {e}")
        return False

def configure_pipeline_county(slug, co_no, name):
    """Configure pipeline.counties entry for scraping"""
    log(f"🔧 Configuring pipeline for {name}")
    
    # Basic county configuration for Gold Standard work
    # This sets up the county for future scraper configuration
    county_config = {
        'slug': slug,
        'co_no': co_no,
        'name': name,
        'state': 'FL',
        'foreclosure_platform': 'manual_queue',  # Start with manual queue
        'tax_deed_platform': 'manual_queue',
        'enabled': True,
        'priority': 3,  # Low priority for new counties
        'notes': f'SHARD-10 bootstrap - {datetime.now().strftime("%Y-%m-%d")}',
        'created_at': datetime.now().isoformat()
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
            f"{SUPABASE_URL}/rest/v1/counties",
            headers=headers,
            json=county_config
        )
        
        if response.status_code in [200, 201, 204]:
            log(f"✅ Pipeline configured for {name}")
            return True
        else:
            log(f"❌ Pipeline configuration failed for {name}: {response.text}")
            return False
            
    except Exception as e:
        log(f"❌ Pipeline configuration error for {name}: {e}")
        return False

def evaluate_county_final(slug):
    """Run final Gold Standard evaluation"""
    log(f"📊 Running Gold Standard evaluation for {slug}")
    
    try:
        client = httpx.Client(timeout=60)
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        response = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=headers,
            json={"county_slug_arg": slug}
        )
        
        if response.status_code == 200:
            result = response.json()
            pass_count = 0
            
            log(f"📈 {slug.upper()} Gold Standard Results:")
            for letter_data in result:
                letter = letter_data.get('letter', '?')
                metric = letter_data.get('metric')
                is_pass = letter_data.get('pass', False)
                detail = letter_data.get('detail', '')
                
                if is_pass:
                    pass_count += 1
                    log(f"  {letter}: ✅ PASS metric={metric}")
                else:
                    log(f"  {letter}: ❌ FAIL metric={metric} - {detail}")
            
            log(f"📊 TOTAL IMPROVEMENT: 0/10 → {pass_count}/10 (+{pass_count})")
            return pass_count
        else:
            log(f"❌ Evaluation failed for {slug}: {response.text}")
            return 0
            
    except Exception as e:
        log(f"❌ Evaluation error for {slug}: {e}")
        return 0

def bootstrap_single_county(county_info):
    """Bootstrap a single county through the complete pipeline"""
    co_no = county_info['co_no']
    name = county_info['name']
    slug = county_info['slug']
    
    log(f"\n{'='*60}")
    log(f"BOOTSTRAPPING {name.upper()} COUNTY (CO_NO={co_no})")
    log(f"{'='*60}")
    
    # Step 1: Check current status
    status = check_county_status(co_no, name, slug)
    if not status:
        log(f"❌ Could not check status for {name}")
        return False
    
    log(f"📋 Current status for {name}:")
    log(f"  - Sample properties: {status['sample_properties']}")
    log(f"  - Auction records: {status['auctions']}")
    log(f"  - Pipeline configured: {status['pipeline_configured']}")
    log(f"  - Needs ingestion: {status['needs_ingestion']}")
    
    # Step 2: Run county ingestion if needed
    if status['needs_ingestion']:
        log(f"🚀 Starting county ingestion for {name}")
        if not run_county_ingestion(co_no, name):
            log(f"❌ County ingestion failed for {name}")
            return False
        
        # Re-check status after ingestion
        status = check_county_status(co_no, name, slug)
        log(f"📊 Post-ingestion: {status['sample_properties']} sample properties")
    else:
        log(f"✅ {name} already has baseline parcel data")
    
    # Step 3: Configure pipeline if needed
    if not status['pipeline_configured']:
        if not configure_pipeline_county(slug, co_no, name):
            log(f"❌ Pipeline configuration failed for {name}")
            return False
    else:
        log(f"✅ {name} already configured in pipeline")
    
    # Step 4: Final evaluation
    final_pass_count = evaluate_county_final(slug)
    
    log(f"\n🎯 BOOTSTRAP COMPLETE FOR {name}")
    log(f"   Gold Standard Score: {final_pass_count}/10")
    log(f"   Expected improvement: Letter A (dual-product) likely PASS")
    log(f"   Next steps: Configure scrapers for foreclosure/tax_deed data")
    
    return final_pass_count > 0

def main():
    parser = argparse.ArgumentParser(description='SHARD-10 County Bootstrap')
    parser.add_argument('--county', choices=['franklin', 'union'], 
                        help='Bootstrap specific county only')
    args = parser.parse_args()
    
    log("🎯 SHARD-10 COUNTY BOOTSTRAP STARTING")
    log(f"Target counties: {[c['name'] for c in TARGET_COUNTIES]}")
    log(f"Timestamp: {datetime.now().isoformat()}")
    
    if not SUPABASE_KEY:
        log("❌ SUPABASE_KEY environment variable not set")
        sys.exit(1)
    
    if not check_supabase_connection():
        sys.exit(1)
    
    # Filter counties if specific county requested
    if args.county:
        TARGET_COUNTIES[:] = [c for c in TARGET_COUNTIES if c['slug'] == args.county]
        log(f"Focusing on single county: {args.county}")
    
    results = {}
    
    # Bootstrap each county
    for county_info in TARGET_COUNTIES:
        results[county_info['slug']] = bootstrap_single_county(county_info)
    
    # Final summary
    log(f"\n{'='*60}")
    log("SHARD-10 BOOTSTRAP SUMMARY")
    log(f"{'='*60}")
    
    total_counties = len(TARGET_COUNTIES)
    successful_counties = sum(1 for success in results.values() if success)
    
    for slug, success in results.items():
        status = "✅ SUCCESS" if success else "❌ FAILED"
        log(f"  {slug}: {status}")
    
    log(f"\nBootstrap Success Rate: {successful_counties}/{total_counties}")
    
    if successful_counties == total_counties:
        log("🎉 All counties successfully bootstrapped!")
        log("Next steps: Configure scrapers and work on remaining Gold Standard letters")
    else:
        log("⚠️  Some counties failed bootstrap - check logs above")

if __name__ == "__main__":
    main()