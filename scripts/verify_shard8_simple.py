#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-8 Simple Verification Script using urllib only
Check current Gold Standard status for: hillsborough, alachua, nassau, desoto, monroe
"""
import os
import sys
import json
import urllib.request
import urllib.parse
from typing import Dict, List, Optional

# Setup Supabase connection using environment variables or hardcoded values  
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

print(f"Using Supabase URL: {SUPABASE_URL}")
print(f"API Key present: {bool(SUPABASE_KEY)}")

def make_request(url: str, method: str = "GET", data: Optional[Dict] = None) -> Dict:
    """Make a request to Supabase REST API using urllib"""
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        if method == "GET":
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as response:
                return {
                    "status_code": response.getcode(),
                    "data": json.loads(response.read().decode())
                }
        elif method == "POST":
            post_data = json.dumps(data).encode() if data else None
            req = urllib.request.Request(url, data=post_data, headers=headers)
            req.get_method = lambda: "POST"
            with urllib.request.urlopen(req, timeout=60) as response:
                return {
                    "status_code": response.getcode(),
                    "data": json.loads(response.read().decode())
                }
    except Exception as e:
        return {
            "status_code": 0,
            "error": str(e)
        }

def test_connection() -> bool:
    """Test basic connection to Supabase"""
    if not SUPABASE_KEY:
        print("❌ No Supabase API key found in environment variables")
        return False
        
    print("Testing database connection...")
    url = f"{SUPABASE_URL}/rest/v1/fl_counties?select=count&limit=1"
    result = make_request(url)
    
    if result["status_code"] == 200:
        print("✅ Database connection successful")
        return True
    else:
        print(f"❌ Database connection failed: {result.get('error', 'Unknown error')}")
        return False

def evaluate_county_current(county_slug: str) -> Optional[List[Dict]]:
    """Run the pencil_dod_evaluate_county function for a single county"""
    print(f"Evaluating county: {county_slug}")
    
    url = f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county"
    data = {"county_slug_arg": county_slug}
    
    result = make_request(url, method="POST", data=data)
    
    if result["status_code"] == 200:
        evaluation_data = result["data"]
        print(f"✅ County evaluation for {county_slug}:")
        
        if isinstance(evaluation_data, list) and len(evaluation_data) > 0:
            for letter_data in evaluation_data:
                letter = letter_data.get('letter', '?')
                metric = letter_data.get('metric')
                status = "✅" if letter_data.get('pass') else "❌"
                print(f"  {letter}: {status} {metric}")
        return evaluation_data
    else:
        print(f"❌ Failed to evaluate county {county_slug}: {result.get('error', 'Unknown error')}")
        return None

def analyze_priority_targets(evaluations: Dict[str, List[Dict]]) -> Dict[str, List[str]]:
    """Analyze evaluations and determine priority letters for each county"""
    priorities = {}
    
    # According to CLAUDE.md priority order: C/D root cause, J generator, G hit list, B reconciliation
    priority_letters = ['C', 'D', 'J', 'G', 'B']
    
    for county, evaluation in evaluations.items():
        if not evaluation:
            priorities[county] = ['A']  # Start with basic data if no evaluation
            continue
            
        failing_letters = []
        for letter_data in evaluation:
            if not letter_data.get('pass'):
                failing_letters.append(letter_data.get('letter'))
        
        # Sort by priority order
        county_priorities = []
        for letter in priority_letters:
            if letter in failing_letters:
                county_priorities.append(letter)
        
        # Add other failing letters 
        for letter in ['A', 'E', 'F', 'H', 'I']:
            if letter in failing_letters and letter not in county_priorities:
                county_priorities.append(letter)
                
        priorities[county] = county_priorities[:3]  # Top 3 priorities
    
    return priorities

if __name__ == "__main__":
    print("=== GOLD STANDARD SHARD-8 SIMPLE VERIFICATION ===")
    
    # Test connection first
    if not test_connection():
        print("❌ Cannot proceed without database connection")
        print("\nSuggested next steps:")
        print("1. Check if environment variables are properly set")
        print("2. Verify network connectivity") 
        print("3. Check API key permissions")
        sys.exit(1)
    
    print("\n=== Fresh County Evaluations ===")
    assigned_counties = ['hillsborough', 'alachua', 'nassau', 'desoto', 'monroe']
    county_evaluations = {}
    
    for county in assigned_counties:
        print(f"\n--- {county} ---")
        evaluation = evaluate_county_current(county)
        county_evaluations[county] = evaluation
    
    print("\n=== SHARD-8 Current Status Summary ===")
    for county in assigned_counties:
        if county in county_evaluations and county_evaluations[county]:
            pass_count = sum(1 for letter in county_evaluations[county] if letter.get('pass'))
            total_letters = len(county_evaluations[county])
            print(f"{county}: {pass_count}/{total_letters} letters passing")
        else:
            print(f"{county}: No evaluation data available")
    
    print("\n=== Priority Analysis ===")
    priorities = analyze_priority_targets(county_evaluations)
    for county, priority_letters in priorities.items():
        print(f"{county}: Priority letters to fix: {', '.join(priority_letters)}")
    
    print("\n=== Recommendations ===")
    print("Based on CLAUDE.md priority order:")
    print("1. C/D root cause - fix parity matching via clerk/official records")
    print("2. J generator - build bid_decisions generator with Shapira V14")
    print("3. G hit list - backfill zone_standards values from ordinance text") 
    print("4. B reconciliation - fix verified_outcomes vs closed_sold mismatch")
    print("5. Focus on counties with existing data first (hillsborough, alachua, nassau)")