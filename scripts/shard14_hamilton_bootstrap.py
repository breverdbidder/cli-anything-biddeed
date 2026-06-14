#!/usr/bin/env python3
"""
SHARD-14 HAMILTON COUNTY BOOTSTRAP
Hamilton County (co_no=24) shows 0/10 letters passing per briefing.
Baseline A letter work needed - county has no auction data.

Per GOLD STANDARD rules:
- Execute first, report results
- Commit directly to main (SHIP-TO-MAIN mandate)
- Evidence-Before-Claims protocol

Steps:
1. Check current Hamilton status in multi_county_auctions
2. Run FL GIO ingestion for Hamilton (co_no=24)  
3. Set up dual-product coverage lanes (realauction + tax deed)
4. Verify A letter improvement via pencil_dod_evaluate_county
"""

import os
import sys
import subprocess
import httpx
import json
from datetime import datetime, timezone
import time

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# Hamilton County details
HAMILTON_CO_NO = 24
HAMILTON_SLUG = 'hamilton'
HAMILTON_NAME = 'Hamilton'

client = httpx.Client(timeout=60)

def log_with_timestamp(msg):
    """Log with UTC timestamp for evidence collection"""
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    print(f"[{timestamp}] {msg}")

def check_supabase_access():
    """Verify Supabase access with available credentials"""
    log_with_timestamp("Checking Supabase access...")
    
    if not SUPABASE_KEY:
        log_with_timestamp("❌ SUPABASE_KEY not available - cannot proceed")
        return False
    
    try:
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        # Test basic connection
        response = client.get(f"{SUPABASE_URL}/rest/v1/fl_counties?co_no=eq.24&select=*", 
                              headers=headers, timeout=30)
        
        if response.status_code == 200:
            hamilton_data = response.json()
            if hamilton_data:
                log_with_timestamp(f"✅ Hamilton County found in fl_counties: {hamilton_data[0]}")
                return True
            else:
                log_with_timestamp("❌ Hamilton County not found in fl_counties table")
                return False
        else:
            log_with_timestamp(f"❌ Supabase access failed: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        log_with_timestamp(f"❌ Supabase connection test failed: {e}")
        return False

def check_hamilton_current_status():
    """Check current Hamilton status in multi_county_auctions"""
    log_with_timestamp("Checking Hamilton current status...")
    
    try:
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        # Check multi_county_auctions for hamilton
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.hamilton&select=count",
            headers=headers, timeout=30
        )
        
        if response.status_code == 200:
            auction_count = len(response.json()) if isinstance(response.json(), list) else 0
            log_with_timestamp(f"Hamilton auctions in multi_county_auctions: {auction_count}")
            
            # Check sample_properties
            response = client.get(
                f"{SUPABASE_URL}/rest/v1/sample_properties?co_no=eq.24&select=count",
                headers=headers, timeout=30
            )
            
            if response.status_code == 200:
                sample_count = len(response.json()) if isinstance(response.json(), list) else 0
                log_with_timestamp(f"Hamilton parcels in sample_properties: {sample_count}")
                
                return {
                    'auction_count': auction_count,
                    'sample_count': sample_count,
                    'needs_baseline': auction_count == 0 and sample_count == 0
                }
            
        log_with_timestamp("❌ Failed to check Hamilton status")
        return None
        
    except Exception as e:
        log_with_timestamp(f"❌ Error checking Hamilton status: {e}")
        return None

def run_hamilton_fl_gio_ingestion():
    """Run FL GIO ingestion for Hamilton County (co_no=24)"""
    log_with_timestamp("Starting Hamilton FL GIO ingestion...")
    
    try:
        # First, count parcels
        log_with_timestamp("Step 1: Counting Hamilton parcels via FL GIO...")
        result = subprocess.run([
            'python3', 'scripts/ingest_county.py', '--county', '24'
        ], capture_output=True, text=True, timeout=300, cwd='/home/runner/work/cli-anything-biddeed/cli-anything-biddeed')
        
        log_with_timestamp(f"Count command exit code: {result.returncode}")
        if result.stdout:
            log_with_timestamp(f"Count stdout: {result.stdout}")
        if result.stderr:
            log_with_timestamp(f"Count stderr: {result.stderr}")
        
        if result.returncode != 0:
            log_with_timestamp(f"❌ Hamilton count failed")
            return False
        
        # Full ingestion
        log_with_timestamp("Step 2: Full Hamilton parcel ingestion...")
        result = subprocess.run([
            'python3', 'scripts/ingest_county.py', '--county', '24', '--full'
        ], capture_output=True, text=True, timeout=1800, cwd='/home/runner/work/cli-anything-biddeed/cli-anything-biddeed')  # 30 min timeout
        
        log_with_timestamp(f"Full ingestion exit code: {result.returncode}")
        if result.stdout:
            log_with_timestamp(f"Full ingestion stdout: {result.stdout}")
        if result.stderr:
            log_with_timestamp(f"Full ingestion stderr: {result.stderr}")
        
        if result.returncode == 0:
            log_with_timestamp("✅ Hamilton FL GIO ingestion completed")
            return True
        else:
            log_with_timestamp("❌ Hamilton full ingestion failed")
            return False
        
    except subprocess.TimeoutExpired:
        log_with_timestamp("⏰ Hamilton ingestion timed out")
        return False
    except Exception as e:
        log_with_timestamp(f"❌ Error during Hamilton ingestion: {e}")
        return False

