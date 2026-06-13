#!/usr/bin/env python3
"""
Simple baseline check for SHARD-20 counties: charlotte, citrus, broward
Using the same pattern as verify_shard1_status.py
"""
import os
import sys

# Check if requests is available
try:
    import requests
    print("✅ requests library available")
except ImportError:
    print("❌ requests library not available")
    sys.exit(1)

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")

print(f"Supabase URL: {SUPABASE_URL}")
print(f"API Key present: {bool(SUPABASE_KEY)}")
print(f"API Key length: {len(SUPABASE_KEY) if SUPABASE_KEY else 0}")

if not SUPABASE_KEY:
    print("❌ No Supabase API key found")
    print("Available env vars:", [k for k in os.environ.keys() if any(term in k.upper() for term in ['SUPA', 'KEY', 'TOKEN'])])
    sys.exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}", 
    "Content-Type": "application/json"
}

# SHARD-20 counties
COUNTIES = ['charlotte', 'citrus', 'broward']

def test_connection():
    """Test basic Supabase connection"""
    try:
        response = requests.get(f"{BASE}/audit_log", headers=HEADERS, params={"limit": "1"}, timeout=10)
        print(f"Connection test status: {response.status_code}")
        if response.status_code == 200:
            print("✅ Supabase connection successful")
            return True
        else:
            print(f"❌ Connection failed: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def get_county_evaluation(county):
    """Get evaluation for a specific county using pencil_dod_evaluate_county function"""
    print(f"\n--- Evaluating {county} ---")
    try:
        # Try the parameter name that works
        for param_name in ["county_slug_arg", "county_name", "county"]:
            payload = {param_name: county}
            print(f"Trying param: {param_name}={county}")
            
            response = requests.post(
                f"{BASE}/rpc/pencil_dod_evaluate_county", 
                headers=HEADERS, 
                json=payload,
                timeout=60
            )
            
            print(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Success with {param_name}")
                print(f"Result type: {type(result)}, length: {len(result) if isinstance(result, list) else 'N/A'}")
                return result
            else:
                print(f"❌ Failed with {param_name}: {response.text[:200]}")
        
        return None
        
    except Exception as e:
        print(f"❌ Error evaluating {county}: {e}")
        return None

def format_evaluation(county, evaluation):
    """Format the evaluation results for display"""
    if not evaluation:
        return f"{county}: ❌ No evaluation data"
    
    if not isinstance(evaluation, list):
        return f"{county}: ❌ Unexpected data format: {type(evaluation)}"
    
    letters = {}
    pass_count = 0
    
    for item in evaluation:
        if not isinstance(item, dict):
            continue
            
        letter = item.get('letter', '?')
        metric = item.get('metric')
        passes = item.get('pass', False)
        
        letters[letter] = {
            'metric': metric,
            'pass': passes
        }
        
        if passes:
            pass_count += 1
    
    result = f"\n## {county.upper()} ({pass_count}/10)\n"
    
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
    print("=== SHARD-20 BASELINE CHECK ===")
    print("Counties: charlotte, citrus, broward")
    
    # Test connection
    if not test_connection():
        print("❌ Cannot proceed without database connection")
        sys.exit(1)
    
    # Evaluate each county
    evaluations = {}
    
    for county in COUNTIES:
        evaluation = get_county_evaluation(county)
        evaluations[county] = evaluation
    
    # Display results
    print("\n" + "="*60)
    print("BASELINE EVALUATION RESULTS")
    print("="*60)
    
    for county in COUNTIES:
        evaluation = evaluations[county]
        formatted = format_evaluation(county, evaluation)
        print(formatted)
    
    print(f"\nTimestamp: {os.environ.get('GITHUB_RUN_ID', 'local')}")
    print("Baseline check complete.")

if __name__ == "__main__":
    main()