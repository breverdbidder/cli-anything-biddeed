#!/usr/bin/env python3
"""
Brevard + Duval County Status Verification
Check current A-J letter grades for assigned counties in this session

Usage:
  python scripts/verify_brevard_duval_status.py
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

# Target counties for this session (per issue assignment)
TARGET_COUNTIES = ['brevard', 'duval']

def test_connection():
    """Test Supabase connection"""
    try:
        response = requests.get(f"{BASE}/fl_counties", headers=HEADERS, params={"limit": "1"}, timeout=10)
        if response.status_code == 200:
            print("✅ Supabase connection successful")
            return True
        else:
            print(f"❌ Connection failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def evaluate_county_current(county_slug):
    """Run pencil_dod_evaluate_county function for a county"""
    try:
        # Use RPC call with correct parameter name per issue text
        payload = {"county_slug_arg": county_slug}
        response = requests.post(
            f"{BASE}/rpc/pencil_dod_evaluate_county", 
            headers=HEADERS, 
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"⚠️ Failed to evaluate {county_slug}: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"⚠️ Error evaluating {county_slug}: {e}")
        return None

def format_county_report(county, evaluation_result):
    """Format a detailed county report from pencil_dod_evaluate_county result"""
    report = [f"\n## {county.upper()} County Status"]
    
    if evaluation_result and isinstance(evaluation_result, list):
        report.append("\n### Letter Grades:")
        passing_count = 0
        
        for letter_data in evaluation_result:
            letter = letter_data.get('letter', '?')
            metric = letter_data.get('metric', 'N/A')
            is_pass = letter_data.get('pass', False)
            
            if is_pass:
                passing_count += 1
            
            status_icon = "✅ PASS" if is_pass else "❌ FAIL"
            metric_str = f" metric={metric}"
            
            report.append(f"**{letter}**: {status_icon}{metric_str}")
        
        report.append(f"\n**Overall**: {passing_count}/10 letters passing")
    else:
        report.append("⚠️ No evaluation data available")
    
    return "\n".join(report)

def main():
    print("🔍 Brevard + Duval Counties Status Verification")
    print(f"Target counties: {', '.join(TARGET_COUNTIES)}")
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
    for county in TARGET_COUNTIES:
        print(f"Processing {county}...")
        
        # Get evaluation using function (fresh evaluation)
        evaluation = evaluate_county_current(county)
        
        county_data[county] = {
            'evaluation': evaluation
        }
    
    # Generate reports
    print("\n" + "="*60)
    print("BREVARD + DUVAL COUNTY STATUS REPORT")
    print("="*60)
    
    for county, data in county_data.items():
        evaluation = data.get('evaluation')
        print(format_county_report(county, evaluation))
    
    # Summary with priority order from issue
    print(f"\n" + "="*60)
    print("PRIORITY ORDER (per issue)")
    print("="*60)
    
    print("BREVARD SPRINT ORDER:")
    print("1. C/D ROOT CAUSE — numerators frozen, investigate PropertyOnion coverage")
    print("2. J GENERATOR — build bid_decisions to evaluator contract")  
    print("3. G HIT LIST — verify zone_standards for ~15 districts")
    print("4. B RECONCILIATION — verified=8547 > closed_sold=6373 anomaly")
    
    print("\nDUVAL SPRINT ORDER:")
    print("1. G+I SUBSTRATE BUILD — populate parcel_zones and zoning_districts")
    print("2. C/D ROOT CAUSE — same PropertyOnion coverage issue as Brevard")
    print("3. J GENERATOR — county-agnostic, check if brevard built it first")
    print("4. B RECONCILIATION — 110.2% anomaly, same refuter treatment")
    
    total_counties = len(TARGET_COUNTIES)
    evaluated_counties = sum(1 for data in county_data.values() if data.get('evaluation'))
    
    print(f"\nCounties evaluated: {evaluated_counties}/{total_counties}")
    print("Next: Execute highest priority fixes per county")

if __name__ == "__main__":
    main()