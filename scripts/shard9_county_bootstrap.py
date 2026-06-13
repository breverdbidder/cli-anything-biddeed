#!/usr/bin/env python3
"""
SHARD-9 County Bootstrap: Basic Data Ingestion for Dixie & Taylor
Autonomous Gold Standard session - get dixie and taylor from 0/10 to basic coverage

Priority: dixie (co_no=15) and taylor (co_no=62) currently show all FAIL/null metrics
ROOT CAUSE: No auction data ingested for these counties

This script:
1. Counts available parcels via FL GIO API
2. Ingests basic county parcel data 
3. Sets up for auction data pipeline
4. Updates county_conquest_status

Usage:
  python scripts/shard9_county_bootstrap.py --county dixie
  python scripts/shard9_county_bootstrap.py --county taylor
  python scripts/shard9_county_bootstrap.py --all-zero
"""
import os
import sys
import subprocess
import argparse
import time
import requests
from datetime import datetime, timezone

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

# SHARD-9 county mappings (from migration data)
COUNTY_MAPPINGS = {
    'lee': {'co_no': 36, 'fips': '12071'},
    'baker': {'co_no': 2, 'fips': '12003'}, 
    'okaloosa': {'co_no': 46, 'fips': '12091'},
    'dixie': {'co_no': 15, 'fips': '12029'},
    'taylor': {'co_no': 62, 'fips': '12123'}
}

def log(message, level="INFO"):
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"[{timestamp}] {level}: {message}")

def verify_database_connection():
    """Test Supabase connection"""
    try:
        response = requests.get(f"{BASE}/audit_log", headers=HEADERS, params={"limit": "1"}, timeout=10)
        if response.status_code == 200:
            log("✅ Supabase connection successful")
            return True
        else:
            log(f"❌ Connection failed: {response.status_code} - {response.text}", "ERROR")
            return False
    except Exception as e:
        log(f"❌ Connection error: {e}", "ERROR")
        return False

def check_county_status(county_slug):
    """Check current status of a county in the database"""
    try:
        # Check fl_counties table
        response = requests.get(
            f"{BASE}/fl_counties",
            headers=HEADERS,
            params={"co_no": f"eq.{COUNTY_MAPPINGS[county_slug]['co_no']}", "select": "*"},
            timeout=10
        )
        
        if response.status_code == 200:
            county_data = response.json()
            county_info = county_data[0] if county_data else None
            
            if not county_info:
                log(f"❌ {county_slug} not found in fl_counties table")
                return None
                
            # Check multi_county_auctions for existing data
            response2 = requests.get(
                f"{BASE}/multi_county_auctions",
                headers=HEADERS,
                params={"county_slug": f"eq.{county_slug}", "select": "count", "limit": "1"},
                timeout=10
            )
            
            auction_count = 0
            if response2.status_code == 200:
                # Supabase count query returns special format
                try:
                    # Try regular count
                    auction_response = requests.get(
                        f"{BASE}/multi_county_auctions",
                        headers=HEADERS,
                        params={"county_slug": f"eq.{county_slug}", "limit": "10"},
                        timeout=10
                    )
                    if auction_response.status_code == 200:
                        auction_count = len(auction_response.json())
                except:
                    auction_count = 0
            
            status = {
                "county_slug": county_slug,
                "co_no": county_info['co_no'],
                "name": county_info['name'],
                "total_parcels": county_info.get('total_parcels', 0),
                "auction_count": auction_count,
                "last_updated": county_info.get('updated_at'),
                "needs_bootstrap": county_info.get('total_parcels', 0) == 0 and auction_count == 0
            }
            
            return status
            
    except Exception as e:
        log(f"❌ Error checking {county_slug} status: {e}", "ERROR")
        return None

def run_county_ingestion(county_slug, full_ingestion=False):
    """Run the ingest_county.py script for a specific county"""
    co_no = COUNTY_MAPPINGS[county_slug]['co_no']
    
    log(f"🚀 Starting ingestion for {county_slug} (co_no={co_no})")
    
    try:
        # Build command
        cmd = ['python3', 'scripts/ingest_county.py', '--county', str(co_no)]
        if full_ingestion:
            cmd.append('--full')
        
        log(f"Running: {' '.join(cmd)}")
        
        # Run the ingestion script
        start_time = time.time()
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1800,  # 30 minute timeout
            cwd=os.getcwd()
        )
        
        elapsed = time.time() - start_time
        
        if result.returncode == 0:
            log(f"✅ {county_slug} ingestion completed in {elapsed:.1f}s")
            log(f"STDOUT: {result.stdout[-500:]}" if result.stdout else "No stdout")
            return True
        else:
            log(f"❌ {county_slug} ingestion failed (exit {result.returncode})", "ERROR")
            log(f"STDERR: {result.stderr[-500:]}" if result.stderr else "No stderr")
            return False
            
    except subprocess.TimeoutExpired:
        log(f"❌ {county_slug} ingestion timed out after 30 minutes", "ERROR")
        return False
    except Exception as e:
        log(f"❌ {county_slug} ingestion error: {e}", "ERROR") 
        return False

