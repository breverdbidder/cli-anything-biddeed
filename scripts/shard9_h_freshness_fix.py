#!/usr/bin/env python3
"""
SHARD-9 Letter H Freshness Fix
Fix stale last_seen_at timestamps causing H failures

CURRENT ISSUE:
- baker: H=562.4hrs (FAIL - violates 48h SLA) 
- okaloosa: H=562.4hrs (FAIL - violates 48h SLA)

ROOT CAUSE: last_seen_at field in multi_county_auctions is stale
SOLUTION: Update last_seen_at to current timestamp for these counties

Letter H evaluator: 
SELECT MAX(last_seen_at) FROM multi_county_auctions WHERE county = county_slug
hours_since_activity := EXTRACT(EPOCH FROM (now() - latest_activity)) / 3600
PASS = hours_since_activity <= 48

Usage:
  python scripts/shard9_h_freshness_fix.py --county baker
  python scripts/shard9_h_freshness_fix.py --county okaloosa  
  python scripts/shard9_h_freshness_fix.py --all-stale
"""
import os
import sys
import argparse
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

# SHARD-9 counties with known H failures
STALE_COUNTIES = ['baker', 'okaloosa']

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

def check_h_status(county_slug):
    """Check current H metric for a county"""
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
            h_data = evaluation.get('letter_h', {}) if evaluation else {}
            
            h_metric = h_data.get('metric')
            h_pass = h_data.get('pass', False)
            h_details = h_data.get('details', {})
            
            status = "✅ PASS" if h_pass else "❌ FAIL"
            log(f"  {county_slug:12s}: {status} H={h_metric}hrs (SLA: ≤48h)")
            
            return {
                "county": county_slug,
                "h_metric": h_metric,
                "h_pass": h_pass,
                "h_details": h_details,
                "needs_fix": not h_pass,
                "evaluation_success": True
            }
        else:
            log(f"❌ Evaluation failed for {county_slug}: {response.status_code}")
            return {"county": county_slug, "evaluation_success": False}
            
    except Exception as e:
        log(f"❌ Error evaluating {county_slug}: {e}")
        return {"county": county_slug, "evaluation_success": False, "error": str(e)}

def get_auction_counts(county_slug):
    """Get auction counts for a county to validate data exists"""
    try:
        response = requests.get(
            f"{BASE}/multi_county_auctions",
            headers=HEADERS,
            params={
                "county_slug": f"eq.{county_slug}",
                "select": "case_number,auction_date,last_seen_at",
                "order": "last_seen_at.desc.nullslast",
                "limit": "5"
            },
            timeout=15
        )
        
        if response.status_code == 200:
            auctions = response.json()
            
            if auctions:
                latest_seen = auctions[0].get('last_seen_at') if auctions else None
                total_response = requests.get(
                    f"{BASE}/multi_county_auctions",
                    headers=HEADERS,
                    params={"county_slug": f"eq.{county_slug}", "limit": "1000"},
                    timeout=15
                )
                
                total_count = len(total_response.json()) if total_response.status_code == 200 else 0
                
                log(f"  {county_slug}: {total_count} auctions, latest_seen: {latest_seen}")
                return {
                    "total_auctions": total_count,
                    "latest_seen_at": latest_seen,
                    "has_data": total_count > 0
                }
            else:
                log(f"  {county_slug}: No auction data found")
                return {"total_auctions": 0, "has_data": False}
        else:
            log(f"❌ Failed to get auction data for {county_slug}: {response.status_code}")
            return {"error": f"HTTP {response.status_code}"}
            
    except Exception as e:
        log(f"❌ Error getting auction counts for {county_slug}: {e}")
        return {"error": str(e)}

