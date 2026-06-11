#!/usr/bin/env python3
"""
SHARD-2 County Status Verification
Check current A-J letter grades for brevard, putnam, flagler, santa_rosa, holmes

Usage:
  python scripts/verify_shard2_status.py
"""
import os
import requests
import json
from datetime import datetime

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}", 
    "Content-Type": "application/json"
}

# Target counties for SHARD-2
SHARD2_COUNTIES = ['brevard', 'putnam', 'flagler', 'santa_rosa', 'holmes']

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
        # Use RPC call to the evaluation function with correct parameter name
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
        report.append(f"**Score**: {status.get('pass_count', 'N/A')}/10")
        report.append(f"**Last Updated**: {status.get('updated_at', 'Unknown')}")
    
    if evaluation and isinstance(evaluation, list):
        report.append("\n### Letter Grades:")
        for item in evaluation:
            letter = item.get('letter', '?')
            metric = item.get('metric')
            passed = item.get('pass', False)
            
            status_icon = "✅ PASS" if passed else "❌ FAIL" 
            metric_str = f" (metric={metric})" if metric is not None else ""
            
            report.append(f"**{letter}**: {status_icon}{metric_str}")
    
    return "\n".join(report)

def main():
    print("🔍 SHARD-2 County Status Verification")
    print(f"Target counties: {', '.join(SHARD2_COUNTIES)}")
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
    for county in SHARD2_COUNTIES:
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
    print("SHARD-2 COUNTY STATUS REPORT")
    print("="*60)
    
    for county, data in county_data.items():
        evaluation = data.get('evaluation')
        status = data.get('status')
        
        print(format_county_report(county, evaluation, status))
    
    # Summary and Next Steps Analysis
    print(f"\n" + "="*60)
    print("SUMMARY & PRIORITY ANALYSIS")
    print("="*60)
    
    total_counties = len(SHARD2_COUNTIES)
    evaluated_counties = sum(1 for data in county_data.values() if data.get('evaluation'))
    
    print(f"Counties evaluated: {evaluated_counties}/{total_counties}")
    
    if evaluated_counties > 0:
        print("\nPriority Analysis (Based on Issue #7530):")
        print("1. **HIGHEST PRIORITY**: Brevard B+F pipeline - AcclaimWeb endpoint verification")
        print("2. Focus on letters with highest leverage (B, I, J are critical)")
        print("3. Ship directly to main - no side branches or PRs")
        print("4. Verify metrics movement with SQL after each change")
        
        # Analyze which counties need which letters
        priority_work = []
        for county, data in county_data.items():
            evaluation = data.get('evaluation')
            if evaluation:
                failing_letters = []
                for item in evaluation:
                    if not item.get('pass', False):
                        failing_letters.append(item.get('letter'))
                
                if failing_letters:
                    priority_work.append((county, failing_letters))
        
        if priority_work:
            print(f"\nFailing Letters by County:")
            for county, letters in priority_work:
                print(f"  {county}: {', '.join(letters)}")

if __name__ == "__main__":
    main()