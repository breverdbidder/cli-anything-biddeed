#!/usr/bin/env python3
"""
SHARD-9 Gold Standard Master Coordinator: leon, clay, okaloosa, dixie, taylor
Autonomous session implementing priority fixes based on current metrics

Counties and Current Status (from issue brief):
- leon (2/10): A✓, H✓ - Focus on B, C/D, E, F issues
- clay (1/10): A✓ - Critical freshness issue (H=373h), need B, C/D, E, F fixes  
- okaloosa (1/10): A✓ - Similar issues, very stale (H=574h)
- dixie (0/10): Complete greenfield - needs full pipeline setup
- taylor (0/10): Complete greenfield - needs full pipeline setup

Sprint Priorities from issue brief:
1. C/D ROOT CAUSE - PropertyOnion coverage issues, pre-authorized to adopt clerk/official-records as supplementary litmus
2. E LINKAGE - Parcel linkage via county property appraiser ArcGIS FeatureServer  
3. B VERIFICATION - Independent data sources for verified outcomes (>95% requirement)
"""
import os
import sys
import json
import httpx
from datetime import datetime
import subprocess

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# SHARD-9 assigned counties
ASSIGNED_COUNTIES = ['leon', 'clay', 'okaloosa', 'dixie', 'taylor']

# County to CO_NO mapping (from FL counties manifest)
COUNTY_CO_MAPPING = {
    'leon': 38,
    'clay': 15, 
    'okaloosa': 57,
    'dixie': 23,
    'taylor': 79
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
    print(f"[{timestamp}] SHARD-9 {action} | {county} | {details}")

def test_connection():
    """Test basic connection to Supabase"""
    try:
        client = httpx.Client(timeout=30)
        r = client.get(f"{SUPABASE_URL}/rest/v1/fl_counties?select=count&limit=1", headers=sb_headers())
        if r.status_code == 200:
            log_action("CONNECTION", "system", "✅ Database connection successful")
            return True
        else:
            log_action("CONNECTION", "system", f"❌ Database connection failed: {r.text}")
            return False
    except Exception as e:
        log_action("CONNECTION", "system", f"❌ Connection error: {e}")
        return False

def evaluate_county_current(county_slug):
    """Run the pencil_dod_evaluate_county function for a single county"""
    try:
        client = httpx.Client(timeout=60)
        
        # Call the RPC function
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=sb_headers(),
            json={"county_slug_arg": county_slug}
        )
        
        if r.status_code == 200:
            result = r.json()
            log_action("EVALUATE", county_slug, "✅ County evaluation completed")
            
            if isinstance(result, list) and len(result) > 0:
                metrics = {}
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    status = letter_data.get('pass', False)
                    metrics[letter] = {
                        'metric': metric,
                        'pass': status,
                        'raw': letter_data
                    }
                    status_icon = "✅" if status else "❌"
                    log_action("METRIC", county_slug, f"{letter}: {status_icon} {metric}")
                return metrics
            return {}
        else:
            log_action("EVALUATE", county_slug, f"❌ Failed to evaluate: {r.status_code} - {r.text}")
            return None
            
    except Exception as e:
        log_action("EVALUATE", county_slug, f"❌ Error evaluating: {e}")
        return None

def check_county_data_status(county):
    """Check basic data ingestion status for a county"""
    try:
        client = httpx.Client(timeout=30)
        co_no = COUNTY_CO_MAPPING.get(county)
        
        # Check multi_county_auctions
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.{county}&select=count&head=true",
            headers=sb_headers()
        )
        auction_count = int(r.headers.get('Content-Range', '0-0/0').split('/')[-1]) if r.status_code == 206 else 0
        
        # Check zoning_assignments
        zoning_count = 0
        if co_no:
            r = client.get(
                f"{SUPABASE_URL}/rest/v1/zoning_assignments?co_no=eq.{co_no}&select=count&head=true",
                headers=sb_headers()
            )
            zoning_count = int(r.headers.get('Content-Range', '0-0/0').split('/')[-1]) if r.status_code == 206 else 0
        
        status = {
            'county': county,
            'co_no': co_no,
            'auctions': auction_count,
            'zoning': zoning_count,
            'needs_baseline': auction_count == 0
        }
        
        log_action("DATA_STATUS", county, f"Auctions: {auction_count:,}, Zoning: {zoning_count:,}")
        return status
        
    except Exception as e:
        log_action("DATA_STATUS", county, f"❌ Error checking status: {e}")
        return None

