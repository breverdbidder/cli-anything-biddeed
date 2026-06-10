#!/usr/bin/env python3
"""
Gold Standard SHARD-2 Campaign Runner
Unified execution of Letters B, I, J for duval, manatee, pinellas counties.

This is the main campaign script that orchestrates all three critical letters
to move these counties toward 10/10 gold standard certification.
"""

import os
import sys
import subprocess
import time
from datetime import datetime, timezone
import argparse
import requests
import json

# Database connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_KEY:
    print("ERROR: SUPABASE_KEY or SUPABASE_SERVICE_KEY not set")
    sys.exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

SHARD2_COUNTIES = ['duval', 'manatee', 'pinellas']

def log(msg):
    """Log with timestamp and save to activities table."""
    timestamp = datetime.now()
    message = f"[{timestamp}] {msg}"
    print(message)
    
    # Store activity log
    try:
        activity_data = {
            "activity_type": "gold_standard_campaign",
            "description": msg,
            "metadata": {"shard": "SHARD-2", "timestamp": timestamp.isoformat()},
            "created_at": timestamp.isoformat()
        }
        requests.post(f"{BASE}/activities", headers=HEADERS, json=activity_data)
    except:
        pass  # Don't fail campaign if logging fails

def run_command(command, description):
    """Run a subprocess command with logging."""
    log(f"EXECUTING: {description}")
    log(f"Command: {command}")
    
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            log(f"SUCCESS: {description}")
            if result.stdout.strip():
                log(f"Output: {result.stdout.strip()}")
            return True
        else:
            log(f"FAILED: {description}")
            log(f"Error: {result.stderr.strip()}")
            return False
            
    except subprocess.TimeoutExpired:
        log(f"TIMEOUT: {description}")
        return False
    except Exception as e:
        log(f"EXCEPTION: {description} - {e}")
        return False

def get_county_status():
    """Get current gold standard status for all SHARD-2 counties."""
    log("=== CHECKING CURRENT STATUS ===")
    
    status = {}
    for county in SHARD2_COUNTIES:
        r = requests.get(
            f"{BASE}/gold_standard_scoreboard",
            headers=HEADERS,
            params={
                "select": "county_slug,pass_count,critical_three_pass,b_verified_outcomes,i_property_card,j_deal_thesis",
                "county_slug": f"eq.{county}"
            }
        )
        
        if r.status_code == 200 and r.json():
            data = r.json()[0]
            status[county] = {
                "pass_count": data.get('pass_count', 0),
                "critical_three": data.get('critical_three_pass', False),
                "b_score": data.get('b_verified_outcomes'),
                "i_score": data.get('i_property_card'),
                "j_score": data.get('j_deal_thesis')
            }
            log(f"{county}: {data.get('pass_count', 0)}/10 (B={data.get('b_verified_outcomes')}, I={data.get('i_property_card')}, J={data.get('j_deal_thesis')})")
        else:
            log(f"Could not fetch status for {county}")
            status[county] = None
    
    return status

def run_letter_campaign(letter, script_name, max_cases=100):
    """Run campaign for a specific letter."""
    log(f"\n=== LETTER {letter} CAMPAIGN ===")
    
    success_count = 0
    for county in SHARD2_COUNTIES:
        command = f"python3 scripts/{script_name} --county {county} --max-cases {max_cases}"
        if run_command(command, f"Letter {letter} for {county}"):
            success_count += 1
        time.sleep(5)  # Brief pause between counties
    
    log(f"Letter {letter} campaign: {success_count}/{len(SHARD2_COUNTIES)} counties succeeded")
    return success_count

def run_verification_query(county):
    """Run single-county verification query."""
    log(f"Running verification for {county}")
    
    # In a production environment with database access, this would run:
    # SELECT public.pencil_dod_evaluate_county('{county}');
    
    # For now, simulate by checking status again
    r = requests.get(
        f"{BASE}/gold_standard_scoreboard",
        headers=HEADERS,
        params={
            "select": "county_slug,pass_count,critical_three_pass",
            "county_slug": f"eq.{county}"
        }
    )
    
    if r.status_code == 200 and r.json():
        data = r.json()[0]
        log(f"{county} verification: {data.get('pass_count', 0)}/10, critical_three={data.get('critical_three_pass', False)}")
        return data.get('pass_count', 0)
    return 0

