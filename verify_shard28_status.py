#!/usr/bin/env python3
"""
SHARD-28 Status Verification
Counties: charlotte, citrus, highlands

Verifies current metrics for assigned counties per GOLD STANDARD AUTOPILOT-NEXT briefing.
"""
import os
import sys
import httpx
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# SHARD-28 assigned counties
SHARD_COUNTIES = ['charlotte', 'citrus', 'highlands']

# Briefing data for comparison (loop run 28)
BRIEFING_DATA = {
    'charlotte': {
        'A': {'grade': 'PASS', 'metric': 249, 'detail': 'fc=249 td=7857'},
        'B': {'grade': 'FAIL', 'metric': None, 'detail': 'verified=0 closed_sold=945'},
        'C': {'grade': 'FAIL', 'metric': 10.1, 'detail': 'matched_clean=821 of 8106'},
        'D': {'grade': 'PASS', 'metric': 97.4, 'detail': 'matched_any=7899 of 8106'},
        'E': {'grade': 'FAIL', 'metric': 43.8, 'detail': 'parcel_linked=3547 of 8106'},
        'F': {'grade': 'FAIL', 'metric': 2.1, 'detail': 'tier1_sold=20 closed_sold=945'},
        'G': {'grade': 'FAIL', 'metric': None, 'detail': 'density= far= pk1000='},
        'H': {'grade': 'FAIL', 'metric': 74.0, 'detail': 'hours since last_seen (SLA 48h)'},
        'I': {'grade': 'FAIL', 'metric': None, 'detail': 'zoned_complete_parcels=0 field_complete_parcels=1423 auctions=8106'},
        'J': {'grade': 'FAIL', 'metric': 0.0, 'detail': 'deal_complete=0 of 8106 (triangle + two-arm CMA + ml_score + max_bid)'}
    },
    'citrus': {
        'A': {'grade': 'PASS', 'metric': 1666, 'detail': 'fc=1666 td=3846'},
        'B': {'grade': 'FAIL', 'metric': None, 'detail': 'verified=0 closed_sold=1308'},
        'C': {'grade': 'FAIL', 'metric': 9.5, 'detail': 'matched_clean=523 of 5512'},
        'D': {'grade': 'FAIL', 'metric': 75.3, 'detail': 'matched_any=4152 of 5512'},
        'E': {'grade': 'PASS', 'metric': 95.3, 'detail': 'parcel_linked=5253 of 5512'},
        'F': {'grade': 'FAIL', 'metric': 6.1, 'detail': 'tier1_sold=80 closed_sold=1308'},
        'G': {'grade': 'FAIL', 'metric': None, 'detail': 'density= far= pk1000='},
        'H': {'grade': 'FAIL', 'metric': 61.6, 'detail': 'hours since last_seen (SLA 48h)'},
        'I': {'grade': 'FAIL', 'metric': None, 'detail': 'zoned_complete_parcels=0 field_complete_parcels=1473 auctions=5512'},
        'J': {'grade': 'FAIL', 'metric': 0.0, 'detail': 'deal_complete=0 of 5512 (triangle + two-arm CMA + ml_score + max_bid)'}
    },
    'highlands': {
        'A': {'grade': 'PASS', 'metric': 80, 'detail': 'fc=80 td=161'},
        'B': {'grade': 'FAIL', 'metric': None, 'detail': 'verified=0 closed_sold=63'},
        'C': {'grade': 'FAIL', 'metric': 31.5, 'detail': 'matched_clean=76 of 241'},
        'D': {'grade': 'PASS', 'metric': 97.5, 'detail': 'matched_any=235 of 241'},
        'E': {'grade': 'FAIL', 'metric': 50.2, 'detail': 'parcel_linked=121 of 241'},
        'F': {'grade': 'FAIL', 'metric': 0.0, 'detail': 'tier1_sold=0 closed_sold=63'},
        'G': {'grade': 'FAIL', 'metric': None, 'detail': 'density= far= pk1000='},
        'H': {'grade': 'FAIL', 'metric': 598.4, 'detail': 'hours since last_seen (SLA 48h)'},
        'I': {'grade': 'FAIL', 'metric': None, 'detail': 'zoned_complete_parcels=0 field_complete_parcels=58 auctions=241'},
        'J': {'grade': 'FAIL', 'metric': 0.0, 'detail': 'deal_complete=0 of 241 (triangle + two-arm CMA + ml_score + max_bid)'}
    }
}

def log_action(msg: str, level: str = "INFO", honesty_tag: str = "UNTESTED"):
    """Log with timestamp and honesty protocol tag"""
    timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{timestamp}] {level} [{honesty_tag}]: {msg}")

