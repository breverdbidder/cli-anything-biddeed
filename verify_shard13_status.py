#!/usr/bin/env python3
"""
SHARD-13 County Status Verification - Run 20 Autonomous Session  
Check current A-J letter grades for orange, collier, pinellas, gulf

Usage:
  python verify_shard13_status.py
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

# Target counties for SHARD-13 (Run 20)
SHARD13_COUNTIES = ['orange', 'collier', 'pinellas', 'gulf']

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
        # Use RPC call to the evaluation function - try both parameter patterns
        for param_name in ["county_slug_arg", "county_name"]:
            payload = {param_name: county}
            response = requests.post(
                f"{BASE}/rpc/pencil_dod_evaluate_county", 
                headers=HEADERS, 
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result:  # If we got data, this parameter worked
                    return result
            else:
                print(f"  Warning: {param_name} failed with {response.status_code}")
        
        # If neither parameter pattern worked
        print(f"❌ Failed to evaluate {county} with either parameter pattern")
        return None
        
    except Exception as e:
        print(f"❌ Error evaluating {county}: {e}")
        return None

def format_county_status(county, evaluation):
    """Format county evaluation into readable status"""
    if not evaluation:
        return f"{county}: ❌ No evaluation data"
    
    letters = {}
    pass_count = 0
    
    # Parse evaluation results
    if isinstance(evaluation, list):
        for item in evaluation:
            if isinstance(item, dict):
                letter = item.get('letter', '?')
                metric = item.get('metric')
                passed = item.get('pass', False)
                letters[letter] = {
                    'metric': metric,
                    'pass': passed
                }
                if passed:
                    pass_count += 1
    
    # Format output
    status_line = f"\n## {county} ({pass_count}/10)"
    for letter in 'ABCDEFGHIJ':
        if letter in letters:
            data = letters[letter]
            status = "PASS" if data['pass'] else "FAIL"
            metric = data['metric'] if data['metric'] is not None else 'null'
            status_line += f"\n    {letter} {status} metric={metric}"
        else:
            status_line += f"\n    {letter} FAIL metric=null"
    
    return status_line

def main():
    """Main verification function"""
    print("=== SHARD-13 County Status Verification ===")
    print(f"Target counties: {', '.join(SHARD13_COUNTIES)}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Test connection first
    if not test_connection():
        print("❌ Cannot proceed without database connection")
        return False
    
    # Check API key
    if not SUPABASE_KEY:
        print("❌ No Supabase API key found in environment")
        return False
    
    print("\n=== County Evaluations ===")
    
    all_results = {}
    for county in SHARD13_COUNTIES:
        print(f"\nEvaluating {county}...")
        evaluation = get_county_evaluation(county)
        all_results[county] = evaluation
        print(format_county_status(county, evaluation))
    
    # Summary
    print("\n=== Summary ===")
    total_counties = len(SHARD13_COUNTIES)
    working_counties = sum(1 for v in all_results.values() if v is not None)
    
    print(f"Counties evaluated: {working_counties}/{total_counties}")
    
    # Get pass counts
    for county in SHARD13_COUNTIES:
        evaluation = all_results[county]
        if evaluation:
            pass_count = sum(1 for item in evaluation if item.get('pass', False))
            print(f"{county}: {pass_count}/10 letters passing")
    
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)