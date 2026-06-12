#!/usr/bin/env python3
"""
SHARD-8 County Status Verification
Check current A-J letter grades for indian_river, sumter, jackson, desoto, monroe

Usage:
  python scripts/verify_shard8_status.py
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

# Target counties for SHARD-8
SHARD8_COUNTIES = ['indian_river', 'sumter', 'jackson', 'desoto', 'monroe']

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
        pass_count = status.get('pass_count', 'N/A')
        loop_run = status.get('loop_run_id', 'Unknown')
        report.append(f"**Score**: {pass_count}/10")
        report.append(f"**Loop Run**: {loop_run}")
        report.append(f"**Last Updated**: {status.get('updated_at', 'Unknown')}")
    
    if evaluation:
        report.append("\n### Letter Grades:")
        letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']
        
        # Handle both list format and object format
        if isinstance(evaluation, list):
            # Convert list to dict for easier access
            eval_dict = {}
            for item in evaluation:
                if 'letter' in item:
                    eval_dict[item['letter']] = item
            
            for letter in letters:
                item = eval_dict.get(letter, {})
                pass_status = item.get('pass', False)
                metric = item.get('metric')
                
                status_icon = "✅ PASS" if pass_status else "❌ FAIL"
                metric_str = f" (metric={metric})" if metric is not None else ""
                
                report.append(f"**{letter}**: {status_icon}{metric_str}")
        else:
            # Object format fallback
            for letter in letters:
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
    print("\n" + "="*60)
    print("SHARD-8 COUNTY STATUS REPORT")
    print("="*60)
    
    for county, data in county_data.items():
        evaluation = data.get('evaluation')
        status = data.get('status')
        
        print(format_county_report(county, evaluation, status))
    
    # Summary
    print(f"\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    total_counties = len(SHARD8_COUNTIES)
    evaluated_counties = sum(1 for data in county_data.values() if data.get('evaluation'))
    
    print(f"Counties evaluated: {evaluated_counties}/{total_counties}")
    
    if evaluated_counties > 0:
        print("\nNext steps based on current status:")
        print("1. Focus on highest-leverage failing letters")
        print("2. Prioritize counties with existing infrastructure")
        print("3. Follow ship-to-main mandate - commit directly")

if __name__ == "__main__":
    main()