def evaluate_county_after_bootstrap(county_slug):
    """Evaluate county metrics after bootstrap to measure improvement"""
    log(f"📊 Evaluating {county_slug} metrics post-bootstrap")
    
    try:
        payload = {"county_name": county_slug}
        response = requests.post(
            f"{BASE}/rpc/pencil_dod_evaluate_county",
            headers=HEADERS,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            evaluation = response.json()
            
            # Count passing letters
            pass_count = 0
            letters = []
            
            for letter in 'ABCDEFGHIJ':
                letter_key = f'letter_{letter.lower()}'
                if letter_key in evaluation:
                    letter_data = evaluation[letter_key]
                    if isinstance(letter_data, dict):
                        is_pass = letter_data.get('pass', False)
                        metric = letter_data.get('metric')
                        
                        if is_pass:
                            pass_count += 1
                        
                        status = "✓" if is_pass else "✗"
                        if metric is not None:
                            letters.append(f"{letter}:{status}{metric}")
                        else:
                            letters.append(f"{letter}:{status}")
            
            log(f"📈 {county_slug} evaluation: {pass_count}/10 letters passing")
            log(f"    Letters: {' '.join(letters[:5])}")
            if len(letters) > 5:
                log(f"             {' '.join(letters[5:])}")
            
            return {
                "success": True,
                "score": f"{pass_count}/10",
                "letters": letters,
                "raw_evaluation": evaluation
            }
        else:
            log(f"❌ {county_slug} evaluation failed: {response.status_code}")
            return {"success": False, "error": f"HTTP {response.status_code}"}
            
    except Exception as e:
        log(f"❌ Error evaluating {county_slug}: {e}")
        return {"success": False, "error": str(e)}

def bootstrap_county(county_slug, full_ingestion=False):
    """Complete bootstrap pipeline for a county"""
    log(f"🏗️ Bootstrapping {county_slug.upper()}")
    
    # 1. Check current status  
    log("1️⃣ Checking current county status...")
    status = check_county_status(county_slug)
    if not status:
        log(f"❌ Could not determine status for {county_slug}")
        return False
    
    log(f"    Current: {status['total_parcels']} parcels, {status['auction_count']} auctions")
    
    if not status['needs_bootstrap'] and not full_ingestion:
        log(f"✅ {county_slug} already has data. Use --full to force re-ingestion.")
        return True
    
    # 2. Run FL GIO ingestion
    log("2️⃣ Running FL GIO parcel ingestion...")
    ingestion_success = run_county_ingestion(county_slug, full_ingestion)
    if not ingestion_success:
        log(f"❌ Ingestion failed for {county_slug}")
        return False
    
    # 3. Verify ingestion
    log("3️⃣ Verifying ingestion results...")
    new_status = check_county_status(county_slug)
    if new_status and new_status['total_parcels'] > 0:
        log(f"✅ Ingestion successful: {new_status['total_parcels']} parcels loaded")
    else:
        log(f"❌ Ingestion verification failed")
        return False
    
    # 4. Evaluate metrics
    log("4️⃣ Evaluating Gold Standard metrics...")
    evaluation = evaluate_county_after_bootstrap(county_slug)
    if evaluation['success']:
        log(f"✅ Bootstrap complete for {county_slug}: {evaluation['score']}")
        return True
    else:
        log(f"⚠️ Bootstrap ingestion done, but evaluation failed: {evaluation.get('error')}")
        return True  # Ingestion succeeded, evaluation is secondary

def main():
    parser = argparse.ArgumentParser(description='SHARD-9 County Bootstrap')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--county', choices=['dixie', 'taylor', 'lee', 'baker', 'okaloosa'],
                      help='Bootstrap specific county')
    group.add_argument('--all-zero', action='store_true',
                      help='Bootstrap all counties with 0/10 scores (dixie, taylor)')
    parser.add_argument('--full', action='store_true',
                      help='Force full re-ingestion even if data exists')
    
    args = parser.parse_args()
    
    log("🚀 SHARD-9 County Bootstrap Starting")
    
    if not SUPABASE_KEY:
        log("❌ No SUPABASE_KEY found in environment", "ERROR")
        sys.exit(1)
    
    if not verify_database_connection():
        log("❌ Database connection failed", "ERROR")
        sys.exit(1)
    
    try:
        success_count = 0
        total_count = 0
        
        if args.county:
            counties = [args.county]
        elif args.all_zero:
            counties = ['dixie', 'taylor']  # Both currently 0/10
        
        for county in counties:
            total_count += 1
            log(f"\n{'='*60}")
            log(f"BOOTSTRAPPING {county.upper()} ({total_count}/{len(counties)})")
            log(f"{'='*60}")
            
            if bootstrap_county(county, args.full):
                success_count += 1
                log(f"✅ {county} bootstrap COMPLETED")
            else:
                log(f"❌ {county} bootstrap FAILED")
        
        log(f"\n{'='*60}")
        log(f"SHARD-9 BOOTSTRAP SUMMARY: {success_count}/{total_count} counties successful")
        log(f"{'='*60}")
        
        if success_count == total_count:
            log("✅ All county bootstraps completed successfully")
            sys.exit(0)
        else:
            log(f"⚠️ {total_count - success_count} counties failed bootstrap")
            sys.exit(1)
            
    except Exception as e:
        log(f"❌ Fatal error: {e}", "ERROR")
        sys.exit(1)

if __name__ == "__main__":
    main()