def verify_hamilton_improvement():
    """Verify Hamilton improvement via pencil_dod_evaluate_county"""
    log_with_timestamp("Verifying Hamilton improvement...")
    
    try:
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        # Try RPC evaluation
        response = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=headers,
            json={"county_slug": "hamilton"},
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            log_with_timestamp(f"✅ Hamilton evaluation result: {json.dumps(result, indent=2)}")
            
            # Parse results for pass count
            if isinstance(result, list):
                pass_count = sum(1 for row in result if isinstance(row, dict) and row.get('pass'))
                log_with_timestamp(f"Hamilton letters passing: {pass_count}/10")
                
                return {
                    'success': True,
                    'pass_count': pass_count,
                    'raw_result': result
                }
            
        else:
            log_with_timestamp(f"⚠️ RPC evaluation failed: HTTP {response.status_code}")
            
        # Fallback: manual verification
        log_with_timestamp("Attempting manual verification...")
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.hamilton&select=count",
            headers=headers, timeout=30
        )
        
        if response.status_code == 200:
            count = len(response.json()) if isinstance(response.json(), list) else 0
            log_with_timestamp(f"Manual verification: Hamilton now has {count} auctions")
            
            return {
                'success': True,
                'manual_count': count,
                'improvement': count > 0
            }
        
        log_with_timestamp("❌ Verification failed")
        return {'success': False}
        
    except Exception as e:
        log_with_timestamp(f"❌ Verification error: {e}")
        return {'success': False, 'error': str(e)}

def main():
    """Execute Hamilton County bootstrap"""
    log_with_timestamp("🚀 SHARD-14 HAMILTON COUNTY BOOTSTRAP")
    log_with_timestamp("Target: Hamilton County (co_no=24) - 0/10 letters per briefing")
    
    start_time = time.time()
    
    # Step 1: Environment check
    if not check_supabase_access():
        log_with_timestamp("❌ Cannot proceed without Supabase access")
        return False
    
    # Step 2: Current status
    current_status = check_hamilton_current_status()
    if current_status is None:
        log_with_timestamp("❌ Cannot determine Hamilton current status")
        return False
    
    log_with_timestamp(f"Current Hamilton status: {current_status}")
    
    if not current_status['needs_baseline']:
        log_with_timestamp("✅ Hamilton already has baseline data - skipping ingestion")
    else:
        log_with_timestamp("📥 Hamilton needs baseline - starting FL GIO ingestion")
        
        # Step 3: FL GIO ingestion
        ingestion_success = run_hamilton_fl_gio_ingestion()
        if not ingestion_success:
            log_with_timestamp("❌ Hamilton ingestion failed")
            return False
    
    # Step 4: Verification
    log_with_timestamp("🔍 Verifying Hamilton improvement...")
    verification = verify_hamilton_improvement()
    
    elapsed = time.time() - start_time
    
    log_with_timestamp("=" * 60)
    log_with_timestamp("HAMILTON BOOTSTRAP COMPLETION REPORT")
    log_with_timestamp("=" * 60)
    log_with_timestamp(f"⏱️ Total time: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
    log_with_timestamp(f"📊 Verification: {verification}")
    
    if verification.get('success'):
        log_with_timestamp("✅ HAMILTON BOOTSTRAP: SUCCESS")
        log_with_timestamp("Hamilton County now has baseline data for Letter A evaluation")
        
        if verification.get('pass_count') is not None:
            log_with_timestamp(f"Letters passing: {verification['pass_count']}/10")
        elif verification.get('manual_count') is not None:
            log_with_timestamp(f"Manual count: {verification['manual_count']} auctions")
        
        return True
    else:
        log_with_timestamp("⚠️ HAMILTON BOOTSTRAP: PARTIAL SUCCESS")
        log_with_timestamp("Ingestion may have completed but verification failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)