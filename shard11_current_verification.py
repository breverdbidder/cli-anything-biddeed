#!/usr/bin/env python3
"""
SHARD-11 Current Campaign Verification
Counties: putnam, gilchrist, orange, gadsden, wakulla
VERIFIED approach with evidence collection per Honesty Protocol

Usage: python shard11_current_verification.py
"""
import os
import requests
import json
from datetime import datetime, timezone

# Supabase configuration from CLAUDE.md
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}", 
    "Content-Type": "application/json"
}

# CURRENT SHARD-11 counties per issue brief
SHARD11_COUNTIES = ['putnam', 'gilchrist', 'orange', 'gadsden', 'wakulla']

# Expected metrics from issue brief for VERIFIED comparison
EXPECTED_METRICS = {
    'putnam': {
        'A': {'grade': 'PASS', 'metric': 98},
        'B': {'grade': 'FAIL', 'metric': None},
        'C': {'grade': 'FAIL', 'metric': 6.3},
        'D': {'grade': 'PASS', 'metric': 97.7},
        'E': {'grade': 'FAIL', 'metric': 17.9},
        'F': {'grade': 'FAIL', 'metric': 0.0},
        'G': {'grade': 'FAIL', 'metric': None},
        'H': {'grade': 'FAIL', 'metric': 433.0},
        'I': {'grade': 'FAIL', 'metric': None},
        'J': {'grade': 'FAIL', 'metric': 0.0}
    },
    'gilchrist': {
        'A': {'grade': 'PASS', 'metric': 2},
        'total_score': 1  # 1/10 per brief
    },
    'orange': {
        'A': {'grade': 'PASS', 'metric': 5540},
        'total_score': 1  # 1/10 per brief
    },
    'gadsden': {'total_score': 0},  # 0/10 per brief
    'wakulla': {'total_score': 0}   # 0/10 per brief
}

def test_connection():
    """Test Supabase connection - VERIFIED approach"""
    try:
        response = requests.get(f"{BASE}/audit_log", headers=HEADERS, params={"limit": "1"}, timeout=10)
        if response.status_code == 200:
            print("✅ VERIFIED: Supabase connection successful")
            return True
        else:
            print(f"❌ VERIFIED: Connection failed {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ VERIFIED: Connection error {e}")
        return False

def get_county_evaluation(county):
    """Get LIVE evaluation for county - VERIFIED approach with evidence collection"""
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
            # Evidence collection per Honesty Protocol
            evidence = {
                "query": f"pencil_dod_evaluate_county('{county}')",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "response_code": response.status_code,
                "result": result
            }
            print(f"✅ VERIFIED: {county} evaluation retrieved")
            return result, evidence
        else:
            print(f"❌ VERIFIED: {county} evaluation failed {response.status_code}")
            return None, None
            
    except Exception as e:
        print(f"❌ VERIFIED: {county} evaluation error: {e}")
        return None, None

def compare_to_brief(county, live_result):
    """Compare live results to issue brief expectations - INFERRED analysis"""
    if not live_result:
        return {"status": "NO_DATA", "comparison": "Cannot compare - no live data"}
    
    expected = EXPECTED_METRICS.get(county, {})
    comparison = {
        "county": county,
        "comparison_timestamp": datetime.now(timezone.utc).isoformat(),
        "matches": {},
        "discrepancies": {}
    }
    
    # Compare total score if available
    live_score = live_result.get('total_score')
    expected_score = expected.get('total_score')
    
    if expected_score is not None and live_score is not None:
        if live_score == expected_score:
            comparison["matches"]["total_score"] = {"expected": expected_score, "live": live_score}
        else:
            comparison["discrepancies"]["total_score"] = {"expected": expected_score, "live": live_score}
    
    # Compare individual letters for putnam (most detailed in brief)
    if county == 'putnam' and 'A' in expected:
        for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
            expected_letter = expected.get(letter, {})
            live_grade = live_result.get(f'grade_{letter.lower()}')
            live_metric = live_result.get(f'metric_{letter.lower()}')
            
            expected_grade = expected_letter.get('grade')
            expected_metric = expected_letter.get('metric')
            
            if expected_grade and live_grade:
                if expected_grade == live_grade:
                    comparison["matches"][f"grade_{letter}"] = {"expected": expected_grade, "live": live_grade}
                else:
                    comparison["discrepancies"][f"grade_{letter}"] = {"expected": expected_grade, "live": live_grade}
    
    return comparison

