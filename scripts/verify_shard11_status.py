#!/usr/bin/env python3
"""
SHARD-11 County Status Verification
Check current A-J letter grades for manatee, washington, miami_dade, gadsden, wakulla

Usage:
  python scripts/verify_shard11_status.py
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

# Target counties for SHARD-11
SHARD11_COUNTIES = ['manatee', 'washington', 'miami_dade', 'gadsden', 'wakulla']

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
        payload = {"county_slug_arg": county}
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
                "county_slug": f"eq.{county}",
                "select": "*",
                "order": "loop_run_id.desc",
                "limit": "1"
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
        pass_count = status.get('pass_count', 0)
        report.append(f"**Score**: {pass_count}/10")
        report.append(f"**Last Updated**: {status.get('updated_at', 'Unknown')}")
    
    if evaluation:
        report.append("\n### Letter Grades (Latest Evaluation):")
        for letter_data in evaluation:
            letter = letter_data.get('letter', 'Unknown')
            passed = letter_data.get('pass', False)
            metric = letter_data.get('metric')
            description = letter_data.get('description', '')
            
            status_icon = "✅ PASS" if passed else "❌ FAIL"
            metric_str = f" (metric={metric})" if metric is not None else ""
            
            report.append(f"**{letter}**: {status_icon}{metric_str}")
            if description and not passed:
                report.append(f"   └─ {description}")
    
    return "\n".join(report)

def analyze_leverage_opportunities(county_data):
    """Analyze which counties and letters offer the highest leverage"""
    print("\n🎯 LEVERAGE ANALYSIS")
    print("="*50)
    
    # Count failing letters per county
    county_failures = {}
    all_failures = {}
    
    for county, data in county_data.items():
        evaluation = data.get('evaluation', [])
        if not evaluation:
            print(f"❌ {county}: No evaluation data")
            continue
            
        failures = []
        for letter_data in evaluation:
            if not letter_data.get('pass', False):
                letter = letter_data.get('letter')
                failures.append(letter)
                
                if letter not in all_failures:
                    all_failures[letter] = []
                all_failures[letter].append(county)
        
        county_failures[county] = failures
        print(f"📊 {county}: {len(failures)} failing letters {failures}")
    
    print(f"\n📈 MOST COMMON FAILING LETTERS:")
    for letter, counties in sorted(all_failures.items(), key=lambda x: -len(x[1])):
        print(f"  {letter}: {len(counties)} counties ({', '.join(counties)})")
    
    return county_failures, all_failures

def main():
    print("🔍 SHARD-11 County Status Verification")
    print(f"Target counties: {', '.join(SHARD11_COUNTIES)}")
    print(f"Timestamp: {datetime.now().isoformat()}\n")
    
    # Print debug info about environment
    print(f"SUPABASE_URL: {SUPABASE_URL}")
    print(f"SUPABASE_KEY available: {'Yes' if SUPABASE_KEY else 'No'}")
    
    # Test connection first
    if not test_connection():
        print("❌ Database connection failed. Checking for environment variables...")
        print(f"Available env vars: {[k for k in os.environ.keys() if 'SUPABASE' in k or 'DB' in k]}")
        return False
    
    print("📊 Gathering county evaluations...\n")
    
    # Collect data for each county
    county_data = {}
    for county in SHARD11_COUNTIES:
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
    print("SHARD-11 COUNTY STATUS REPORT")
    print("="*60)
    
    for county, data in county_data.items():
        evaluation = data.get('evaluation')
        status = data.get('status')
        
        print(format_county_report(county, evaluation, status))
    
    # Leverage analysis
    analyze_leverage_opportunities(county_data)
    
    # Summary
    print(f"\n" + "="*60)
    print("SUMMARY & NEXT STEPS")
    print("="*60)
    
    total_counties = len(SHARD11_COUNTIES)
    evaluated_counties = sum(1 for data in county_data.values() if data.get('evaluation'))
    
    print(f"Counties evaluated: {evaluated_counties}/{total_counties}")
    
    if evaluated_counties > 0:
        print("\n🚀 GOLD STANDARD SESSION PRIORITIES:")
        print("1. Focus on highest-leverage failing letters (multiple counties)")
        print("2. Prioritize counties with existing data (avoid 0/10 unless quick wins)")
        print("3. Follow ship-to-main mandate - commit directly, no PRs")
        print("4. Wire all new code to execution (cron/workflows)")
        print("5. Verify metrics movement after each fix")
        print("6. Continue until ~5.5h budget consumed")
        print("7. Execute close-out verification protocol")
        
        return True
    else:
        print("❌ No counties successfully evaluated")
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print(f"\n✅ SHARD-11 verification completed at {datetime.now().isoformat()}")
    else:
        print(f"\n❌ SHARD-11 verification failed at {datetime.now().isoformat()}")