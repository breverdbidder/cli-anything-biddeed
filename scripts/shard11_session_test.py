#!/usr/bin/env python3
"""
SHARD-11 Session Test - Verify database access and county metrics
Target counties: sarasota, hillsborough, pinellas, gadsden, wakulla

Usage:
  python scripts/shard11_session_test.py
"""
import os
import requests
import json
from datetime import datetime

# Supabase configuration from CLAUDE.md
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")
DB_POOLER = os.environ.get("DB_POOLER", "aws-0-us-west-2.pooler.supabase.com")
DB_PASSWORD = os.environ.get("SUPABASE_DB_PASSWORD", "")

BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}", 
    "Content-Type": "application/json"
}

# SHARD-11 counties as specified in issue
SHARD11_COUNTIES = ['sarasota', 'hillsborough', 'pinellas', 'gadsden', 'wakulla']

def test_connection():
    """Test Supabase connection"""
    print(f"🔌 Testing connection to {SUPABASE_URL}")
    print(f"   API Key available: {'Yes' if SUPABASE_KEY else 'No'}")
    print(f"   DB Password available: {'Yes' if DB_PASSWORD else 'No'}")
    
    try:
        # Test simple table query
        response = requests.get(
            f"{BASE}/audit_log", 
            headers=HEADERS, 
            params={"limit": "1"},
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ Supabase REST API connection successful")
            return True
        else:
            print(f"❌ Connection failed: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def get_county_evaluation(county):
    """Get evaluation for a specific county using pencil_dod_evaluate_county function"""
    print(f"  📊 Evaluating {county}...")
    
    try:
        payload = {"county_name": county}
        response = requests.post(
            f"{BASE}/rpc/pencil_dod_evaluate_county", 
            headers=HEADERS, 
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"      ✅ Evaluation successful")
            return result
        else:
            print(f"      ⚠️ Evaluation failed: {response.status_code}")
            print(f"      Response: {response.text[:100]}")
            return None
            
    except Exception as e:
        print(f"      ❌ Evaluation error: {e}")
        return None

def format_county_metrics(county, evaluation):
    """Format county metrics in the issue style"""
    if not evaluation:
        return f"## {county} (EVALUATION FAILED)"
    
    # Extract letter metrics 
    letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']
    passes = []
    fails = []
    
    total_pass = 0
    for letter in letters:
        grade_field = f"grade_{letter.lower()}"
        metric_field = f"metric_{letter.lower()}"
        
        grade = evaluation.get(grade_field)
        metric = evaluation.get(metric_field)
        
        if grade == "PASS":
            passes.append(letter)
            total_pass += 1
        else:
            fails.append(f"{letter} {grade if grade != 'FAIL' else 'FAIL'}")
            if metric is not None:
                fails[-1] += f" metric={metric}"
    
    pass_str = "".join([f"{l}✓" for l in passes]) if passes else ""
    fail_str = " | ".join(fails) if fails else ""
    
    divider = " | " if pass_str and fail_str else ""
    
    return f"## {county} ({total_pass}/10)\n    {pass_str}{divider}{fail_str}"

def main():
    print("🎯 SHARD-11 Gold Standard Session - Database Test")
    print(f"Counties: {', '.join(SHARD11_COUNTIES)}")
    print(f"Timestamp: {datetime.now().isoformat()}\n")
    
    # Test connection
    if not test_connection():
        print("\n❌ Database connection failed - cannot proceed with Gold Standard session")
        print("Required environment variables:")
        print("  - SUPABASE_URL (or defaults to mocerqjnksmhcjzxrewo.supabase.co)")
        print("  - SUPABASE_KEY or SUPABASE_SERVICE_KEY")
        print("  - SUPABASE_DB_PASSWORD")
        return False
    
    print("\n📊 Gathering current county metrics...\n")
    
    # Evaluate each county
    county_evaluations = {}
    for county in SHARD11_COUNTIES:
        evaluation = get_county_evaluation(county)
        county_evaluations[county] = evaluation
    
    # Generate metrics report in issue format
    print("\n" + "="*70)
    print("SHARD-11 CURRENT COUNTY METRICS")
    print("="*70)
    
    for county in SHARD11_COUNTIES:
        evaluation = county_evaluations[county]
        metrics = format_county_metrics(county, evaluation)
        print(metrics)
        print()
    
    print("="*70)
    print("🎯 CONNECTION TEST COMPLETE - Ready for Gold Standard session")
    
    # Count successful evaluations
    successful_evaluations = sum(1 for e in county_evaluations.values() if e is not None)
    print(f"   Successfully evaluated: {successful_evaluations}/{len(SHARD11_COUNTIES)} counties")
    
    if successful_evaluations > 0:
        print("   Database access confirmed ✅")
        print("   Ready to execute priority fixes per Brevard Sprint Order:")
        print("   1. C/D ROOT CAUSE → supplementary litmus")
        print("   2. J GENERATOR → bid_decisions pipeline")  
        print("   3. G HIT LIST → zone_standards backfill")
        print("   4. B RECONCILIATION → anomaly resolution")
        return True
    else:
        print("   ❌ No counties could be evaluated - check database function access")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)