def analyze_priorities(county, evaluation):
    """Analyze county priorities based on Brevard Sprint Order - INFERRED from evaluation"""
    if not evaluation:
        return {"priority": "BASIC_SETUP", "reason": "No evaluation data"}
    
    failing_letters = []
    for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
        grade = evaluation.get(f'grade_{letter.lower()}')
        if grade != "PASS":
            failing_letters.append(letter)
    
    # Brevard Sprint Order mapping
    if 'C' in failing_letters or 'D' in failing_letters:
        return {
            "priority": "C_D_ROOT_CAUSE", 
            "failing_letters": failing_letters,
            "rationale": "Parity audit vs PropertyOnion coverage - highest velocity impact"
        }
    elif 'J' in failing_letters:
        return {
            "priority": "J_GENERATOR", 
            "failing_letters": failing_letters,
            "rationale": "bid_decisions pipeline - single largest point block (0→95)"
        }
    elif 'G' in failing_letters:
        return {
            "priority": "G_HIT_LIST", 
            "failing_letters": failing_letters,
            "rationale": "zone_standards NULL backfill for key districts"
        }
    elif 'B' in failing_letters:
        return {
            "priority": "B_RECONCILIATION", 
            "failing_letters": failing_letters,
            "rationale": "verified_outcomes > closed_sold anomaly resolution"
        }
    else:
        return {
            "priority": "MAINTENANCE", 
            "failing_letters": failing_letters,
            "rationale": "County in maintenance mode - focus on other targets"
        }

def main():
    """Execute SHARD-11 verification with evidence collection"""
    print("🔍 SHARD-11 CURRENT Campaign Verification")
    print(f"Counties: {', '.join(SHARD11_COUNTIES)}")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"Honesty Protocol: VERIFIED evidence collection enabled\n")
    
    # Test connection with VERIFIED evidence
    if not test_connection():
        print("❌ VERIFIED: Campaign cannot proceed - no database access")
        return {"status": "FAILED", "reason": "NO_DB_CONNECTION"}
    
    # Collect VERIFIED data for each county
    verification_results = {
        "session_start": datetime.now(timezone.utc).isoformat(),
        "counties": {},
        "verification_evidence": [],
        "priority_rankings": []
    }
    
    print("📊 VERIFIED: Collecting live county evaluations...\n")
    
    for county in SHARD11_COUNTIES:
        print(f"Processing {county}...")
        
        # Get VERIFIED live evaluation
        live_eval, evidence = get_county_evaluation(county)
        
        if evidence:
            verification_results["verification_evidence"].append(evidence)
        
        # Compare to brief expectations - INFERRED
        comparison = compare_to_brief(county, live_eval)
        
        # Analyze priorities - INFERRED
        priority_analysis = analyze_priorities(county, live_eval)
        
        verification_results["counties"][county] = {
            "live_evaluation": live_eval,
            "brief_comparison": comparison,
            "priority_analysis": priority_analysis
        }
        
        # Log results
        if live_eval:
            score = live_eval.get('total_score', 'N/A')
            print(f"✅ VERIFIED: {county} score {score}/10")
            print(f"   INFERRED priority: {priority_analysis['priority']}")
        else:
            print(f"❌ VERIFIED: {county} no evaluation data")
        
        verification_results["priority_rankings"].append({
            "county": county,
            "priority": priority_analysis.get("priority", "UNKNOWN"),
            "failing_letters": priority_analysis.get("failing_letters", [])
        })
    
    verification_results["session_end"] = datetime.now(timezone.utc).isoformat()
    
    # Save VERIFIED results for audit trail
    with open("/tmp/shard11_verification_results.json", "w") as f:
        json.dump(verification_results, f, indent=2, default=str)
    
    print(f"\n{'='*60}")
    print("SHARD-11 VERIFICATION COMPLETE")
    print(f"{'='*60}")
    
    # Summary with VERIFIED evidence counts
    evidence_count = len(verification_results["verification_evidence"])
    print(f"VERIFIED evidence items: {evidence_count}")
    
    # Priority recommendations based on INFERRED analysis
    print(f"\nINFERRED Priority Targets (Brevard Sprint Order):")
    for ranking in verification_results["priority_rankings"]:
        county = ranking["county"]
        priority = ranking["priority"]
        failing = len(ranking.get("failing_letters", []))
        print(f"- {county}: {priority} ({failing} failing letters)")
    
    print(f"\nVERIFIED session complete: {datetime.now(timezone.utc).isoformat()}")
    
    return verification_results

if __name__ == "__main__":
    results = main()