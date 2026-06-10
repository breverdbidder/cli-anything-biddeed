#!/usr/bin/env python3
"""
GOLD STANDARD WAVE2-SHARD-7: Verification and Reporting
Counties: alachua, gilchrist, miami_dade, walton, gadsden, lafayette, wakulla

Implements verification protocol per CLAUDE.md requirements:
- After each fix: SELECT public.pencil_dod_evaluate_county('<county>');
- Before session end: SELECT public.gold_standard_loop(); SELECT public.gold_standard_certify();
- Report scoreboard deltas and log to insights table
"""
import httpx
import json
import os
import sys
import argparse
from datetime import datetime
from typing import Dict, List, Optional
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

# WAVE2-SHARD-7 counties
SHARD_COUNTIES = ['alachua', 'gilchrist', 'miami_dade', 'walton', 'gadsden', 'lafayette', 'wakulla']

client = httpx.Client(timeout=120)

def supabase_rpc(func_name: str, params: Dict = None) -> Optional[Dict]:
    """Call Supabase RPC function"""
    try:
        url = f"{BASE}/rpc/{func_name}"
        response = client.post(url, headers=HEADERS, json=params or {})
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error calling {func_name}: {e}")
        return None

def supabase_get(table: str, params: str = "") -> List[Dict]:
    """Get data from Supabase table"""
    try:
        url = f"{BASE}/{table}?{params}"
        response = client.get(url, headers=HEADERS)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching from {table}: {e}")
        return []

def supabase_insert(table: str, data: Dict) -> bool:
    """Insert record to Supabase table"""
    try:
        url = f"{BASE}/{table}"
        response = client.post(url, headers=HEADERS, json=data)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Error inserting to {table}: {e}")
        return False

def evaluate_county(county_slug: str) -> Optional[List[Dict]]:
    """Run pencil_dod_evaluate_county for a specific county"""
    logger.info(f"Evaluating {county_slug}...")
    
    result = supabase_rpc("pencil_dod_evaluate_county", {"county_slug_arg": county_slug})
    
    if result:
        logger.info(f"✅ Evaluation completed for {county_slug}")
        for letter_data in result:
            letter = letter_data.get('letter', '?')
            metric = letter_data.get('metric', 'N/A')
            status = "✅" if letter_data.get('pass') else "❌"
            threshold = letter_data.get('threshold', '')
            detail = letter_data.get('detail', '')
            
            logger.info(f"  {letter}: {status} {metric} (threshold: {threshold})")
            if detail and not letter_data.get('pass'):
                logger.info(f"      Detail: {detail}")
    else:
        logger.error(f"❌ Failed to evaluate {county_slug}")
    
    return result

def get_current_scoreboard() -> Dict[str, Dict]:
    """Get current gold standard scoreboard for SHARD-7 counties"""
    logger.info("Fetching current scoreboard...")
    
    counties_filter = ','.join(f'"{c}"' for c in SHARD_COUNTIES)
    scoreboard = supabase_get(
        "gold_standard_scoreboard",
        f"county_slug=in.({counties_filter})&select=*"
    )
    
    result = {}
    for record in scoreboard:
        county = record.get('county_slug')
        if county:
            result[county] = record
    
    return result

def run_gold_standard_loop() -> bool:
    """Run the gold standard loop evaluation"""
    logger.info("Running gold standard loop evaluation...")
    
    # Set statement timeout to 0 first (per CLAUDE.md requirements)
    timeout_result = supabase_rpc("exec", {"sql": "SET statement_timeout = 0;"})
    if not timeout_result:
        logger.warning("Could not set statement timeout - proceeding anyway")
    
    # Run the gold standard loop
    loop_result = supabase_rpc("gold_standard_loop")
    
    if loop_result is not None:
        logger.info("✅ Gold standard loop completed successfully")
        return True
    else:
        logger.error("❌ Gold standard loop failed")
        return False

def run_gold_standard_certify() -> bool:
    """Run the gold standard certification"""
    logger.info("Running gold standard certification...")
    
    cert_result = supabase_rpc("gold_standard_certify")
    
    if cert_result is not None:
        logger.info("✅ Gold standard certification completed")
        return True
    else:
        logger.error("❌ Gold standard certification failed")
        return False

def calculate_scoreboard_delta(before: Dict[str, Dict], after: Dict[str, Dict]) -> Dict:
    """Calculate the difference between before and after scoreboards"""
    delta = {
        'improved_counties': [],
        'degraded_counties': [],
        'unchanged_counties': [],
        'total_pass_delta': 0
    }
    
    for county in SHARD_COUNTIES:
        before_data = before.get(county, {})
        after_data = after.get(county, {})
        
        before_pass = before_data.get('pass_count', 0)
        after_pass = after_data.get('pass_count', 0)
        
        pass_delta = after_pass - before_pass
        
        county_delta = {
            'county': county,
            'before_pass': before_pass,
            'after_pass': after_pass,
            'delta': pass_delta
        }
        
        if pass_delta > 0:
            delta['improved_counties'].append(county_delta)
            delta['total_pass_delta'] += pass_delta
        elif pass_delta < 0:
            delta['degraded_counties'].append(county_delta)
            delta['total_pass_delta'] += pass_delta
        else:
            delta['unchanged_counties'].append(county_delta)
    
    return delta

