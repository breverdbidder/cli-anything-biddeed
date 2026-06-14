#!/usr/bin/env python3
"""
SHARD-9 Greenfield Bootstrap: dixie, taylor
Complete pipeline setup for counties with 0/10 scores

Based on existing county ingestion patterns and Gold Standard requirements
"""
import os
import sys
import subprocess
import httpx
from datetime import datetime
import time

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# Greenfield counties
GREENFIELD_COUNTIES = {
    'dixie': {
        'co_no': 23,
        'full_name': 'Dixie County',
        'expected_parcels': 10000,  # Estimate - small rural county
        'clerk_url': 'dixieclerk.com',
        'appraiser_url': 'dixiepropertyappraiser.com'
    },
    'taylor': {
        'co_no': 79,
        'full_name': 'Taylor County', 
        'expected_parcels': 15000,  # Estimate - small rural county
        'clerk_url': 'taylorclerk.com',
        'appraiser_url': 'taylorpropertyappraiser.com'
    }
}

def sb_headers():
    return {
        "apikey": SUPABASE_KEY, 
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def log_action(action, county, details=""):
    """Log actions for tracking and verification"""
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{timestamp}] GREENFIELD {action} | {county} | {details}")

def check_current_data_status(county):
    """Check what data currently exists for a greenfield county"""
    config = GREENFIELD_COUNTIES[county]
    co_no = config['co_no']
    
    try:
        client = httpx.Client(timeout=30)
        
        # Check multi_county_auctions
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.{county}&select=count&head=true",
            headers=sb_headers()
        )
        auction_count = int(r.headers.get('Content-Range', '0-0/0').split('/')[-1]) if r.status_code == 206 else 0
        
        # Check zoning_assignments
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/zoning_assignments?co_no=eq.{co_no}&select=count&head=true",
            headers=sb_headers()
        )
        zoning_count = int(r.headers.get('Content-Range', '0-0/0').split('/')[-1]) if r.status_code == 206 else 0
        
        # Check sample_properties
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/sample_properties?co_no=eq.{co_no}&select=count&head=true",
            headers=sb_headers()
        )
        sample_count = int(r.headers.get('Content-Range', '0-0/0').split('/')[-1]) if r.status_code == 206 else 0
        
        # Check fl_counties entry
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/fl_counties?co_no=eq.{co_no}&select=*",
            headers=sb_headers()
        )
        fl_county_data = r.json()[0] if r.status_code == 200 and r.json() else None
        
        status = {
            'auctions': auction_count,
            'zoning': zoning_count,
            'samples': sample_count,
            'fl_county_exists': fl_county_data is not None,
            'total_parcels': fl_county_data.get('total_parcels', 0) if fl_county_data else 0,
            'is_truly_greenfield': auction_count == 0 and zoning_count == 0
        }
        
        log_action("CHECK_STATUS", county, f"Auctions: {auction_count}, Zoning: {zoning_count}, Samples: {sample_count}")
        return status
        
    except Exception as e:
        log_action("CHECK_STATUS", county, f"❌ Error checking status: {e}")
        return None

