#!/usr/bin/env python3
"""
SHARD-30 County Status Verification - Run 30 Autonomous Session
Check current A-J letter grades for charlotte, volusia, jackson, seminole, hardee

Usage:
  python verify_shard30_status.py
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

# Target counties for SHARD-30 (my assigned counties)
SHARD30_COUNTIES = ['charlotte', 'volusia', 'jackson', 'seminole', 'hardee']

def test_connection():
    """Test Supabase connection"""
    if not SUPABASE_KEY:
        print("❌ No Supabase API key found in environment")
        print("This is expected in Claude Code environment without explicit credentials")
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
        payload = {"county_slug": county}
        response = requests.post(
            f"{BASE}/rpc/pencil_dod_evaluate_county", 
            headers=HEADERS, 
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            return result
        else:
            print(f"❌ Failed to evaluate {county}: {response.status_code} - {response.text}")
            return None
        
    except Exception as e:
        print(f"❌ Error evaluating {county}: {e}")
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
    print("=== SHARD-30 County Status Verification ===")
    print(f"Counties: {', '.join(SHARD30_COUNTIES)}")
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    
    # Test connection
    if not test_connection():
        print("\n📊 FALLBACK: Using briefing data for analysis...")
        
        # Use briefing data if no database connection
        briefing_data = {
            'charlotte': {'score': 3, 'failing': ['B', 'C', 'E', 'F', 'G', 'I', 'J']},
            'volusia': {'score': 2, 'failing': ['B', 'C', 'D', 'E', 'F', 'G', 'I', 'J']},
            'jackson': {'score': 1, 'failing': ['B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']},
            'seminole': {'score': 1, 'failing': ['B', 'C', 'D', 'F', 'G', 'H', 'I', 'J']}, 
            'hardee': {'score': 0, 'failing': ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']}
        }
        
        print("\n=== ANALYSIS FROM BRIEFING ===")
        
        # Fleet-wide failing letters
        all_failing = set()
        for county_data in briefing_data.values():
            all_failing.update(county_data['failing'])
        
        print(f"\n📊 FLEET-WIDE FAILING LETTERS: {sorted(all_failing)}")
        
        # Priority analysis
        failing_counts = {}
        for county, data in briefing_data.items():
            for letter in data['failing']:
                failing_counts[letter] = failing_counts.get(letter, 0) + 1
        
        print(f"\n🎯 HIGHEST IMPACT LETTERS (by county count):")
        for letter, count in sorted(failing_counts.items(), key=lambda x: x[1], reverse=True):
            counties = [county for county, data in briefing_data.items() if letter in data['failing']]
            print(f"   {letter}: {count}/5 counties failing - {counties}")
        
        print(f"\n📝 RECOMMENDED SESSION PLAN:")
        print(f"1. **J GENERATOR** - all 5 counties fail (highest impact)")
        print(f"2. **B RECONCILIATION** - all 5 counties fail (verified outcomes)")  
        print(f"3. **G/I SUBSTRATE** - all 5 counties fail (zoning + property cards)")
        print(f"4. **C/D PARITY** - 4-5 counties fail (matching issues)")
        print(f"5. **H FRESHNESS** - jackson (433h), seminole (289h) exceed SLA")
        print(f"6. **E LINKAGE** - charlotte (43.8%), volusia (58.8%), jackson (46.0%)")
        print(f"7. **F TIER1** - low percentages across all counties")
        
        return 0
        
    print("\n=== BEFORE Evaluations ===")
    
    # Evaluate each county
    all_results = {}
    total_pass = 0
    
    for county in SHARD30_COUNTIES:
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
    print(f"Total counties evaluated: {len(all_results)}/{len(SHARD30_COUNTIES)}")
    print(f"Total letters passing: {total_pass}/{len(SHARD30_COUNTIES) * 10}")
    print(f"Overall completion: {total_pass/(len(SHARD30_COUNTIES) * 10)*100:.1f}%")
    
    return 0

if __name__ == "__main__":
    exit(main())