def check_db_connection() -> bool:
    """Check if we can connect to Supabase"""
    if not SUPABASE_KEY:
        log_action("No Supabase credentials available", "INFO", "VERIFIED")
        return False
    
    try:
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        with httpx.Client(timeout=10) as client:
            response = client.get(
                f"{SUPABASE_URL}/rest/v1/audit_log",
                headers=headers,
                params={"limit": "1"}
            )
            
            if response.status_code == 200:
                log_action("Database connection verified", "INFO", "VERIFIED")
                return True
            else:
                log_action(f"Database connection failed: {response.status_code}", "ERROR", "VERIFIED")
                return False
                
    except Exception as e:
        log_action(f"Database connection error: {e}", "ERROR", "VERIFIED")
        return False

def get_county_evaluation(county_slug: str) -> Optional[List[Dict]]:
    """Get live county evaluation using pencil_dod_evaluate_county RPC"""
    if not SUPABASE_KEY:
        return None
    
    try:
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        with httpx.Client(timeout=30) as client:
            response = client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
                headers=headers,
                json={"county_slug_arg": county_slug}
            )
            
            if response.status_code == 200:
                result = response.json()
                log_action(f"Got evaluation for {county_slug}: {len(result)} letters", "INFO", "VERIFIED")
                return result
            else:
                log_action(f"Evaluation failed for {county_slug}: {response.status_code}", "ERROR", "VERIFIED")
                return None
                
    except Exception as e:
        log_action(f"Evaluation error for {county_slug}: {e}", "ERROR", "VERIFIED")
        return None

def analyze_failing_letters(county_slug: str, evaluation: List[Dict]) -> List[str]:
    """Identify failing letters and prioritize by leverage"""
    failing = []
    critical = []  # B, I, J are critical per briefing
    
    for item in evaluation:
        letter = item.get('letter')
        passes = item.get('pass', False)
        
        if not passes:
            failing.append(letter)
            
            # Critical letters per briefing
            if letter in ['B', 'I', 'J']:
                critical.append(letter)
    
    # Priority order from briefing: critical three first, then by impact
    priority_order = ['J', 'B', 'I', 'C', 'D', 'G', 'E', 'F', 'H', 'A']
    
    # Sort failing letters by priority
    failing_sorted = []
    for letter in priority_order:
        if letter in failing:
            failing_sorted.append(letter)
    
    log_action(f"{county_slug} failing letters: {', '.join(failing_sorted)} (critical: {', '.join(critical)})", "INFO", "VERIFIED")
    return failing_sorted

def compare_with_briefing(county_slug: str, live_evaluation: List[Dict]) -> Dict:
    """Compare live evaluation with briefing data"""
    briefing = BRIEFING_DATA.get(county_slug, {})
    comparison = {
        'county': county_slug,
        'changes': [],
        'score_change': None,
        'new_passes': [],
        'new_fails': [],
        'metrics_changed': []
    }
    
    live_by_letter = {}
    for item in live_evaluation:
        letter = item.get('letter')
        live_by_letter[letter] = item
    
    # Compare each letter
    for letter in 'ABCDEFGHIJ':
        briefing_data = briefing.get(letter, {})
        live_data = live_by_letter.get(letter, {})
        
        briefing_grade = briefing_data.get('grade')
        briefing_metric = briefing_data.get('metric')
        
        live_pass = live_data.get('pass', False)
        live_metric = live_data.get('metric')
        live_grade = 'PASS' if live_pass else 'FAIL'
        
        # Check for grade changes
        if briefing_grade and briefing_grade != live_grade:
            if briefing_grade == 'FAIL' and live_grade == 'PASS':
                comparison['new_passes'].append(letter)
            elif briefing_grade == 'PASS' and live_grade == 'FAIL':
                comparison['new_fails'].append(letter)
            
            comparison['changes'].append(f"{letter}: {briefing_grade} → {live_grade}")
        
        # Check for metric changes (significant = >5% change)
        if briefing_metric is not None and live_metric is not None:
            pct_change = abs(live_metric - briefing_metric) / briefing_metric * 100
            if pct_change > 5:
                comparison['metrics_changed'].append(f"{letter}: {briefing_metric} → {live_metric}")
    
    # Calculate current score
    current_passes = len([item for item in live_evaluation if item.get('pass', False)])
    briefing_score = len([k for k, v in briefing.items() if v.get('grade') == 'PASS'])
    comparison['score_change'] = f"{briefing_score}/10 → {current_passes}/10"
    
    return comparison

