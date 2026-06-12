#!/usr/bin/env python3
"""
SHARD-8 County Status Verification - GOLD STANDARD CAMPAIGN
Check current A-J letter grades for: hillsborough, volusia, miami_dade, desoto, monroe

Usage:
  python scripts/verify_shard8_status.py
"""
import os
import requests
import json
from datetime import datetime

# Supabase configuration from CLAUDE.md
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}", 
    "Content-Type": "application/json"
}

# SHARD-8 assigned counties from briefing
SHARD8_COUNTIES = ['hillsborough', 'volusia', 'miami_dade', 'desoto', 'monroe']

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
    """Get evaluation using pencil_dod_evaluate_county function per briefing verification protocol"""
    try:
        # Updated per briefing: use county_slug_arg parameter
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

def format_county_status_from_briefing(county, evaluation):
    """Format county status matching briefing format - return pass count and letter details"""
    if not evaluation:
        return f"{county}: No evaluation data", []
    
    letters_status = []
    pass_count = 0
    
    if isinstance(evaluation, list):
        # Parse array response format from pencil_dod_evaluate_county
        for letter_data in evaluation:
            letter = letter_data.get('letter', '?')
            metric = letter_data.get('metric')
            pass_status = letter_data.get('pass')
            
            if pass_status:
                pass_count += 1
                status_str = f"{letter} PASS metric={metric}"
            else:
                status_str = f"{letter} FAIL metric={metric}"
            
            letters_status.append({
                'letter': letter,
                'pass': pass_status,
                'metric': metric,
                'status_str': status_str
            })
    
    return f"{county}: {pass_count}/10 PASS", letters_status

def identify_failing_letters_by_county(county_data):
    """Identify failing letters per county for priority targeting"""
    county_failures = {}
    
    for county, data in county_data.items():
        evaluation = data.get('evaluation')
        if not evaluation:
            county_failures[county] = []
            continue
        
        failing_letters = []
        
        if isinstance(evaluation, list):
            for letter_data in evaluation:
                letter = letter_data.get('letter', '?')
                pass_status = letter_data.get('pass')
                if not pass_status:
                    failing_letters.append(letter)
        
        county_failures[county] = failing_letters
    
    return county_failures

def analyze_shard8_priorities():
    """Analyze SHARD-8 priorities based on briefing data and current metrics"""
    print("📊 SHARD-8 PRIORITY ANALYSIS based on briefing:")
    print("- hillsborough: 2/10 PASS (A,H) - major C/D parity issues")
    print("- volusia: 2/10 PASS (A,H) - poor C/D matching")
    print("- miami_dade: 1/10 PASS (A only) - H failing at 248h")
    print("- desoto: 0/10 PASS - no data (fc=0, td=0)")
    print("- monroe: 0/10 PASS - no data (fc=0, td=0)")
    print()
    print("🎯 RECOMMENDED PRIORITY ORDER:")
    print("1. hillsborough + volusia (have auction data, need C/D/E fixes)")
    print("2. miami_dade (large dataset, needs freshness H + all criteria)")  
    print("3. desoto + monroe (need A-lane configuration first)")

def main():
    print("🔍 GOLD STANDARD SHARD-8 County Status Verification")
    print(f"Target counties: {', '.join(SHARD8_COUNTIES)}")
    print(f"Timestamp: {datetime.now().isoformat()}\n")
    
    # Print connection info
    print(f"SUPABASE_URL: {SUPABASE_URL}")
    print(f"SUPABASE_KEY available: {'Yes' if SUPABASE_KEY else 'No'}")
    
    # Test connection first
    if not test_connection():
        print("❌ Database connection failed. Checking environment...")
        available_vars = [k for k in os.environ.keys() if 'SUPABASE' in k or 'DB' in k]
        print(f"Available DB env vars: {available_vars}")
        print("⚠️ PROCEEDING WITH VERIFICATION ANYWAY (may use GitHub Actions secrets)")
        # Continue anyway - GitHub Actions may have secrets we can't see
    
    print("\n📊 Gathering SHARD-8 county evaluations (VERIFIED metrics)...\n")
    
    # Collect data for each county
    county_data = {}
    county_summaries = []
    
    for county in SHARD8_COUNTIES:
        print(f"🔍 Processing {county}...")
        
        # Get evaluation using function per briefing protocol
        evaluation = get_county_evaluation(county)
        
        county_data[county] = {
            'evaluation': evaluation
        }
        
        # Format status summary
        status_summary, letters_detail = format_county_status_from_briefing(county, evaluation)
        county_summaries.append(status_summary)
        
        # Show details
        if letters_detail:
            for letter_info in letters_detail:
                status_icon = "✅" if letter_info['pass'] else "❌"
                print(f"  {letter_info['letter']}: {status_icon} metric={letter_info['metric']}")
        else:
            print(f"  ⚠️ No evaluation data returned")
        print()
    
    # Summary report
    print("=" * 60)
    print("SHARD-8 CURRENT STATUS (VERIFIED)")
    print("=" * 60)
    for summary in county_summaries:
        print(summary)
    
    # Failing letters analysis
    print("\n" + "=" * 60)
    print("FAILING LETTERS ANALYSIS")
    print("=" * 60)
    
    failing_analysis = identify_failing_letters_by_county(county_data)
    for county, failing_letters in failing_analysis.items():
        if failing_letters:
            critical_failing = [l for l in failing_letters if l in ['B', 'I', 'J']]
            print(f"{county}: FAIL {failing_letters}")
            if critical_failing:
                print(f"  🎯 CRITICAL: {critical_failing}")
        else:
            print(f"{county}: All letters passing or no data")
    
    # Priority recommendations
    print("\n" + "=" * 60)
    print("SHARD-8 PRIORITY TARGETS")
    print("=" * 60)
    analyze_shard8_priorities()
    
    print("\n" + "=" * 60)
    print("NEXT ACTIONS")
    print("=" * 60)
    print("Per briefing SHIP-TO-MAIN mandate:")
    print("1. Target highest-leverage failing letters per county")
    print("2. Commit fixes directly to main (no side branches)")
    print("3. Verify with: SELECT public.pencil_dod_evaluate_county('<county>');")
    print("4. Continue until ~5.5h elapsed or significant progress made")
    print("5. Execute final verification protocol before session end")

if __name__ == "__main__":
    main()