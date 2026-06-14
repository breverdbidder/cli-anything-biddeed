#!/usr/bin/env python3
"""
Quick verification script to check current status for brevard and duval counties
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

TARGET_COUNTIES = ['brevard', 'duval']

def test_connection():
    """Test Supabase connection"""
    if not SUPABASE_KEY:
        print("❌ No SUPABASE_KEY found in environment")
        return False
        
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

def format_county_report(county, evaluation):
    """Format a detailed county report"""
    report = [f"\n## {county.upper()} County Current Status (VERIFIED)"]
    
    if evaluation:
        report.append("### Letter Metrics:")
        for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
            grade_field = f"grade_{letter.lower()}"
            metric_field = f"metric_{letter.lower()}"
            
            grade = evaluation.get(grade_field, 'UNKNOWN')
            metric = evaluation.get(metric_field, 'N/A')
            
            if grade == 'PASS':
                status = "✅ PASS"
            elif grade == 'FAIL':
                status = "❌ FAIL"
            else:
                status = f"⚠️ {grade}"
                
            report.append(f"- **{letter}**: {status} (metric={metric})")
    else:
        report.append("❌ No evaluation data available")
    
    return "\n".join(report)

def main():
    print("🔍 Checking current status for brevard and duval counties...")
    print(f"📅 Timestamp: {datetime.now().isoformat()}")
    
    if not test_connection():
        print("❌ Cannot connect to Supabase. Exiting.")
        return 1
    
    all_results = {}
    
    for county in TARGET_COUNTIES:
        print(f"\n📊 Evaluating {county}...")
        evaluation = get_county_evaluation(county)
        all_results[county] = evaluation
        print(format_county_report(county, evaluation))
    
    # Summary
    print("\n" + "="*50)
    print("SUMMARY FOR SHARD (brevard, duval)")
    print("="*50)
    
    for county in TARGET_COUNTIES:
        eval_data = all_results[county]
        if eval_data:
            pass_count = sum(1 for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J'] 
                           if eval_data.get(f"grade_{letter.lower()}") == 'PASS')
            print(f"**{county}**: {pass_count}/10 PASS")
        else:
            print(f"**{county}**: NO DATA")
    
    return 0

if __name__ == "__main__":
    exit(main())