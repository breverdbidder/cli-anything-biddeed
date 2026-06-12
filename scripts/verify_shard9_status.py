#!/usr/bin/env python3
"""
SHARD-9 County Status Verification
Check current A-J letter grades for lee, alachua, nassau, dixie, taylor

Usage:
  python scripts/verify_shard9_status.py
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

# Target counties for SHARD-9
SHARD9_COUNTIES = ['lee', 'alachua', 'nassau', 'dixie', 'taylor']

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
    """Format a detailed county report with focus on SHARD-9 priorities"""
    report = [f"\n## {county.upper()} County Status"]
    
    if status:
        score = status.get('total_score', 'N/A')
        report.append(f"**Score**: {score}/10")
        report.append(f"**Last Updated**: {status.get('updated_at', 'Unknown')}")
        
        # Add specific context from issue brief
        if county == 'lee':
            report.append("**Current**: A✓ H✓ - Focus: C/D parity, J generator")
        elif county == 'alachua':
            report.append("**Current**: A✓ - Focus: H freshness, C/D parity")
        elif county == 'nassau':
            report.append("**Current**: A✓ - Focus: H freshness, C/D parity")
        elif county in ['dixie', 'taylor']:
            report.append("**Current**: All criteria failing - Full pipeline setup needed")
    
    if evaluation:
        report.append("\n### Letter Grades:")
        priority_letters = ['B', 'I', 'J']  # Critical three per brief
        
        for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
            grade_field = f"grade_{letter.lower()}"
            metric_field = f"metric_{letter.lower()}"
            
            grade = evaluation.get(grade_field, 'UNKNOWN')
            metric = evaluation.get(metric_field)
            
            status_icon = "✅ PASS" if grade == "PASS" else "❌ FAIL"
            priority_marker = " ⭐ CRITICAL" if letter in priority_letters else ""
            metric_str = f" (metric={metric})" if metric is not None else ""
            
            report.append(f"**{letter}**: {status_icon}{metric_str}{priority_marker}")
    
    return "\n".join(report)

def analyze_priorities(county_data):
    """Analyze and recommend priorities based on current status"""
    priorities = []
    
    for county, data in county_data.items():
        evaluation = data.get('evaluation', {})
        
        failing_letters = []
        for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
            grade = evaluation.get(f"grade_{letter.lower()}", 'FAIL')
            if grade != 'PASS':
                failing_letters.append(letter)
        
        if failing_letters:
            # Priority based on brief: C/D root cause → J generator → G hit list → B reconciliation
            priority_order = ['C', 'D', 'J', 'G', 'B', 'I', 'F', 'E', 'A', 'H']
            sorted_failing = sorted(failing_letters, key=lambda x: priority_order.index(x) if x in priority_order else 99)
            
            priorities.append({
                'county': county,
                'failing': sorted_failing,
                'priority_letter': sorted_failing[0] if sorted_failing else None
            })
    
    return priorities

def main():
    print("🔍 SHARD-9 County Status Verification")
    print(f"Target counties: {', '.join(SHARD9_COUNTIES)}")
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
    for county in SHARD9_COUNTIES:
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
    print("\n" + "="*60)
    print("SHARD-9 COUNTY STATUS REPORT")
    print("="*60)
    
    for county, data in county_data.items():
        evaluation = data.get('evaluation')
        status = data.get('status')
        
        print(format_county_report(county, evaluation, status))
    
    # Priority analysis
    priorities = analyze_priorities(county_data)
    
    print(f"\n" + "="*60)
    print("PRIORITY ANALYSIS")
    print("="*60)
    
    print("Based on BREVARD SPRINT ORDER:")
    print("1. C/D ROOT CAUSE - PropertyOnion coverage scenario")
    print("2. J GENERATOR - bid_decisions pipeline")
    print("3. G HIT LIST - zone_standards backfill")
    print("4. B RECONCILIATION - anomalous ratios >100%")
    
    print(f"\nCounty priorities:")
    for priority in priorities:
        county = priority['county']
        failing = priority['failing']
        next_letter = priority['priority_letter']
        
        print(f"**{county.upper()}**: {len(failing)} failing letters, next focus = {next_letter}")
        print(f"  Failing: {', '.join(failing)}")
    
    # Summary
    print(f"\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    total_counties = len(SHARD9_COUNTIES)
    evaluated_counties = sum(1 for data in county_data.values() if data.get('evaluation'))
    
    print(f"Counties evaluated: {evaluated_counties}/{total_counties}")
    
    if evaluated_counties > 0:
        print("\nNext steps per ULTRALOOP PROTOCOL:")
        print("1. Run /effort ultracode for audit orchestration")
        print("2. Focus on C/D root cause analysis first")
        print("3. Build J generator for deal completion")
        print("4. Ship directly to main branch")

if __name__ == "__main__":
    main()