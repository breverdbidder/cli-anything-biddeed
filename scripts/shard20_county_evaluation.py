#!/usr/bin/env python3
"""
SHARD 20 County Evaluation - Brevard & Duval Gold Standard Assessment
Autonomous session run 20 - evaluating current status per pencil_dod_evaluate_county
"""

import os
import requests
import json
from datetime import datetime
import sys

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}", 
    "Content-Type": "application/json"
}

# Target counties for SHARD-20 run 20
SHARD20_COUNTIES = ['brevard', 'duval']

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
            return None
            
    except Exception as e:
        print(f"⚠️ Error evaluating {county}: {e}")
        return None

def execute_evaluation():
    """Execute pencil_dod_evaluate_county for both target counties"""
    print("=== SHARD 20 GOLD STANDARD EVALUATION ===")
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    print("")
    
    # Test connection first
    if not test_connection():
        print("❌ Database connection failed. Checking environment...")
        print(f"Available env vars: {[k for k in os.environ.keys() if 'SUPABASE' in k or 'DB' in k]}")
        return {'error': 'Database connection failed'}
    
    # Evaluate both counties
    results = {}
    
    for county in SHARD20_COUNTIES:
        print(f"--- Evaluating {county.upper()} ---")
        
        # Execute evaluation function
        result = get_county_evaluation(county)
        if result:
            results[county] = result
            
            print(f"Raw evaluation result for {county}:")
            print(json.dumps(result, indent=2))
            print("")
            
            # Parse letter grades (from the actual structure)
            letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']
            passes = []
            fails = []
            
            for letter in letters:
                grade_field = f"grade_{letter.lower()}"
                metric_field = f"metric_{letter.lower()}"
                
                status = result.get(grade_field, 'UNKNOWN')
                metric = result.get(metric_field)
                
                if status == 'PASS':
                    passes.append(f"{letter}✓")
                else:
                    fails.append(f"{letter}={metric}")
            
            print(f"{county.upper()} Summary: {len(passes)}/10 pass")
            print(f"PASS: {', '.join(passes) if passes else 'None'}")
            print(f"FAIL: {', '.join(fails) if fails else 'None'}")
            print("")
        else:
            print(f"❌ Failed to evaluate {county}")
            results[county] = None
    
    # Summary
    print("=== SPRINT ORDER ANALYSIS ===")
    
    # Brevard sprint order per issue brief
    print("BREVARD SPRINT ORDER:")
    print("1. C/D Root Cause - PropertyOnion coverage analysis")
    print("2. J Generator - bid_decisions pipeline")
    print("3. G Hit List - zone_standards backfill")
    print("4. B Reconciliation - verified_outcomes vs closed_sold")
    print("")
    
    # Duval sprint order per issue brief
    print("DUVAL SPRINT ORDER:")
    print("1. G+I Substrate Build - zoning districts and parcel linkage")
    print("2. C/D Root Cause - PropertyOnion coverage analysis") 
    print("3. J Generator - bid_decisions pipeline")
    print("4. B Reconciliation - verified_outcomes anomaly")
    print("")
    
    # Return structured results
    return {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'shard': 20,
        'counties': results,
        'session_status': 'BASELINE_ESTABLISHED'
    }

if __name__ == "__main__":
    result = execute_evaluation()
    if 'error' not in result:
        print("=== EVALUATION COMPLETE ===")
        print("Ready for sprint execution")
    else:
        print("EVALUATION FAILED - check database connection")
        sys.exit(1)