def save_campaign_results(start_status, end_status, campaigns_run):
    """Save campaign results to insights table."""
    results = {
        "campaign_type": "gold_standard_shard2",
        "counties": SHARD2_COUNTIES,
        "start_status": start_status,
        "end_status": end_status,
        "campaigns_run": campaigns_run,
        "total_counties": len(SHARD2_COUNTIES),
        "execution_timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    try:
        insight_data = {
            "insight_type": "campaign_results",
            "title": "Gold Standard SHARD-2 Campaign Results",
            "summary": f"Executed {len(campaigns_run)} letter campaigns across {len(SHARD2_COUNTIES)} counties",
            "data": results,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        r = requests.post(f"{BASE}/insights", headers=HEADERS, json=insight_data)
        if r.status_code == 201:
            log("Campaign results saved to insights table")
    except Exception as e:
        log(f"Error saving results: {e}")

def main():
    parser = argparse.ArgumentParser(description="Gold Standard SHARD-2 Campaign")
    parser.add_argument("--letter", choices=['B', 'I', 'J'], help="Run single letter campaign")
    parser.add_argument("--county", choices=SHARD2_COUNTIES, help="Run single county")
    parser.add_argument("--max-cases", type=int, default=100, help="Max cases per county per letter")
    parser.add_argument("--status-only", action="store_true", help="Only check status")
    parser.add_argument("--quick", action="store_true", help="Quick campaign (50 cases per letter)")
    parser.add_argument("--full", action="store_true", help="Full campaign (200 cases per letter)")
    
    args = parser.parse_args()
    
    # Determine execution mode
    if args.quick:
        max_cases = 50
    elif args.full:
        max_cases = 200
    else:
        max_cases = args.max_cases
    
    log("=" * 80)
    log("GOLD STANDARD SHARD-2 CAMPAIGN")
    log("=" * 80)
    log(f"Counties: {', '.join(SHARD2_COUNTIES)}")
    log(f"Max cases per letter: {max_cases}")
    log(f"Execution mode: {'STATUS' if args.status_only else 'CAMPAIGN'}")
    
    # Get initial status
    start_status = get_county_status()
    
    if args.status_only:
        return
    
    campaigns_run = []
    
    # Single letter mode
    if args.letter:
        script_map = {
            'B': 'gold_standard_b_verified_outcomes.py',
            'I': 'gold_standard_i_property_complete.py', 
            'J': 'gold_standard_j_deal_thesis.py'
        }
        
        if args.county:
            # Single county, single letter
            command = f"python3 scripts/{script_map[args.letter]} --county {args.county} --max-cases {max_cases}"
            run_command(command, f"Letter {args.letter} for {args.county}")
        else:
            # All counties, single letter
            run_letter_campaign(args.letter, script_map[args.letter], max_cases)
        campaigns_run = [args.letter]
        
    else:
        # Full campaign: B -> I -> J
        log("\n" + "=" * 80)
        log("EXECUTING FULL CAMPAIGN: B -> I -> J")
        log("=" * 80)
        
        # Letter B: Verified Outcomes
        run_letter_campaign('B', 'gold_standard_b_verified_outcomes.py', max_cases)
        campaigns_run.append('B')
        time.sleep(10)
        
        # Letter I: Property Card Complete
        run_letter_campaign('I', 'gold_standard_i_property_complete.py', max_cases)
        campaigns_run.append('I')
        time.sleep(10)
        
        # Letter J: Deal Thesis
        run_letter_campaign('J', 'gold_standard_j_deal_thesis.py', max_cases)
        campaigns_run.append('J')
    
    # Verification phase
    log("\n" + "=" * 80)
    log("VERIFICATION PHASE")
    log("=" * 80)
    
    for county in SHARD2_COUNTIES:
        run_verification_query(county)
        time.sleep(2)
    
    # Final status check
    log("\n" + "=" * 80)
    log("FINAL STATUS")
    log("=" * 80)
    
    end_status = get_county_status()
    
    # Calculate improvements
    log("\nIMPROVEMENT SUMMARY:")
    for county in SHARD2_COUNTIES:
        if start_status.get(county) and end_status.get(county):
            start_pass = start_status[county].get('pass_count', 0)
            end_pass = end_status[county].get('pass_count', 0)
            improvement = end_pass - start_pass
            log(f"{county}: {start_pass}/10 -> {end_pass}/10 ({improvement:+d})")
        else:
            log(f"{county}: Status unavailable")
    
    # Save results
    save_campaign_results(start_status, end_status, campaigns_run)
    
    log("\n" + "=" * 80)
    log("SHARD-2 CAMPAIGN COMPLETE")
    log("=" * 80)

if __name__ == "__main__":
    main()