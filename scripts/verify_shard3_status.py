#!/usr/bin/env python3
"""
SHARD-3 County Status Verification
Check current A-J letter grades for broward, sarasota, gilchrist, seminole, jefferson

Usage:
  python scripts/verify_shard3_status.py
"""
import os
import requests
import json
from datetime import datetime

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}", 
    "Content-Type": "application/json"
}

# Target counties for SHARD-3 from fl_counties_manifest.yml
SHARD3_COUNTIES = [
    {'name': 'broward', 'co_no': 16, 'slug': 'broward'},
    {'name': 'sarasota', 'co_no': 68, 'slug': 'sarasota'},  # slug needs resolution
    {'name': 'gilchrist', 'co_no': 31, 'slug': 'gilchrist'},  # slug needs resolution
    {'name': 'seminole', 'co_no': 69, 'slug': 'seminole'},
    {'name': 'jefferson', 'co_no': 43, 'slug': 'jefferson'}  # slug needs resolution
]

def test_connection():
    """Test Supabase connection"""
    try:
        response = requests.get(f"{BASE}/audit_log", headers=HEADERS, params={"limit": "1"}, timeout=10)
        if response.status_code == 200:
            print("✅ Supabase connection successful")
            return True
        else:
            print(f"❌ Connection failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def check_multi_county_auctions(county_name):
    """Check if county exists in multi_county_auctions table"""
    try:
        response = requests.get(
            f"{BASE}/multi_county_auctions",
            headers=HEADERS,
            params={
                "county": f"eq.{county_name}",
                "select": "count",
                "limit": "1"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            count = len(response.json())
            print(f"  📊 {county_name}: {count} auctions found in multi_county_auctions")
            return count > 0
        return False
    except Exception as e:
        print(f"  ❌ Error checking {county_name} auctions: {e}")
        return False

def get_county_evaluation(county_name):
    """Get evaluation for a specific county using pencil_dod_evaluate_county function"""
    try:
        # Use RPC call to the evaluation function
        payload = {"county_slug_arg": county_name}
        response = requests.post(
            f"{BASE}/rpc/pencil_dod_evaluate_county", 
            headers=HEADERS, 
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Evaluated {county_name}: {len(result) if isinstance(result, list) else 'N/A'} letters")
            return result
        else:
            print(f"⚠️ Failed to evaluate {county_name}: {response.status_code} - {response.text[:200]}")
            return None
            
    except Exception as e:
        print(f"⚠️ Error evaluating {county_name}: {e}")
        return None

def format_evaluation_report(county_info, evaluation):
    """Format a detailed county evaluation report"""
    county_name = county_info['name']
    co_no = county_info['co_no']
    slug = county_info['slug']
    
    report = [f"\n## {county_name.upper()} County (CO_NO={co_no}, slug={slug})"]
    
    if not evaluation:
        report.append("❌ No evaluation data available")
        return "\n".join(report)
    
    if isinstance(evaluation, list) and len(evaluation) > 0:
        report.append("\n### Letter Status:")
        
        pass_count = 0
        for letter_data in evaluation:
            letter = letter_data.get('letter', '?')
            metric = letter_data.get('metric')
            is_pass = letter_data.get('pass', False)
            
            if is_pass:
                pass_count += 1
                status_icon = "✅ PASS"
            else:
                status_icon = "❌ FAIL"
            
            metric_str = f" metric={metric}" if metric is not None else " metric=null"
            report.append(f"  **{letter}**: {status_icon}{metric_str}")
        
        report.append(f"\n**Overall Score**: {pass_count}/10 letters passing")
        
        # Identify critical failures
        failing_letters = [item['letter'] for item in evaluation if not item.get('pass', False)]
        if failing_letters:
            report.append(f"**Failing Letters**: {', '.join(failing_letters)}")
            
            # Flag critical ones
            critical_failures = [l for l in failing_letters if l in ['B', 'I', 'J']]
            if critical_failures:
                report.append(f"**🚨 CRITICAL FAILURES**: {', '.join(critical_failures)} (priority targets)")
    
    return "\n".join(report)

def resolve_county_slugs():
    """Try to resolve missing county slugs by checking multi_county_auctions"""
    print("🔍 Resolving county slugs...")
    
    for county in SHARD3_COUNTIES:
        if county['slug'] == county['name']:  # Already resolved
            continue
            
        # Try the county name as slug
        county_name = county['name']
        if check_multi_county_auctions(county_name):
            county['slug'] = county_name
            print(f"✅ Resolved {county['name']} -> slug: {county_name}")
        else:
            print(f"⚠️ No auctions found for {county_name}, slug remains unresolved")

def main():
    print("🔍 SHARD-3 County Status Verification")
    print(f"Target counties: {', '.join([c['name'] for c in SHARD3_COUNTIES])}")
    print(f"Timestamp: {datetime.now().isoformat()}\n")
    
    # Print debug info about environment
    print(f"SUPABASE_URL: {SUPABASE_URL}")
    print(f"SUPABASE_KEY available: {'Yes' if SUPABASE_KEY else 'No'}")
    
    if not SUPABASE_KEY:
        print("❌ No SUPABASE_KEY found. Checking environment...")
        print(f"Available env vars: {[k for k in os.environ.keys() if 'SUPABASE' in k or 'DB' in k]}")
        return
    
    # Test connection first
    if not test_connection():
        print("❌ Database connection failed.")
        return
    
    # Resolve slugs if needed
    resolve_county_slugs()
    
    print("\n📊 Gathering county evaluations...\n")
    
    # Collect evaluations for each county
    county_reports = []
    for county_info in SHARD3_COUNTIES:
        county_name = county_info['slug']
        
        if not county_name or county_name == 'null':
            print(f"⚠️ Skipping {county_info['name']} - no resolved slug")
            continue
        
        print(f"Processing {county_name}...")
        evaluation = get_county_evaluation(county_name)
        report = format_evaluation_report(county_info, evaluation)
        county_reports.append(report)
    
    # Generate final report
    print("\n" + "="*80)
    print("SHARD-3 COUNTY STATUS REPORT")
    print("="*80)
    
    for report in county_reports:
        print(report)
    
    # Summary and next steps
    print(f"\n" + "="*80)
    print("PRIORITY ACTIONS")
    print("="*80)
    print("Based on issue guidance:")
    print("1. **B+F Priority**: Focus on Brevard AcclaimWeb endpoint (B=verified outcomes, F=tier1 amounts)")
    print("2. **B Critical**: All counties need independent verified outcome sources (not PropertyOnion)")
    print("3. **I Critical**: Property card completion (address+geo+value+zoned parcel) >=95%")
    print("4. **J Critical**: Deal thesis pipeline (bid_decisions: arv+max_bid+ml_score+triangle+CMA)")
    print("5. Ship directly to main - no side branches")

if __name__ == "__main__":
    main()