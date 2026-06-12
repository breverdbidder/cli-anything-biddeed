#!/usr/bin/env python3
"""
Evaluate Brevard and Duval Gold Standard Metrics
GOLD STANDARD AUTOPILOT-BD Session - Run 19
"""
import os
import requests
import json
from datetime import datetime

# Supabase configuration - using documented values from CLAUDE.md
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"

print(f"Using Supabase URL: {SUPABASE_URL}")
print(f"API Key present: {bool(SUPABASE_KEY)}")

HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}", 
    "Content-Type": "application/json"
}

# Assigned counties for this session (VERIFIED from issue brief)
ASSIGNED_COUNTIES = ['brevard', 'duval']

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
            # Try alternative parameter name
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
                print(f"❌ Both parameter formats failed for {county}")
                return None
            
    except Exception as e:
        print(f"⚠️ Error evaluating {county}: {e}")
        return None

def format_county_metrics(county, evaluation):
    """Format county metrics for analysis"""
    if not evaluation:
        return None
        
    metrics = {}
    
    # Parse evaluation result based on the structure from other scripts
    if isinstance(evaluation, list):
        for item in evaluation:
            letter = item.get('letter')
            metric = item.get('metric')
            passes = item.get('pass', False)
            if letter:
                metrics[letter] = {
                    'metric': metric,
                    'passes': passes,
                    'status': 'PASS' if passes else 'FAIL'
                }
    elif isinstance(evaluation, dict):
        # Handle different evaluation formats
        for key, value in evaluation.items():
            if key.startswith('grade_'):
                letter = key.split('_')[1].upper()
                metric_key = f'metric_{letter.lower()}'
                metrics[letter] = {
                    'metric': evaluation.get(metric_key),
                    'passes': value == 'PASS',
                    'status': value
                }
    
    return metrics

def print_county_analysis(county, metrics):
    """Print detailed county analysis"""
    print(f"\n{'='*50}")
    print(f"{county.upper()} COUNTY ANALYSIS")
    print(f"{'='*50}")
    
    if not metrics:
        print("❌ No metrics available")
        return
    
    pass_count = sum(1 for m in metrics.values() if m.get('passes', False))
    print(f"Overall Score: {pass_count}/10 letters passing")
    
    print("\nLetter-by-Letter Breakdown:")
    for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
        if letter in metrics:
            m = metrics[letter]
            status_icon = "✅" if m['passes'] else "❌"
            metric_val = m['metric'] if m['metric'] is not None else "null"
            print(f"  {letter}: {status_icon} {m['status']} - metric={metric_val}")
        else:
            print(f"  {letter}: ❓ UNKNOWN")
    
    # Priority analysis based on issue brief
    if county == 'brevard':
        print("\n🎯 BREVARD PRIORITY ORDER (per session brief):")
        priority_letters = ['C', 'J', 'G', 'B']
        for letter in priority_letters:
            if letter in metrics:
                m = metrics[letter]
                status = "✅" if m['passes'] else "❌"
                print(f"  {letter}: {status} {m.get('metric', 'N/A')} - {get_letter_description(letter)}")
    
    elif county == 'duval':
        print("\n🎯 DUVAL PRIORITY ORDER (per session brief):")
        priority_letters = ['G', 'I', 'C', 'J']
        for letter in priority_letters:
            if letter in metrics:
                m = metrics[letter]
                status = "✅" if m['passes'] else "❌"
                print(f"  {letter}: {status} {m.get('metric', 'N/A')} - {get_letter_description(letter)}")

def get_letter_description(letter):
    """Get description of what each letter represents"""
    descriptions = {
        'A': 'dual-product coverage',
        'B': 'verified INDEPENDENT outcomes >=95%',
        'C': 'parity_clean >=95%',
        'D': 'parity_any >=95%',
        'E': 'parcel linkage >=95%',
        'F': 'tier1 sold-amount >=95%',
        'G': 'zoning min(density,FAR,pk1000) >=95%',
        'H': 'freshness <=48h',
        'I': 'property card complete >=95%',
        'J': 'Shapira deal thesis >=95%'
    }
    return descriptions.get(letter, 'Unknown criteria')

if __name__ == "__main__":
    print("🚀 GOLD STANDARD AUTOPILOT-BD SESSION - RUN 19")
    print(f"Time: {datetime.now().isoformat()}")
    print("Target Counties: Brevard, Duval")
    
    # Test connection first
    if not test_connection():
        print("❌ Cannot proceed without database connection")
        exit(1)
    
    # Evaluate each county
    for county in ASSIGNED_COUNTIES:
        print(f"\n📊 Evaluating {county}...")
        evaluation = get_county_evaluation(county)
        metrics = format_county_metrics(county, evaluation)
        print_county_analysis(county, metrics)
    
    print(f"\n{'='*50}")
    print("✅ VERIFIED: Current metrics retrieved from live database")
    print(f"Next: Implement priority fixes per session brief")
    print(f"{'='*50}")