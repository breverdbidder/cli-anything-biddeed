#!/usr/bin/env python3
"""
SHARD-19 County Status Verification  
Check current A-J letter grades for charlotte, citrus, broward
Run 19 baseline metrics collection per autonomous session brief

Usage:
  python scripts/verify_shard19_status.py
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

# Target counties for SHARD-19 Run 19
SHARD19_COUNTIES = ['charlotte', 'citrus', 'broward']

# Expected metrics from issue brief for verification
EXPECTED_METRICS = {
    'charlotte': {
        'score': '3/10',
        'status': 'A✅ B❌null C❌10.1% D✅97.4% E❌43.8% F❌2.1% G❌null H✅22.7h I❌null J❌0.0%'
    },
    'citrus': {
        'score': '3/10', 
        'status': 'A✅ B❌null C❌9.5% D❌75.3% E✅95.3% F❌6.1% G❌null H✅10.3h I❌null J❌0.0%'
    },
    'broward': {
        'score': '2/10',
        'status': 'A✅ B❌null C❌19.4% D❌47.7% E❌20.6% F❌2.5% G❌null H✅34.3h I❌null J❌0.0%'
    }
}

def test_connection():
    """Test Supabase connection with statement timeout override per CLAUDE.md"""
    try:
        # Set unlimited timeout per CLAUDE.md directive
        timeout_payload = {"sql": "SET statement_timeout = 0;"}
        timeout_response = requests.post(
            f"{BASE}/rpc/exec", 
            headers=HEADERS, 
            json=timeout_payload,
            timeout=10
        )
        if timeout_response.status_code != 200:
            print("⚠️ Could not set unlimited timeout, proceeding anyway")
        
        response = requests.get(f"{BASE}/fl_counties", headers=HEADERS, params={"limit": "1"}, timeout=10)
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
        # Use the correct parameter name from the brief
        payload = {"county_slug_arg": county}
        response = requests.post(
            f"{BASE}/rpc/pencil_dod_evaluate_county", 
            headers=HEADERS, 
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ County evaluation successful for {county}")
            
            # Log individual letter results for verification
            if isinstance(result, list):
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    status = "✅" if letter_data.get('pass') else "❌"
                    print(f"  {county} {letter}: {status} {metric}")
            
            return result
        else:
            print(f"⚠️ Failed to evaluate {county}: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"⚠️ Error evaluating {county}: {e}")
        return None

def get_gold_standard_loop_status():
    """Get the latest gold_standard_loop run results"""
    try:
        response = requests.post(
            f"{BASE}/rpc/gold_standard_loop",
            headers=HEADERS,
            json={},
            timeout=120
        )
        
        if response.status_code == 200:
            print("✅ Gold standard loop completed")
            return response.json()
        else:
            print(f"⚠️ Gold standard loop failed: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"⚠️ Error running gold standard loop: {e}")
        return None

def get_multi_county_auctions_counts():
    """Get auction counts for verification of A/H letters"""
    auction_counts = {}
    
    for county in SHARD19_COUNTIES:
        try:
            response = requests.get(
                f"{BASE}/multi_county_auctions",
                headers=HEADERS,
                params={
                    "county": f"eq.{county}",
                    "select": "count"
                },
                timeout=30
            )
            
            if response.status_code == 200:
                count = len(response.json()) if response.headers.get('content-range') else 0
                auction_counts[county] = count
                print(f"{county}: {count} auctions in database")
            else:
                print(f"⚠️ Failed to get auction count for {county}")
                auction_counts[county] = 0
                
        except Exception as e:
            print(f"⚠️ Error getting auction count for {county}: {e}")
            auction_counts[county] = 0
    
    return auction_counts

def analyze_baseline_vs_expected():
    """Compare current metrics against expected metrics from issue brief"""
    print("\n🔍 BASELINE vs EXPECTED ANALYSIS")
    print("="*50)
    
    for county in SHARD19_COUNTIES:
        expected = EXPECTED_METRICS.get(county, {})
        print(f"\n{county.upper()}:")
        print(f"  Expected: {expected.get('score')} - {expected.get('status')}")
        print(f"  Current:  [Getting fresh evaluation...]")
        
        # Get fresh evaluation to compare
        evaluation = get_county_evaluation(county)
        
        if evaluation:
            # Count passes
            passes = 0
            if isinstance(evaluation, list):
                passes = sum(1 for item in evaluation if item.get('pass'))
            elif isinstance(evaluation, dict):
                passes = sum(1 for k, v in evaluation.items() if k.startswith('grade_') and v == 'PASS')
            
            print(f"  Verified: {passes}/10")
            
            # Flag major deviations
            expected_score = expected.get('score', '0/10')
            expected_passes = int(expected_score.split('/')[0]) if '/' in expected_score else 0
            
            if passes != expected_passes:
                print(f"  ⚠️ DEVIATION: Expected {expected_passes}, got {passes}")
            else:
                print(f"  ✅ MATCHES expected baseline")

def format_county_report(county, evaluation):
    """Format a detailed county report"""
    report = [f"\n## {county.upper()} County Status"]
    
    if evaluation:
        if isinstance(evaluation, list):
            # New format: list of letter results
            passes = sum(1 for item in evaluation if item.get('pass'))
            report.append(f"**Score**: {passes}/10")
            
            report.append("\n### Letter Grades:")
            for item in evaluation:
                letter = item.get('letter', '?')
                metric = item.get('metric')
                status = "✅ PASS" if item.get('pass') else "❌ FAIL"
                
                metric_str = f" (metric={metric})" if metric is not None else ""
                report.append(f"**{letter}**: {status}{metric_str}")
        
        elif isinstance(evaluation, dict):
            # Old format: direct grade fields
            passes = sum(1 for k, v in evaluation.items() if k.startswith('grade_') and v == 'PASS')
            report.append(f"**Score**: {passes}/10")
            
            report.append("\n### Letter Grades:")
            for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
                grade_field = f"grade_{letter.lower()}"
                metric_field = f"metric_{letter.lower()}"
                
                grade = evaluation.get(grade_field, 'UNKNOWN')
                metric = evaluation.get(metric_field)
                
                status = "✅ PASS" if grade == "PASS" else "❌ FAIL"
                metric_str = f" (metric={metric})" if metric is not None else ""
                
                report.append(f"**{letter}**: {status}{metric_str}")
    else:
        report.append("**Status**: ❌ EVALUATION FAILED")
    
    return "\n".join(report)

def main():
    print("🔍 SHARD-19 County Status Verification - Run 19")
    print(f"Target counties: {', '.join(SHARD19_COUNTIES)}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("Purpose: Baseline metrics for autonomous session\n")
    
    # Print debug info about environment  
    print(f"SUPABASE_URL: {SUPABASE_URL}")
    print(f"SUPABASE_KEY available: {'Yes' if SUPABASE_KEY else 'No'}")
    
    # Test connection first
    if not test_connection():
        print("❌ Database connection failed. Checking for environment variables...")
        print(f"Available env vars: {[k for k in os.environ.keys() if 'SUPABASE' in k or 'DB' in k]}")
        return
    
    print("\n📊 Gathering county evaluations and auction counts...\n")
    
    # Get auction counts for context
    auction_counts = get_multi_county_auctions_counts()
    
    # Run baseline vs expected analysis
    analyze_baseline_vs_expected()
    
    # Collect fresh evaluations for each county
    print("\n📊 FRESH EVALUATIONS")
    print("="*50)
    
    county_data = {}
    for county in SHARD19_COUNTIES:
        print(f"\nProcessing {county}...")
        
        # Get evaluation using function
        evaluation = get_county_evaluation(county)
        
        county_data[county] = {
            'evaluation': evaluation,
            'auction_count': auction_counts.get(county, 0)
        }
    
    # Generate detailed reports
    print("\n" + "="*60)
    print("SHARD-19 COUNTY STATUS REPORT")
    print("="*60)
    
    for county, data in county_data.items():
        evaluation = data.get('evaluation')
        auction_count = data.get('auction_count', 0)
        
        print(format_county_report(county, evaluation))
        print(f"**Auction Count**: {auction_count}")
    
    # Summary and next actions
    print(f"\n" + "="*60)
    print("AUTONOMOUS SESSION PRIORITY ANALYSIS")
    print("="*60)
    
    total_counties = len(SHARD19_COUNTIES)
    evaluated_counties = sum(1 for data in county_data.values() if data.get('evaluation'))
    
    print(f"Counties evaluated: {evaluated_counties}/{total_counties}")
    
    if evaluated_counties > 0:
        print("\nPRIORITY ORDER per BREVARD SPRINT ORDER (Jun12):")
        print("1. C/D ROOT CAUSE — PropertyOnion coverage audit + clerk/official-records supplementary")
        print("2. J GENERATOR — bid_decisions with Shapira V14 ml_score")  
        print("3. B RECONCILIATION — fix anomalous verified outcomes ratios")
        print("4. Other letters as session time permits")
        print("\nCRITERION-PARALLEL PIVOT: Fix criteria fleet-wide, not counties serially")
        print("SHIP-TO-MAIN MANDATE: Direct commits, no branches, frequent commits with evidence")
    
    print(f"\nBaseline verification completed at: {datetime.now().isoformat()}")

if __name__ == "__main__":
    main()