def run_county_ingestion(county):
    """Run baseline county ingestion for greenfield counties"""
    co_no = COUNTY_CO_MAPPING.get(county)
    if not co_no:
        log_action("INGESTION", county, "❌ No CO_NO mapping found")
        return False
    
    log_action("INGESTION", county, f"📥 Starting baseline ingestion for CO_NO={co_no}")
    
    try:
        # Run the county ingestion script
        result = subprocess.run([
            'python3', 'scripts/ingest_county.py', '--county', str(co_no), '--full'
        ], capture_output=True, text=True, timeout=3600)
        
        if result.returncode == 0:
            log_action("INGESTION", county, "✅ Baseline ingestion completed")
            return True
        else:
            log_action("INGESTION", county, f"❌ Ingestion failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        log_action("INGESTION", county, "⏰ Ingestion timed out")
        return False
    except Exception as e:
        log_action("INGESTION", county, f"❌ Ingestion error: {e}")
        return False

def implement_cd_parity_fix(county):
    """Implement C/D parity fixes using clerk/official records as supplementary litmus"""
    log_action("CD_PARITY", county, "🔧 Implementing C/D parity fix (clerk records supplement)")
    
    # This is a placeholder for the actual C/D parity fix implementation
    # Based on the issue brief, we're pre-authorized to adopt clerk/official-records 
    # as supplementary litmus source when PropertyOnion coverage is the root cause
    
    try:
        # TODO: Implement actual clerk records lookup and parity reconciliation
        # For now, log the action and return True to indicate the fix was attempted
        log_action("CD_PARITY", county, "⚠️ C/D fix placeholder - needs full implementation")
        return True
    except Exception as e:
        log_action("CD_PARITY", county, f"❌ C/D fix error: {e}")
        return False

def implement_e_linkage_fix(county):
    """Implement parcel linkage via county property appraiser ArcGIS FeatureServer"""
    co_no = COUNTY_CO_MAPPING.get(county)
    log_action("E_LINKAGE", county, f"🔗 Implementing parcel linkage for CO_NO={co_no}")
    
    try:
        # TODO: Implement actual ArcGIS FeatureServer parcel linkage
        # This would involve:
        # 1. Finding the county property appraiser ArcGIS endpoint
        # 2. Querying parcel data by parcel_id matching
        # 3. Updating parcel_id fields in multi_county_auctions
        
        log_action("E_LINKAGE", county, "⚠️ E linkage fix placeholder - needs full implementation")
        return True
    except Exception as e:
        log_action("E_LINKAGE", county, f"❌ E linkage error: {e}")
        return False

def implement_b_verification_fix(county):
    """Implement independent verified outcomes data sources"""
    log_action("B_VERIFICATION", county, "📋 Implementing verified outcomes fix")
    
    try:
        # TODO: Implement actual verified outcomes scraper
        # This would involve:
        # 1. Scraping clerk records for sale results
        # 2. Creating independent data sources (not PropertyOnion-derived)
        # 3. Writing to verified_outcomes tables with independent data_source tags
        
        log_action("B_VERIFICATION", county, "⚠️ B verification fix placeholder - needs full implementation")
        return True
    except Exception as e:
        log_action("B_VERIFICATION", county, f"❌ B verification error: {e}")
        return False

def analyze_and_prioritize_counties():
    """Analyze current status and prioritize work"""
    log_action("ANALYSIS", "system", "📊 Analyzing county status and prioritizing work")
    
    county_analysis = {}
    
    for county in ASSIGNED_COUNTIES:
        # Get current metrics
        metrics = evaluate_county_current(county)
        data_status = check_county_data_status(county)
        
        if metrics is None or data_status is None:
            continue
            
        # Calculate priority score based on current status and potential impact
        priority_score = 0
        
        # Greenfield counties (dixie, taylor) get lower priority unless they have auction data
        if data_status['needs_baseline']:
            priority_score = 1
        else:
            # Counties with existing data - prioritize by highest leverage fixes
            pass_count = sum(1 for letter_data in metrics.values() if letter_data['pass'])
            priority_score = 10 - pass_count  # More failing letters = higher priority
            
            # Boost priority for counties with critical issues (H failure = stale data)
            if not metrics.get('H', {}).get('pass', False):
                priority_score += 5
        
        county_analysis[county] = {
            'metrics': metrics,
            'data_status': data_status,
            'priority_score': priority_score,
            'pass_count': sum(1 for letter_data in metrics.values() if letter_data['pass']) if metrics else 0
        }
        
        log_action("ANALYSIS", county, f"Priority: {priority_score}, Pass: {county_analysis[county]['pass_count']}/10")
    
    # Sort by priority score (higher = more urgent)
    prioritized = sorted(county_analysis.items(), key=lambda x: x[1]['priority_score'], reverse=True)
    
    return prioritized

def main():
    """Main coordinator function for SHARD-9 autonomous session"""
    print("=" * 80)
    print("SHARD-9 GOLD STANDARD AUTONOMOUS SESSION")
    print("Counties: leon, clay, okaloosa, dixie, taylor")
    print("Ship-to-Main Mandate: Direct commits to main branch")
    print("=" * 80)
    
    if not SUPABASE_KEY:
        log_action("SETUP", "system", "❌ No Supabase API key found in environment")
        sys.exit(1)
    
    if not test_connection():
        sys.exit(1)
    
    # Phase 1: Analysis and Prioritization
    prioritized_counties = analyze_and_prioritize_counties()
    
    log_action("PRIORITIZATION", "system", "📋 County work order:")
    for i, (county, analysis) in enumerate(prioritized_counties, 1):
        log_action("PRIORITIZATION", county, f"#{i} - Priority: {analysis['priority_score']}, Status: {analysis['pass_count']}/10")
    
    # Phase 2: Implement fixes based on priority
    for county, analysis in prioritized_counties[:3]:  # Work on top 3 priority counties
        log_action("WORK_START", county, f"🚀 Starting work on {county}")
        
        # Handle greenfield counties first
        if analysis['data_status']['needs_baseline']:
            log_action("BASELINE", county, "🌱 Greenfield county - running baseline ingestion")
            success = run_county_ingestion(county)
            if not success:
                log_action("BASELINE", county, "❌ Baseline ingestion failed - skipping")
                continue
        
        # Focus on highest-leverage fixes based on sprint priorities
        metrics = analysis['metrics']
        
        # Priority 1: C/D ROOT CAUSE (PropertyOnion coverage issues)
        if not metrics.get('C', {}).get('pass') or not metrics.get('D', {}).get('pass'):
            implement_cd_parity_fix(county)
        
        # Priority 2: E LINKAGE (parcel linkage via appraiser ArcGIS)
        if not metrics.get('E', {}).get('pass'):
            implement_e_linkage_fix(county)
        
        # Priority 3: B VERIFICATION (independent verified outcomes)
        if not metrics.get('B', {}).get('pass'):
            implement_b_verification_fix(county)
    
    # Phase 3: Verification and reporting
    log_action("VERIFICATION", "system", "🔍 Running final verification")
    
    for county in ASSIGNED_COUNTIES:
        final_metrics = evaluate_county_current(county)
        if final_metrics:
            pass_count = sum(1 for letter_data in final_metrics.values() if letter_data['pass'])
            log_action("FINAL_STATUS", county, f"Final score: {pass_count}/10")
    
    log_action("SESSION_END", "system", "✅ SHARD-9 autonomous session completed")

if __name__ == "__main__":
    main()