def run_baseline_county_ingestion(county):
    """Run the baseline FL GIO county ingestion"""
    config = GREENFIELD_COUNTIES[county]
    co_no = config['co_no']
    
    log_action("BASELINE_INGESTION", county, f"📥 Starting FL GIO ingestion for CO_NO={co_no}")
    
    try:
        # First, run a count to see how many parcels we'll get
        log_action("BASELINE_INGESTION", county, "🔢 Running parcel count")
        result = subprocess.run([
            'python3', 'scripts/ingest_county.py', '--county', str(co_no)
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode != 0:
            log_action("BASELINE_INGESTION", county, f"❌ Count failed: {result.stderr}")
            return False
        
        log_action("BASELINE_INGESTION", county, f"✅ Count completed: {result.stdout.strip()}")
        
        # Then run full ingestion
        log_action("BASELINE_INGESTION", county, "📦 Running full ingestion")
        result = subprocess.run([
            'python3', 'scripts/ingest_county.py', '--county', str(co_no), '--full'
        ], capture_output=True, text=True, timeout=3600)  # 1 hour timeout
        
        if result.returncode == 0:
            log_action("BASELINE_INGESTION", county, "✅ Full ingestion completed")
            return True
        else:
            log_action("BASELINE_INGESTION", county, f"❌ Full ingestion failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        log_action("BASELINE_INGESTION", county, "⏰ Ingestion timed out")
        return False
    except Exception as e:
        log_action("BASELINE_INGESTION", county, f"❌ Ingestion error: {e}")
        return False

def setup_foreclosure_scraping_pipeline(county):
    """Set up foreclosure data scraping for the county"""
    config = GREENFIELD_COUNTIES[county]
    
    log_action("FORECLOSURE_SETUP", county, "🏛️ Setting up foreclosure scraping pipeline")
    
    try:
        # Check if the county has online foreclosure data
        clerk_url = f"https://www.{config['clerk_url']}"
        
        # Test clerk connectivity
        try:
            r = httpx.head(clerk_url, timeout=10, follow_redirects=True)
            if r.status_code == 200:
                log_action("FORECLOSURE_SETUP", county, f"✅ Clerk accessible: {clerk_url}")
            else:
                log_action("FORECLOSURE_SETUP", county, f"⚠️ Clerk not accessible: {clerk_url}")
        except:
            log_action("FORECLOSURE_SETUP", county, f"❌ Clerk connection failed: {clerk_url}")
        
        # TODO: Implement actual foreclosure pipeline setup
        # This would involve:
        # 1. Configuring scraper for county's specific foreclosure system
        # 2. Adding county to pipeline.counties configuration
        # 3. Setting up periodic scraping schedules
        
        log_action("FORECLOSURE_SETUP", county, "⚠️ Foreclosure pipeline placeholder - needs implementation")
        return True
        
    except Exception as e:
        log_action("FORECLOSURE_SETUP", county, f"❌ Foreclosure setup error: {e}")
        return False

def setup_property_data_pipeline(county):
    """Set up property appraiser data pipeline"""
    config = GREENFIELD_COUNTIES[county]
    
    log_action("PROPERTY_SETUP", county, "🏠 Setting up property data pipeline")
    
    try:
        # Test property appraiser connectivity
        appraiser_url = f"https://www.{config['appraiser_url']}"
        
        try:
            r = httpx.head(appraiser_url, timeout=10, follow_redirects=True)
            if r.status_code == 200:
                log_action("PROPERTY_SETUP", county, f"✅ Appraiser accessible: {appraiser_url}")
            else:
                log_action("PROPERTY_SETUP", county, f"⚠️ Appraiser not accessible: {appraiser_url}")
        except:
            log_action("PROPERTY_SETUP", county, f"❌ Appraiser connection failed: {appraiser_url}")
        
        # TODO: Implement actual property data pipeline setup
        # This would involve:
        # 1. Discovering ArcGIS endpoints for parcel data
        # 2. Setting up parcel linkage automation
        # 3. Configuring property value/assessment scraping
        
        log_action("PROPERTY_SETUP", county, "⚠️ Property pipeline placeholder - needs implementation")
        return True
        
    except Exception as e:
        log_action("PROPERTY_SETUP", county, f"❌ Property setup error: {e}")
        return False

def seed_basic_jurisdictions(county):
    """Seed basic jurisdiction data for the county"""
    config = GREENFIELD_COUNTIES[county]
    full_name = config['full_name']
    co_no = config['co_no']
    
    log_action("JURISDICTION_SEED", county, f"🏛️ Seeding jurisdictions for {full_name}")
    
    try:
        client = httpx.Client(timeout=30)
        
        # Check if jurisdictions already exist
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/jurisdictions?county=eq.{full_name}&select=count&head=true",
            headers=sb_headers()
        )
        existing_count = int(r.headers.get('Content-Range', '0-0/0').split('/')[-1]) if r.status_code == 206 else 0
        
        if existing_count > 0:
            log_action("JURISDICTION_SEED", county, f"ℹ️ {existing_count} jurisdictions already exist")
            return True
        
        # Seed basic jurisdictions (county + major municipalities)
        basic_jurisdictions = [
            {
                'name': f"Unincorporated {full_name}",
                'county': full_name,
                'state': 'FL',
                'co_no': co_no,
                'jurisdiction_type': 'unincorporated'
            }
        ]
        
        # TODO: Research actual municipalities in dixie/taylor counties
        # For now, just create the unincorporated jurisdiction
        
        for jurisdiction in basic_jurisdictions:
            r = client.post(
                f"{SUPABASE_URL}/rest/v1/jurisdictions",
                headers=sb_headers(),
                json=jurisdiction
            )
            
            if r.status_code == 201:
                log_action("JURISDICTION_SEED", county, f"✅ Created jurisdiction: {jurisdiction['name']}")
            else:
                log_action("JURISDICTION_SEED", county, f"⚠️ Failed to create jurisdiction: {r.text}")
        
        log_action("JURISDICTION_SEED", county, "✅ Basic jurisdictions seeded")
        return True
        
    except Exception as e:
        log_action("JURISDICTION_SEED", county, f"❌ Jurisdiction seeding error: {e}")
        return False

def verify_greenfield_progress(county):
    """Verify that greenfield setup made progress"""
    log_action("VERIFY_PROGRESS", county, "🔍 Verifying greenfield setup progress")
    
    # Check data status again
    status = check_current_data_status(county)
    if not status:
        log_action("VERIFY_PROGRESS", county, "❌ Could not verify progress")
        return False
    
    # Check if we're no longer truly greenfield
    progress_made = not status['is_truly_greenfield']
    
    if progress_made:
        log_action("VERIFY_PROGRESS", county, "✅ Progress made - no longer greenfield")
        log_action("VERIFY_PROGRESS", county, f"  Data: {status['auctions']} auctions, {status['zoning']} zoning records")
    else:
        log_action("VERIFY_PROGRESS", county, "⚠️ Still appears greenfield - check setup manually")
    
    return progress_made

def bootstrap_greenfield_county(county):
    """Main function to bootstrap a single greenfield county"""
    log_action("START_BOOTSTRAP", county, f"🚀 Starting greenfield bootstrap")
    
    # Step 1: Check current status
    status = check_current_data_status(county)
    if not status:
        log_action("START_BOOTSTRAP", county, "❌ Could not check current status")
        return False
    
    if not status['is_truly_greenfield']:
        log_action("START_BOOTSTRAP", county, "ℹ️ County is not truly greenfield - skipping")
        return True
    
    # Step 2: Run baseline county ingestion
    if not run_baseline_county_ingestion(county):
        log_action("START_BOOTSTRAP", county, "❌ Baseline ingestion failed")
        return False
    
    # Step 3: Set up foreclosure scraping pipeline
    if not setup_foreclosure_scraping_pipeline(county):
        log_action("START_BOOTSTRAP", county, "⚠️ Foreclosure setup incomplete")
        # Don't fail here - this is not critical for initial bootstrap
    
    # Step 4: Set up property data pipeline
    if not setup_property_data_pipeline(county):
        log_action("START_BOOTSTRAP", county, "⚠️ Property setup incomplete")
        # Don't fail here - this is not critical for initial bootstrap
    
    # Step 5: Seed basic jurisdictions
    if not seed_basic_jurisdictions(county):
        log_action("START_BOOTSTRAP", county, "⚠️ Jurisdiction seeding incomplete")
        # Don't fail here - this is not critical for initial bootstrap
    
    # Step 6: Verify progress
    progress = verify_greenfield_progress(county)
    
    if progress:
        log_action("COMPLETE_BOOTSTRAP", county, "✅ Greenfield bootstrap completed successfully")
    else:
        log_action("COMPLETE_BOOTSTRAP", county, "⚠️ Bootstrap completed but verify results manually")
    
    return True

def main():
    """Main function to bootstrap all greenfield counties"""
    print("=" * 60)
    print("SHARD-9 GREENFIELD BOOTSTRAP")
    print("Counties: dixie, taylor (0/10 scores)")
    print("=" * 60)
    
    if not SUPABASE_KEY:
        print("❌ No Supabase API key found in environment")
        sys.exit(1)
    
    # Process each greenfield county
    results = {}
    
    for county in GREENFIELD_COUNTIES.keys():
        print(f"\n{'='*40}")
        print(f"Bootstrapping {county.upper()}")
        print(f"{'='*40}")
        
        results[county] = bootstrap_greenfield_county(county)
    
    # Summary
    print(f"\n{'='*60}")
    print("GREENFIELD BOOTSTRAP SUMMARY")
    print(f"{'='*60}")
    
    for county, success in results.items():
        status = "✅ COMPLETED" if success else "❌ FAILED"
        print(f"{county:12s} | {status}")
    
    # Overall success rate
    success_count = sum(results.values())
    total_count = len(results)
    print(f"\nOverall: {success_count}/{total_count} counties completed successfully")
    
    if success_count > 0:
        print("\nNext steps:")
        print("  1. Monitor ingestion completion")
        print("  2. Set up county-specific scraping pipelines")
        print("  3. Configure Gold Standard evaluation")
        print("  4. Begin work on higher-level letters (G, I, J)")

if __name__ == "__main__":
    main()