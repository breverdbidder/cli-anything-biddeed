#!/usr/bin/env python3
"""
SHARD-8 County Status Verification
Check current A-J letter grades for osceola, duval, nassau, desoto, monroe

Usage:
  python verify_shard8_status.py
"""
import os
import httpx
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

# Target counties for SHARD-8 (assigned counties from issue)
SHARD8_COUNTIES = ['osceola', 'duval', 'nassau', 'desoto', 'monroe']

def test_connection():
    """Test Supabase connection"""
    try:
        with httpx.Client() as client:
            response = client.get(f"{BASE}/audit_log", headers=HEADERS, params={"limit": "1"}, timeout=10)
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
        with httpx.Client() as client:
            response = client.post(
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
        with httpx.Client() as client:
            response = client.get(
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

def format_county_report(county, evaluation, status, metrics_from_issue):
    """Format a detailed county report with issue context"""
    report = [f"\n## {county.upper()} County Status"]
    
    # Add issue metrics for comparison
    if metrics_from_issue:
        report.append(f"**Issue Brief Metrics**: {metrics_from_issue}")
    
    if status:
        report.append(f"**Current Score**: {status.get('total_score', 'N/A')}/10")
        report.append(f"**Last Updated**: {status.get('updated_at', 'Unknown')}")
    
    if evaluation:
        report.append("\n### Letter Grades:")
        for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
            grade_field = f"grade_{letter.lower()}"
            metric_field = f"metric_{letter.lower()}"
            
            grade = evaluation.get(grade_field, 'UNKNOWN')
            metric = evaluation.get(metric_field)
            
            status_icon = "✅ PASS" if grade == "PASS" else "❌ FAIL"
            metric_str = f" (metric={metric})" if metric is not None else ""
            
            report.append(f"**{letter}**: {status_icon}{metric_str}")
    
    return "\n".join(report)

def main():
    print("🔍 SHARD-8 County Status Verification")
    print(f"Target counties: {', '.join(SHARD8_COUNTIES)}")
    print(f"Timestamp: {datetime.now().isoformat()}\n")
    
    # Issue brief metrics for comparison (from GitHub issue)
    issue_metrics = {
        'osceola': "2/10 - A PASS, B/C/D/E/F/G/I/J FAIL, H PASS",
        'duval': "1/10 - A PASS, B/C/D/E/F/G/I/J FAIL, H FAIL",
        'nassau': "1/10 - A PASS, B/C/D/E/F/G/I/J FAIL, H FAIL",
        'desoto': "0/10 - All metrics FAIL",
        'monroe': "0/10 - All metrics FAIL"
    }
    
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
    for county in SHARD8_COUNTIES:
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
    print("\n" + "="*70)
    print("SHARD-8 COUNTY STATUS REPORT")
    print("="*70)
    
    for county, data in county_data.items():
        evaluation = data.get('evaluation')
        status = data.get('status')
        issue_metric = issue_metrics.get(county, "No baseline provided")
        
        print(format_county_report(county, evaluation, status, issue_metric))
    
    # Summary
    print(f"\n" + "="*70)
    print("PRIORITY ANALYSIS FOR 6-HOUR SESSION")
    print("="*70)
    
    total_counties = len(SHARD8_COUNTIES)
    evaluated_counties = sum(1 for data in county_data.values() if data.get('evaluation'))
    
    print(f"Counties evaluated: {evaluated_counties}/{total_counties}")
    
    if evaluated_counties > 0:
        print("\nSprint Order (from CLAUDE.md brief):")
        print("1. DUVAL Priority: G+I substrate build (zoning districts + parcel zones)")
        print("2. BREVARD Priority: C/D root cause analysis (parity litmus fallback)")
        print("3. County-agnostic: J generator build (bid_decisions pipeline)")
        print("4. Work assigned shard counties based on highest leverage")
        print("5. ULTRALOOP verification after each fix")
    
    print("\nKey Protocol Requirements:")
    print("- SHIP TO MAIN mandate - commit directly, no side branches")
    print("- Evidence-before-claims - SQL proof required for all improvements")
    print("- ULTRALOOP audit procedures for all claims")
    print("- Session must run until ~5.5h elapsed, not exit early")

if __name__ == "__main__":
    main()