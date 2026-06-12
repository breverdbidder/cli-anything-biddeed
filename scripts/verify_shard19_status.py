#!/usr/bin/env python3
"""
SHARD-19 County Status Verification (GOLD STANDARD RECOVERY-BD)
Check current A-J letter grades for brevard, duval

Usage:
  python scripts/verify_shard19_status.py
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

# Target counties for SHARD-19
SHARD19_COUNTIES = ['brevard', 'duval']

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

def get_county_evaluation(county):
    """Get evaluation for a specific county using pencil_dod_evaluate_county function"""
    try:
        # Use RPC call to the evaluation function
        payload = {"county_name": county}
        response = requests.post(
            f"{BASE}/rpc/pencil_dod_evaluate_county", 
            headers=HEADERS, 
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"⚠️ Failed to evaluate {county}: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"⚠️ Error evaluating {county}: {e}")
        return None

def get_county_status_direct(county):
    """Get county status directly from gold_standard_county_status table"""
    try:
        response = requests.get(
            f"{BASE}/gold_standard_county_status", 
            headers=HEADERS, 
            params={
                "county": f"eq.{county}",
                "select": "*"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            return data[0] if data else None
        else:
            print(f"⚠️ Failed to get status for {county}: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"⚠️ Error getting status for {county}: {e}")
        return None

def format_county_report(county, evaluation, status):
    """Format a detailed county report"""
    report = [f"\n## {county.upper()} County Status"]
    
    if status:
        report.append(f"**Score**: {status.get('total_score', 'N/A')}/10")
        report.append(f"**Last Updated**: {status.get('updated_at', 'Unknown')}")
    
    if evaluation:
        report.append("\n### Letter Grades with Metrics:")
        for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
            grade_field = f"grade_{letter.lower()}"
            metric_field = f"metric_{letter.lower()}"
            
            grade = evaluation.get(grade_field, 'UNKNOWN')
            metric = evaluation.get(metric_field)
            
            status_icon = "✅ PASS" if grade == "PASS" else "❌ FAIL"
            metric_str = f" metric={metric}" if metric is not None else " metric=null"
            
            report.append(f"**{letter}**: {status_icon} [{metric_str}]")
            
            # Add detailed metrics for failing letters per issue brief
            if letter == 'B' and grade == 'FAIL':
                report.append(f"    └─ ANOMALY: verified_outcomes > closed_sold (should be <=105%)")
            elif letter == 'C' and grade == 'FAIL':
                report.append(f"    └─ matched_clean vs total auctions - PropertyOnion parity check needed")
            elif letter == 'D' and grade == 'FAIL':
                report.append(f"    └─ matched_any vs total auctions - parity issues")
            elif letter == 'E' and grade == 'FAIL':
                report.append(f"    └─ parcel_linked vs total auctions - need appraiser ArcGIS linkage")
            elif letter == 'F' and grade == 'FAIL':
                report.append(f"    └─ tier1_sold vs closed_sold - need authenticated RealAuction results")
            elif letter == 'G' and grade == 'FAIL':
                report.append(f"    └─ zoning density/FAR/parking - need zone_standards backfill")
            elif letter == 'I' and grade == 'FAIL':
                report.append(f"    └─ property card completeness - depends on E+G completion")
            elif letter == 'J' and grade == 'FAIL':
                report.append(f"    └─ deal_complete (Shapira formula) - need J GENERATOR build")
    
    return "\n".join(report)

def main():
    print("🎯 SHARD-19 GOLD STANDARD RECOVERY-BD Status Verification")
    print(f"Target counties: {', '.join(SHARD19_COUNTIES)}")
    print(f"Timestamp: {datetime.now().isoformat()}\n")
    
    # Print debug info about environment
    print(f"SUPABASE_URL: {SUPABASE_URL}")
    print(f"SUPABASE_KEY available: {'Yes' if SUPABASE_KEY else 'No'}")
    
    # Test connection first
    if not test_connection():
        print("❌ Database connection failed. Checking for environment variables...")
        print(f"Available env vars: {[k for k in os.environ.keys() if 'SUPABASE' in k or 'DB' in k]}")
        return
    
    print("📊 Gathering county evaluations...\n")
    
    # Collect data for each county
    county_data = {}
    for county in SHARD19_COUNTIES:
        print(f"Processing {county}...")
        
        # Get evaluation using function
        evaluation = get_county_evaluation(county)
        
        # Get status from table
        status = get_county_status_direct(county)
        
        county_data[county] = {
            'evaluation': evaluation,
            'status': status
        }
    
    # Generate reports
    print("\n" + "="*80)
    print("SHARD-19 GOLD STANDARD RECOVERY-BD COUNTY STATUS REPORT")
    print("="*80)
    
    for county, data in county_data.items():
        evaluation = data.get('evaluation')
        status = data.get('status')
        
        print(format_county_report(county, evaluation, status))
    
    # BREVARD SPRINT ORDER priority analysis
    print(f"\n" + "="*80)
    print("BREVARD SPRINT ORDER ANALYSIS")
    print("="*80)
    
    brevard_data = county_data.get('brevard', {})
    brevard_eval = brevard_data.get('evaluation', {})
    
    if brevard_eval:
        failing_letters = []
        for letter in ['C', 'D', 'J', 'G', 'B']:  # Sprint order priority
            grade = brevard_eval.get(f"grade_{letter.lower()}", 'UNKNOWN')
            metric = brevard_eval.get(f"metric_{letter.lower()}")
            if grade == 'FAIL':
                failing_letters.append(f"{letter} (metric={metric})")
        
        print(f"📋 Brevard failing letters in sprint order: {', '.join(failing_letters) if failing_letters else 'None'}")
        
        # Specific recommendations per sprint order
        brevard_c = brevard_eval.get("metric_c")
        brevard_d = brevard_eval.get("metric_d") 
        brevard_j = brevard_eval.get("metric_j")
        brevard_b = brevard_eval.get("metric_b")
        
        print("\n🎯 NEXT ACTIONS (Brevard Sprint Order):")
        if brevard_c is not None and brevard_c < 95:
            print(f"1. C/D ROOT CAUSE: C={brevard_c}% - PropertyOnion coverage audit, adopt clerk/official-records supplementary litmus")
        if brevard_j is not None and brevard_j < 95:
            print(f"2. J GENERATOR: J={brevard_j}% - Build bid_decisions pipeline (arv+max_bid+ml_score+5 factors)")
        if brevard_b is not None and brevard_b > 105:
            print(f"4. B RECONCILIATION: B={brevard_b}% - Fix verified_outcomes > closed_sold anomaly")
    
    # Summary
    total_counties = len(SHARD19_COUNTIES)
    evaluated_counties = sum(1 for data in county_data.values() if data.get('evaluation'))
    
    print(f"\n📈 Counties evaluated: {evaluated_counties}/{total_counties}")
    
    if evaluated_counties > 0:
        print("\n⚡ SESSION PRIORITIES (6-hour autonomous):")
        print("✅ Must apply SHIP-TO-MAIN mandate: all commits direct to main")
        print("✅ Must use ULTRALOOP protocol for verification")
        print("✅ Must run verification protocol after each fix")
        print("✅ Must apply Supabase migrations autonomously")
        print("✅ Evidence-Before-Claims: Execute → Verify → Read output → Compare to spec → THEN claim")

if __name__ == "__main__":
    main()