def log_session_results(session_type: str, delta: Dict, notes: str = "") -> bool:
    """Log session results to insights table"""
    logger.info("Logging session results to insights table...")
    
    insight_data = {
        'type': 'gold_standard_session',
        'category': 'wave2_shard7',
        'title': f'WAVE2-SHARD-7 {session_type} Session Results',
        'content': {
            'session_type': session_type,
            'counties': SHARD_COUNTIES,
            'improved_counties': delta['improved_counties'],
            'degraded_counties': delta['degraded_counties'],
            'unchanged_counties': delta['unchanged_counties'],
            'total_pass_delta': delta['total_pass_delta'],
            'notes': notes,
            'timestamp': datetime.now().isoformat()
        },
        'priority': 'medium',
        'status': 'completed',
        'created_at': datetime.now().isoformat(),
        'metadata': {
            'source': 'wave2_shard7_verification',
            'automated': True
        }
    }
    
    return supabase_insert("insights", insight_data)

def verify_individual_counties() -> Dict[str, List[Dict]]:
    """Verify each county individually"""
    logger.info(f"Verifying {len(SHARD_COUNTIES)} SHARD-7 counties individually...")
    
    results = {}
    for county in SHARD_COUNTIES:
        results[county] = evaluate_county(county)
    
    return results

def full_verification_protocol(session_type: str = "autonomous", notes: str = "") -> Dict:
    """Run the complete verification protocol"""
    logger.info("=" * 80)
    logger.info("GOLD STANDARD WAVE2-SHARD-7 VERIFICATION PROTOCOL")
    logger.info("=" * 80)
    
    # 1. Get baseline scoreboard
    logger.info("\n1. Getting baseline scoreboard...")
    baseline_scoreboard = get_current_scoreboard()
    
    # 2. Verify individual counties
    logger.info("\n2. Verifying individual counties...")
    county_evaluations = verify_individual_counties()
    
    # 3. Run gold standard loop
    logger.info("\n3. Running gold standard loop...")
    loop_success = run_gold_standard_loop()
    
    # 4. Run gold standard certification
    logger.info("\n4. Running gold standard certification...")
    cert_success = run_gold_standard_certify()
    
    # 5. Get final scoreboard
    logger.info("\n5. Getting final scoreboard...")
    final_scoreboard = get_current_scoreboard()
    
    # 6. Calculate delta
    logger.info("\n6. Calculating scoreboard delta...")
    delta = calculate_scoreboard_delta(baseline_scoreboard, final_scoreboard)
    
    # 7. Report results
    logger.info("\n7. VERIFICATION RESULTS")
    logger.info("=" * 60)
    
    logger.info(f"Loop execution: {'✅' if loop_success else '❌'}")
    logger.info(f"Certification: {'✅' if cert_success else '❌'}")
    logger.info(f"Total pass count delta: {delta['total_pass_delta']}")
    
    if delta['improved_counties']:
        logger.info(f"\nImproved counties ({len(delta['improved_counties'])}):")
        for county_info in delta['improved_counties']:
            logger.info(f"  {county_info['county']}: {county_info['before_pass']} → {county_info['after_pass']} (+{county_info['delta']})")
    
    if delta['degraded_counties']:
        logger.info(f"\nDegraded counties ({len(delta['degraded_counties'])}):")
        for county_info in delta['degraded_counties']:
            logger.info(f"  {county_info['county']}: {county_info['before_pass']} → {county_info['after_pass']} ({county_info['delta']})")
    
    if delta['unchanged_counties']:
        logger.info(f"\nUnchanged counties ({len(delta['unchanged_counties'])}):")
        for county_info in delta['unchanged_counties']:
            logger.info(f"  {county_info['county']}: {county_info['before_pass']}/10")
    
    # 8. Log to insights
    logger.info("\n8. Logging session results...")
    log_success = log_session_results(session_type, delta, notes)
    logger.info(f"Insights logging: {'✅' if log_success else '❌'}")
    
    verification_results = {
        'baseline_scoreboard': baseline_scoreboard,
        'final_scoreboard': final_scoreboard,
        'county_evaluations': county_evaluations,
        'delta': delta,
        'loop_success': loop_success,
        'cert_success': cert_success,
        'log_success': log_success
    }
    
    logger.info("\n✅ Verification protocol completed")
    return verification_results

def main():
    parser = argparse.ArgumentParser(description="WAVE2-SHARD-7 Verification and Reporting")
    parser.add_argument("--county", choices=SHARD_COUNTIES, help="Evaluate specific county")
    parser.add_argument("--all-counties", action="store_true", help="Evaluate all SHARD-7 counties")
    parser.add_argument("--full-protocol", action="store_true", help="Run complete verification protocol")
    parser.add_argument("--scoreboard", action="store_true", help="Show current scoreboard")
    parser.add_argument("--session-type", default="autonomous", help="Session type for logging")
    parser.add_argument("--notes", default="", help="Additional notes for logging")
    
    args = parser.parse_args()
    
    if not SUPABASE_KEY:
        logger.error("SUPABASE_KEY environment variable required")
        sys.exit(1)
    
    if args.county:
        # Evaluate single county
        evaluate_county(args.county)
    
    elif args.all_counties:
        # Evaluate all SHARD-7 counties
        verify_individual_counties()
    
    elif args.scoreboard:
        # Show current scoreboard
        scoreboard = get_current_scoreboard()
        
        logger.info("\nCurrent Gold Standard Scoreboard (SHARD-7):")
        logger.info("=" * 60)
        
        for county in SHARD_COUNTIES:
            data = scoreboard.get(county, {})
            pass_count = data.get('pass_count', 0)
            critical_three = data.get('critical_three_pass', False)
            gold_standard = data.get('gold_standard', False)
            
            status_icon = "🥇" if gold_standard else "⭐" if critical_three else "📊"
            logger.info(f"{status_icon} {county:15s} | {pass_count:2d}/10 | Critical-3: {'✅' if critical_three else '❌'}")
    
    elif args.full_protocol:
        # Run complete verification protocol
        full_verification_protocol(args.session_type, args.notes)
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()