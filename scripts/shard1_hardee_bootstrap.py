#!/usr/bin/env python3
"""
SHARD-1 Hardee County Bootstrap (CO_NO=35)
Currently 0/10 on Gold Standard - likely missing all basic auction data
Priority: Get Letter A passing by ingesting dual-product coverage

Usage:
  python scripts/shard1_hardee_bootstrap.py
"""
import os
import sys
import time
import httpx
import subprocess
from datetime import datetime, timezone

# Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

# Hardee County details from fl_counties_manifest.yml
HARDEE_CO_NO = 35
HARDEE_NAME = "Hardee"
HARDEE_SLUG = "hardee"

def log(msg):
    """Timestamped logging"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def check_hardee_current_status():
    """Check current data for Hardee county"""
    try:
        client = httpx.Client(timeout=30)
        
        # Check fl_counties for Hardee
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/fl_counties?co_no=eq.{HARDEE_CO_NO}&select=*",
            headers=sb_headers()
        )
        fl_county = r.json()[0] if r.status_code == 200 and r.json() else None
        
        # Check multi_county_auctions
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.{HARDEE_SLUG}&select=count",
            headers=sb_headers()
        )
        auction_count = len(r.json()) if r.status_code == 200 else 0
        
        # Check zoning_assignments
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/zoning_assignments?co_no=eq.{HARDEE_CO_NO}&select=count",
            headers=sb_headers()
        )
        zoning_count = len(r.json()) if r.status_code == 200 else 0
        
        log(f"Hardee current status:")
        log(f"  fl_counties entry: {'✅' if fl_county else '❌'}")
        log(f"  total_parcels: {fl_county.get('total_parcels', 0) if fl_county else 0}")
        log(f"  auction records: {auction_count}")
        log(f"  zoning assignments: {zoning_count}")
        
        return {
            'fl_county_exists': fl_county is not None,
            'total_parcels': fl_county.get('total_parcels', 0) if fl_county else 0,
            'auction_count': auction_count,
            'zoning_count': zoning_count,
            'needs_basic_setup': auction_count == 0 and zoning_count == 0
        }
        
    except Exception as e:
        log(f"❌ Error checking Hardee status: {e}")
        return None

def run_county_ingestion():
    """Run county ingestion for Hardee using existing script"""
    log(f"🚀 Starting Hardee County ingestion (CO_NO={HARDEE_CO_NO})...")
    
    try:
        # First, count parcels to verify
        log("📊 Counting Hardee parcels...")
        result = subprocess.run([
            'python3', 'scripts/ingest_county.py', '--county', str(HARDEE_CO_NO)
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode != 0:
            log(f"❌ Count failed: {result.stderr}")
            return False
        
        log(f"✅ Count completed:")
        log(result.stdout)
        
        # Then do full ingestion
        log("📦 Starting full Hardee ingestion...")
        result = subprocess.run([
            'python3', 'scripts/ingest_county.py', '--county', str(HARDEE_CO_NO), '--full'
        ], capture_output=True, text=True, timeout=3600)  # 1 hour timeout
        
        if result.returncode != 0:
            log(f"❌ Full ingestion failed: {result.stderr}")
            return False
        
        log(f"✅ Full ingestion completed:")
        log(result.stdout)
        return True
        
    except subprocess.TimeoutExpired:
        log(f"⏰ Hardee ingestion timed out")
        return False
    except Exception as e:
        log(f"❌ Error running Hardee ingestion: {e}")
        return False

def setup_hardee_auction_scraper():
    """Set up Hardee county auction scraping"""
    log("🔧 Setting up Hardee auction data scraping...")
    
    # Check if Hardee has RealAuction presence
    # According to manifest, hardee slug is null, so needs manual setup
    
    # Create basic auction data structure for Hardee
    hardee_config = {
        'county': HARDEE_SLUG,
        'name': HARDEE_NAME,
        'co_no': HARDEE_CO_NO,
        'foreclosure_platform': 'clerk_hardee',  # Default to clerk calendar
        'foreclosure_url': 'https://www.hardeeclerk.com/foreclosure-sales/',
        'tax_deed_platform': 'realauction',  # Most FL counties use RealAuction for tax deeds
        'tax_deed_url': 'https://www.realauction.com/florida/hardee'
    }
    
    log(f"📝 Hardee auction config: {hardee_config}")
    
    # TODO: Implement actual auction scraping for Hardee
    # For now, establish the configuration
    
    return True

def evaluate_hardee_post_setup():
    """Evaluate Hardee after setup to see improvement"""
    try:
        client = httpx.Client(timeout=60)
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=sb_headers(),
            json={"county_slug_arg": HARDEE_SLUG}
        )
        
        if r.status_code == 200:
            result = r.json()
            log(f"📈 Hardee evaluation post-setup:")
            if isinstance(result, list) and len(result) > 0:
                pass_count = sum(1 for x in result if x.get('pass'))
                log(f"  OVERALL: {pass_count}/10 pass")
                
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    status = "✅" if letter_data.get('pass') else "❌"
                    context = letter_data.get('context', '')
                    log(f"    {letter}: {status} metric={metric} {context}")
            return result
        else:
            log(f"❌ Hardee evaluation failed: {r.status_code}")
            return None
            
    except Exception as e:
        log(f"❌ Error evaluating Hardee: {e}")
        return None

def main():
    log("=" * 60)
    log("SHARD-1: Hardee County Bootstrap")
    log(f"Target: Move hardee from 0/10 to Letter A pass minimum")
    log("=" * 60)
    
    if not SUPABASE_KEY:
        log("❌ SUPABASE_KEY not available")
        sys.exit(1)
    
    # Check current status
    status = check_hardee_current_status()
    if not status:
        log("❌ Could not check Hardee status")
        sys.exit(1)
    
    # If Hardee needs basic setup, run ingestion
    if status['needs_basic_setup']:
        log("🎯 Hardee needs basic data ingestion")
        if not run_county_ingestion():
            log("❌ Hardee ingestion failed")
            sys.exit(1)
    else:
        log("ℹ️ Hardee already has some data, checking what's missing...")
    
    # Set up auction scraping
    if not setup_hardee_auction_scraper():
        log("❌ Hardee auction setup failed")
        sys.exit(1)
    
    # Evaluate results
    log("🔍 Evaluating Hardee after bootstrap...")
    final_result = evaluate_hardee_post_setup()
    
    if final_result:
        pass_count = sum(1 for x in final_result if x.get('pass'))
        if pass_count > 0:
            log(f"✅ Hardee bootstrap SUCCESS! Now {pass_count}/10")
        else:
            log(f"⚠️ Hardee still 0/10 - may need manual intervention")
    
    log("🏁 Hardee bootstrap complete!")

if __name__ == "__main__":
    main()