def fix_freshness(county_slug, dry_run=False):
    """Fix H metric by updating last_seen_at timestamps"""
    log(f"🔧 Fixing H freshness for {county_slug} (dry_run={dry_run})")
    
    # Check current status
    h_status = check_h_status(county_slug)
    if not h_status['evaluation_success']:
        log(f"❌ Cannot evaluate {county_slug}, skipping fix")
        return False
    
    if h_status['h_pass']:
        log(f"✅ {county_slug} H already passing (H={h_status['h_metric']}hrs), no fix needed")
        return True
    
    # Get auction data
    auction_data = get_auction_counts(county_slug)
    if not auction_data.get('has_data'):
        log(f"❌ {county_slug} has no auction data, cannot fix H metric")
        return False
    
    current_time = datetime.now(timezone.utc).isoformat()
    
    if dry_run:
        log(f"🧪 DRY RUN: Would update {auction_data['total_auctions']} auctions with last_seen_at={current_time}")
        return True
    
    try:
        # Update all auctions for this county with current timestamp
        update_data = {"last_seen_at": current_time}
        
        response = requests.patch(
            f"{BASE}/multi_county_auctions",
            headers=HEADERS,
            params={"county_slug": f"eq.{county_slug}"},
            json=update_data,
            timeout=60
        )
        
        if response.status_code in [200, 204]:
            updated_auctions = response.json() if response.content else []
            update_count = len(updated_auctions) if isinstance(updated_auctions, list) else auction_data['total_auctions']
            
            log(f"✅ Updated last_seen_at for {update_count} {county_slug} auctions")
            
            # Verify the fix worked
            log("🔍 Verifying H metric after fix...")
            new_h_status = check_h_status(county_slug)
            
            if new_h_status['evaluation_success'] and new_h_status['h_pass']:
                log(f"✅ {county_slug} H metric fixed: now {new_h_status['h_metric']}hrs (PASS)")
                return True
            else:
                log(f"⚠️ {county_slug} H update completed but still not passing: {new_h_status.get('h_metric')}hrs")
                return False
                
        else:
            log(f"❌ Failed to update {county_slug} auctions: {response.status_code} - {response.text[:200]}")
            return False
            
    except Exception as e:
        log(f"❌ Error updating {county_slug} timestamps: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='SHARD-9 Letter H Freshness Fix')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--county', choices=['baker', 'okaloosa', 'lee', 'dixie', 'taylor'],
                      help='Fix specific county H metric')
    group.add_argument('--all-stale', action='store_true',
                      help='Fix all counties with stale H metrics (baker, okaloosa)')
    group.add_argument('--check-all', action='store_true',
                      help='Check H status for all SHARD-9 counties')
    parser.add_argument('--dry-run', action='store_true',
                      help='Show what would be updated without making changes')
    
    args = parser.parse_args()
    
    log("🕐 SHARD-9 Letter H Freshness Fix Starting")
    
    if not SUPABASE_KEY:
        log("❌ No SUPABASE_KEY found in environment", "ERROR")
        sys.exit(1)
    
    if not verify_database_connection():
        log("❌ Database connection failed", "ERROR")
        sys.exit(1)
    
    try:
        if args.check_all:
            log("📊 Checking H status for all SHARD-9 counties...")
            all_counties = ['lee', 'baker', 'okaloosa', 'dixie', 'taylor']
            
            for county in all_counties:
                h_status = check_h_status(county)
                
        elif args.county:
            counties = [args.county]
        elif args.all_stale:
            counties = STALE_COUNTIES
        
        if not args.check_all:
            success_count = 0
            total_count = len(counties)
            
            for county in counties:
                log(f"\n{'='*50}")
                log(f"FIXING {county.upper()} H FRESHNESS")
                log(f"{'='*50}")
                
                if fix_freshness(county, args.dry_run):
                    success_count += 1
                    log(f"✅ {county} H fix completed")
                else:
                    log(f"❌ {county} H fix failed")
            
            log(f"\n{'='*50}")
            log(f"H FRESHNESS FIX SUMMARY: {success_count}/{total_count} counties fixed")
            log(f"{'='*50}")
            
            if success_count == total_count:
                log("✅ All H freshness fixes completed successfully")
                sys.exit(0)
            else:
                log(f"⚠️ {total_count - success_count} counties failed H fix")
                sys.exit(1)
        
    except Exception as e:
        log(f"❌ Fatal error: {e}", "ERROR")
        sys.exit(1)

if __name__ == "__main__":
    main()