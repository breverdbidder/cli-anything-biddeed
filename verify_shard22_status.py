#!/usr/bin/env python3
"""
SHARD-22 County Status Verification - Run 22 Autonomous Session  
Check current A-J letter grades for charlotte, palm_beach, hendry, st_johns, hardee

Usage:
  python verify_shard22_status.py
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

# Target counties for SHARD-22 (Run 22) - updated from issue
SHARD22_COUNTIES = ['charlotte', 'palm_beach', 'hendry', 'st_johns', 'hardee']

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

def main():
    """Run the verification for all SHARD-22 counties"""
    print(f"=== SHARD-22 County Status Verification ===")
    print(f"Target counties: {', '.join(SHARD22_COUNTIES)}")
    print(f"Timestamp: {datetime.now()}")
    
    # Test connection first
    if not test_connection():
        print("❌ Cannot proceed without database connection")
        return
    
    print(f"\n=== County Evaluations ===")
    
    total_passes = 0
    county_scores = {}
    
    for county in SHARD22_COUNTIES:
        print(f"\n--- Evaluating {county} ---")
        evaluation = get_county_evaluation(county)
        
        if evaluation:
            formatted = format_evaluation(county, evaluation)
            print(formatted)
            
            # Count passes for this county
            county_pass_count = sum(1 for item in evaluation if item.get('pass', False))
            county_scores[county] = county_pass_count
            total_passes += county_pass_count
        else:
            print(f"❌ {county}: Failed to get evaluation")
            county_scores[county] = 0
    
    print(f"\n=== SHARD-22 Summary ===")
    print(f"Total passes across all counties: {total_passes}/50")
    for county, score in county_scores.items():
        print(f"  {county}: {score}/10")
    
    # According to the issue brief, priority targets are those with most failures
    sorted_counties = sorted(county_scores.items(), key=lambda x: x[1])
    print(f"\nPriority order (worst first): {[c for c, s in sorted_counties]}")

if __name__ == "__main__":
    main()