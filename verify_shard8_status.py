#!/usr/bin/env python3
"""
SHARD-8 County Status Verification - GOLD STANDARD Campaign
Check current A-J letter grades for palm_beach, gilchrist, okeechobee, desoto, monroe

Usage:
  python verify_shard8_status.py
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

# Target counties for SHARD-8 (Run 28)
SHARD8_COUNTIES = ['palm_beach', 'gilchrist', 'okeechobee', 'desoto', 'monroe']

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
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                if result:  # If we got data, this param name worked
                    return result
            elif param_name == "county_name":  # Last attempt failed
                print(f"❌ Failed to evaluate {county}: {response.status_code} - {response.text}")
                return None
        
    except Exception as e:
        print(f"❌ Error evaluating {county}: {e}")
        return None
    
    return None

def format_evaluation(county, evaluation):
    """Format the evaluation results for display"""
    if not evaluation or len(evaluation) == 0:
        return f"{county}: ❌ No evaluation data"
    
    letters = {}
    pass_count = 0
    
    for item in evaluation:
        letter = item.get('letter', '?')
        metric = item.get('metric')
        passes = item.get('pass', False)
        
        letters[letter] = {
            'metric': metric,
            'pass': passes
        }
        
        if passes:
            pass_count += 1
    
    result = f"\n## {county} ({pass_count}/10)\n"
    
    # Order by letter A-J
    for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
        if letter in letters:
            status = "PASS" if letters[letter]['pass'] else "FAIL"
            metric = letters[letter]['metric']
            emoji = "✅" if letters[letter]['pass'] else "❌"
            result += f"    {letter} {emoji} {status} metric={metric}\n"
        else:
            result += f"    {letter} ❌ FAIL metric=null\n"
    
    return result

def get_current_metrics_from_issue():
    """Parse the current metrics from the issue description"""
    metrics = {
        'palm_beach': {'pass_count': 2, 'status': 'A PASS metric=8591, H PASS metric=23.0'},
        'gilchrist': {'pass_count': 1, 'status': 'A PASS metric=2, H FAIL metric=421.0'},
        'okeechobee': {'pass_count': 1, 'status': 'A PASS metric=164, H FAIL metric=421.0'},
        'desoto': {'pass_count': 0, 'status': 'All FAIL - no data ingested'},
        'monroe': {'pass_count': 0, 'status': 'All FAIL - no data ingested'}
    }
    return metrics

def main():
    print("=== SHARD-8 County Status Verification ===")
    print(f"Counties: {', '.join(SHARD8_COUNTIES)}")
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    
    if not SUPABASE_KEY:
        print("❌ No Supabase API key found in environment")
        return 1
    
    # Test connection
    if not test_connection():
        return 1
    
    print("\n=== BEFORE Evaluations ===")
    
    # Evaluate each county
    all_results = {}
    total_pass = 0
    
    for county in SHARD8_COUNTIES:
        print(f"\nEvaluating {county}...")
        evaluation = get_county_evaluation(county)
        if evaluation:
            formatted = format_evaluation(county, evaluation)
            print(formatted)
            all_results[county] = evaluation
            
            # Count passes for this county
            county_passes = sum(1 for item in evaluation if item.get('pass', False))
            total_pass += county_passes
        else:
            print(f"❌ Failed to evaluate {county}")
    
    print("\n=== SUMMARY ===")
    print(f"Total counties evaluated: {len(all_results)}/{len(SHARD8_COUNTIES)}")
    print(f"Total letters passing: {total_pass}/{len(SHARD8_COUNTIES) * 10}")
    if len(SHARD8_COUNTIES) > 0:
        print(f"Overall completion: {total_pass/(len(SHARD8_COUNTIES) * 10)*100:.1f}%")
    
    # Show current issue metrics for comparison
    print("\n=== ISSUE BASELINE (for comparison) ===")
    issue_metrics = get_current_metrics_from_issue()
    for county, data in issue_metrics.items():
        print(f"{county}: {data['pass_count']}/10 - {data['status']}")
    
    return 0

if __name__ == "__main__":
    exit(main())