def main():
    """Main verification orchestrator"""
    log_action("Starting SHARD-28 status verification", "INFO", "VERIFIED")
    log_action(f"Assigned counties: {', '.join(SHARD_COUNTIES)}", "INFO", "VERIFIED")
    
    # Check database connectivity
    has_db = check_db_connection()
    
    if not has_db:
        log_action("No database access - using briefing data for analysis", "INFO", "VERIFIED")
        
        # Analyze based on briefing data
        print("\n" + "="*60)
        print("SHARD-28 ANALYSIS FROM BRIEFING DATA")
        print("="*60)
        
        for county in SHARD_COUNTIES:
            briefing = BRIEFING_DATA[county]
            failing = [k for k, v in briefing.items() if v.get('grade') == 'FAIL']
            passing = [k for k, v in briefing.items() if v.get('grade') == 'PASS']
            
            print(f"\n**{county.upper()}** (Score: {len(passing)}/10)")
            print(f"  ✅ PASSING: {', '.join(sorted(passing))}")
            print(f"  ❌ FAILING: {', '.join(sorted(failing))}")
            
            # Highest leverage failing letters
            critical_failing = [letter for letter in failing if letter in ['B', 'I', 'J']]
            high_impact = [letter for letter in failing if letter in ['C', 'D', 'G']]
            
            print(f"  🎯 CRITICAL: {', '.join(critical_failing)} (highest leverage)")
            print(f"  📊 HIGH IMPACT: {', '.join(high_impact)}")
        
        # Fleet-wide analysis
        all_failing = {}
        for county in SHARD_COUNTIES:
            briefing = BRIEFING_DATA[county]
            for letter, data in briefing.items():
                if data.get('grade') == 'FAIL':
                    if letter not in all_failing:
                        all_failing[letter] = []
                    all_failing[letter].append(county)
        
        print(f"\n" + "="*60)
        print("FLEET-WIDE FAILING LETTERS (SHARD-28)")
        print("="*60)
        
        priority_letters = ['J', 'B', 'I', 'G', 'C', 'D', 'E', 'F', 'H']
        for letter in priority_letters:
            counties = all_failing.get(letter, [])
            if counties:
                impact = "CRITICAL" if letter in ['B', 'I', 'J'] else "HIGH" if len(counties) >= 3 else "MEDIUM"
                print(f"**{letter}** ({impact}): {', '.join(counties)} ({len(counties)}/3 counties)")
        
        print(f"\n📋 RECOMMENDED WORK ORDER:")
        print("1. **J GENERATOR** - All 3 counties fail (bid_decisions pipeline)")
        print("2. **B RECONCILIATION** - All 3 counties fail (independent outcomes)")  
        print("3. **G/I SUBSTRATE** - All 3 counties fail (zoning + property cards)")
        print("4. **C/D PARITY** - Varying performance (PropertyOnion vs official)")
        print("5. **E/F LINKAGE** - County-specific fixes")
        
        return 0
    
    else:
        # Live database verification
        print("\n" + "="*60)
        print("LIVE SHARD-28 VERIFICATION")
        print("="*60)
        
        all_comparisons = []
        all_failing_by_county = {}
        
        for county in SHARD_COUNTIES:
            log_action(f"Evaluating {county}...", "INFO", "UNTESTED")
            
            evaluation = get_county_evaluation(county)
            if not evaluation:
                log_action(f"Failed to get evaluation for {county}", "ERROR", "VERIFIED")
                continue
            
            # Analyze failing letters
            failing_letters = analyze_failing_letters(county, evaluation)
            all_failing_by_county[county] = failing_letters
            
            # Compare with briefing
            comparison = compare_with_briefing(county, evaluation)
            all_comparisons.append(comparison)
            
            # Report status
            print(f"\n**{county.upper()}**")
            print(f"  Score: {comparison['score_change']}")
            
            if comparison['new_passes']:
                print(f"  🎉 NEW PASSES: {', '.join(comparison['new_passes'])}")
            
            if comparison['new_fails']:
                print(f"  ⚠️  NEW FAILS: {', '.join(comparison['new_fails'])}")
            
            if comparison['metrics_changed']:
                print(f"  📊 METRICS CHANGED: {', '.join(comparison['metrics_changed'])}")
            
            print(f"  ❌ CURRENTLY FAILING: {', '.join(failing_letters[:5])}")  # Top 5
        
        # Summary of changes
        total_new_passes = sum(len(c['new_passes']) for c in all_comparisons)
        total_new_fails = sum(len(c['new_fails']) for c in all_comparisons)
        
        print(f"\n" + "="*60)
        print(f"CHANGES SINCE BRIEFING: +{total_new_passes} passes, +{total_new_fails} fails")
        print("="*60)
        
        # Identify highest leverage work
        fleet_failing = {}
        for county, failing in all_failing_by_county.items():
            for letter in failing:
                if letter not in fleet_failing:
                    fleet_failing[letter] = []
                fleet_failing[letter].append(county)
        
        print(f"\nRECOMMENDED SESSION WORK (highest leverage first):")
        priority_order = ['J', 'B', 'I', 'G', 'C', 'D', 'E', 'F', 'H', 'A']
        
        work_items = []
        for letter in priority_order:
            counties = fleet_failing.get(letter, [])
            if len(counties) >= 2:  # Multi-county impact
                work_items.append(f"**{letter}**: {', '.join(counties)} ({len(counties)} counties)")
        
        for i, item in enumerate(work_items[:5], 1):  # Top 5
            print(f"{i}. {item}")
        
        return 0

if __name__ == "__main__":
    sys.exit(main())