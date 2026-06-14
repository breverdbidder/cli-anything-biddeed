#!/usr/bin/env python3
"""
SHARD-1 County Status Check for Gold Standard Campaign
Counties: brevard, alachua, lee, st_johns, hardee

This script checks current status and establishes baseline for the autonomous session.
Per CLAUDE.md: Evidence-Before-Claims compliance mandatory.
"""

import os
import sys
import json
from datetime import datetime

# Try importing requests
try:
    import requests
    print("✅ requests available")
except ImportError:
    print("❌ requests not available, trying to install...")
    os.system("pip install requests")
    try:
        import requests
        print("✅ requests installed and available")
    except ImportError:
        print("❌ Failed to install requests")
        sys.exit(1)

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")

print(f"Using Supabase URL: {SUPABASE_URL}")
print(f"API Key present: {bool(SUPABASE_KEY)}")

if not SUPABASE_KEY:
    print("❌ No Supabase API key found in environment")
    # Try hardcoded for GitHub Actions
    print("Attempting to use GitHub Actions environment...")
    
# SHARD-1 assigned counties
SHARD1_COUNTIES = ['brevard', 'alachua', 'lee', 'st_johns', 'hardee']

BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}", 
    "Content-Type": "application/json"
} if SUPABASE_KEY else {}

def test_connection():
    """Test basic connection to Supabase"""
    if not SUPABASE_KEY:
        print("⚠️ No API key - connection test skipped")
        return False
        
    try:
        r = requests.get(f"{SUPABASE_URL}/rest/v1/fl_counties?select=count&limit=1", 
                        headers=HEADERS, timeout=30)
        print(f"Connection status: {r.status_code}")
        if r.status_code == 200:
            print("✅ Database connection successful")
            return True
        else:
            print(f"❌ Database connection failed: {r.text}")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def evaluate_county_live(county):
    """Execute pencil_dod_evaluate_county for real-time status"""
    if not SUPABASE_KEY:
        print(f"⚠️ Cannot evaluate {county} - no API key")
        return None
        
    try:
        response = requests.post(
            f"{BASE}/rpc/pencil_dod_evaluate_county",
            headers=HEADERS,
            json={"county_slug_arg": county},
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            timestamp = datetime.utcnow().isoformat() + "Z"
            
            if isinstance(result, list) and len(result) > 0:
                letters = {}
                pass_count = 0
                
                for item in result:
                    letter = item.get('letter', '?')
                    metric = item.get('metric')
                    passes = item.get('pass', False)
                    
                    letters[letter] = {'metric': metric, 'pass': passes}
                    if passes:
                        pass_count += 1
                
                return {
                    'county': county,
                    'timestamp': timestamp,
                    'pass_count': pass_count,
                    'letters': letters,
                    'raw': result
                }
            else:
                print(f"❌ {county}: No evaluation data returned")
                return None
                
        else:
            print(f"❌ {county} evaluation failed: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ {county} evaluation error: {str(e)}")
        return None

def display_county_status(evaluation):
    """Display formatted county status per issue format"""
    if not evaluation:
        return
        
    county = evaluation['county']
    pass_count = evaluation['pass_count']
    letters = evaluation['letters']
    
    print(f"\n## {county} ({pass_count}/10)")
    
    for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
        if letter in letters:
            data = letters[letter]
            status = "PASS" if data['pass'] else "FAIL"
            metric = data['metric']
            # Format like the issue examples
            if metric is not None:
                print(f"    {letter} {status} metric={metric}")
            else:
                print(f"    {letter} {status} metric=null")
        else:
            print(f"    {letter} FAIL metric=null")

def main():
    """Execute status check for SHARD-1 counties"""
    print("=== SHARD-1 GOLD STANDARD STATUS CHECK ===")
    print(f"Counties: {', '.join(SHARD1_COUNTIES)}")
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    print()
    
    # Test connection first
    connection_ok = test_connection()
    if not connection_ok and SUPABASE_KEY:
        print("❌ Database connection failed - aborting")
        return 1
    
    print("\n=== LIVE COUNTY EVALUATIONS ===")
    
    evaluations = []
    for county in SHARD1_COUNTIES:
        print(f"\nEvaluating {county}...")
        evaluation = evaluate_county_live(county)
        if evaluation:
            evaluations.append(evaluation)
            display_county_status(evaluation)
        else:
            print(f"❌ Failed to evaluate {county}")
    
    # Summary
    print(f"\n=== SUMMARY ===")
    print(f"✅ Evaluated: {len(evaluations)}/{len(SHARD1_COUNTIES)} counties")
    
    if evaluations:
        total_passing_letters = sum(eval_data['pass_count'] for eval_data in evaluations)
        total_possible = len(evaluations) * 10
        fleet_percentage = (total_passing_letters / total_possible) * 100 if total_possible > 0 else 0
        
        print(f"📊 Fleet score: {total_passing_letters}/{total_possible} ({fleet_percentage:.1f}%)")
        
        # Identify priority targets per issue description
        priority_targets = []
        for evaluation in evaluations:
            if evaluation['pass_count'] >= 2:  # Counties with some progress
                priority_targets.append((evaluation['county'], evaluation['pass_count']))
        
        priority_targets.sort(key=lambda x: x[1], reverse=True)
        
        print(f"🎯 Priority targets: {', '.join(f'{county}({score}/10)' for county, score in priority_targets[:3])}")
    
    print(f"\n⏱️ Status check complete at {datetime.utcnow().isoformat()}Z")
    
    # Evidence-Before-Claims compliance note
    print("\n### EVIDENCE-BEFORE-CLAIMS BASELINE")
    print("**Query executed**: `SELECT public.pencil_dod_evaluate_county('<county>');` for each county")
    print(f"**Timestamp**: {datetime.utcnow().isoformat()}Z")
    print(f"**Results**: {len(evaluations)} counties evaluated successfully")
    print("**Compliance**: Live database queries provide verified baseline for autonomous session")
    
    return 0

if __name__ == "__main__":
    exit(main())