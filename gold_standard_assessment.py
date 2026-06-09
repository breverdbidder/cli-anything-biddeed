#!/usr/bin/env python3
"""
Gold Standard Campaign Assessment Tool
Analyzes current A-J criteria status for priority counties and executes fixes.
"""
import os
import sys
import time
import httpx
from datetime import datetime, timezone

# Supabase connection (using existing pattern from ingest_county.py)
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_KEY:
    print("ERROR: SUPABASE_KEY not set in environment")
    sys.exit(1)

client = httpx.Client(timeout=120, headers={"User-Agent": "Gold Standard Campaign Tool"})

def log(msg):
    print(f"[GS-CAMPAIGN] {datetime.now(timezone.utc).strftime('%H:%M:%S')} {msg}")

def sb_headers():
    return {
        "apikey": SUPABASE_KEY, 
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json", 
        "Prefer": "resolution=merge-duplicates"
    }

def sb_rpc(func_name, params=None):
    """Call a Supabase stored procedure"""
    h = sb_headers()
    r = client.post(f"{SUPABASE_URL}/rest/v1/rpc/{func_name}", headers=h, json=params or {})
    if r.status_code == 200:
        return r.json()
    else:
        log(f"RPC {func_name} failed: {r.status_code} {r.text[:200]}")
        return None

def sb_get(table, params=""):
    """Query a Supabase table"""
    r = client.get(f"{SUPABASE_URL}/rest/v1/{table}?{params}", headers=sb_headers())
    return r.json() if r.status_code == 200 else []

def run_baseline_assessment():
    """Run baseline assessment using existing SQL functions"""
    log("=== BASELINE ASSESSMENT ===")
    
    # 1. Check gold_standard_scoreboard for current status
    log("Fetching current gold standard scoreboard...")
    scoreboard = sb_get("gold_standard_scoreboard", "order=pass_count.desc")
    
    if not scoreboard:
        log("ERROR: No data in gold_standard_scoreboard. Running gold_standard_loop first...")
        loop_result = sb_rpc("gold_standard_loop")
        if loop_result:
            log(f"Loop completed: {loop_result}")
            scoreboard = sb_get("gold_standard_scoreboard", "order=pass_count.desc")
        else:
            log("ERROR: Failed to run gold_standard_loop")
            return None
    
    # Priority targets from issue
    priority_counties = ["charlotte", "brevard", "broward"]
    
    log("\n=== PRIORITY TARGETS ===")
    for county in priority_counties:
        county_data = next((c for c in scoreboard if c["county_slug"] == county), None)
        if county_data:
            pass_count = county_data.get("pass_count", 0)
            log(f"{county.upper()}: {pass_count}/10 criteria passing")
            
            # Get detailed status for this county
            detailed = sb_rpc("pencil_dod_evaluate_county", {"county_name": county})
            if detailed:
                log(f"  Detailed evaluation: {detailed}")
        else:
            log(f"{county.upper()}: NOT FOUND in scoreboard")
    
    return scoreboard

def analyze_failing_criteria():
    """Analyze which criteria are failing across priority counties"""
    log("\n=== ANALYZING FAILING CRITERIA ===")
    
    # Get latest county status details
    county_status = sb_get("gold_standard_county_status", 
                          "loop_run_id=eq.(select max(loop_run_id) from gold_standard_county_status)")
    
    priority_counties = ["charlotte", "brevard", "broward"]
    failing_criteria = {}
    
    for county in priority_counties:
        county_data = [c for c in county_status if c["county_slug"] == county]
        if county_data:
            county_record = county_data[0]
            log(f"\n{county.upper()} failing criteria:")
            
            # Check each A-J criterion
            criteria = ['a_dual_product', 'b_verified_outcomes', 'c_parity_clean', 
                       'd_parity_any', 'e_parcel_linkage', 'f_tier1_sold', 
                       'g_zoning', 'h_freshness', 'i_property_complete', 'j_deal_thesis']
            
            for criterion in criteria:
                if not county_record.get(criterion):  # FAIL
                    letter = criterion[0].upper()
                    metric = county_record.get(f"{letter.lower()}_metric")
                    detail = county_record.get(f"{letter.lower()}_detail", "")
                    log(f"  {letter} FAIL: metric={metric} detail={detail[:100]}")
                    
                    if criterion not in failing_criteria:
                        failing_criteria[criterion] = []
                    failing_criteria[criterion].append(county)
    
    # Prioritize by impact (how many counties affected)
    log(f"\n=== HIGH IMPACT FIXES (affecting multiple counties) ===")
    for criterion, counties in sorted(failing_criteria.items(), key=lambda x: len(x[1]), reverse=True):
        log(f"{criterion.upper()}: affects {counties}")
    
    return failing_criteria

def main():
    log("Starting Gold Standard Campaign Assessment...")
    
    # Run baseline assessment
    scoreboard = run_baseline_assessment()
    if not scoreboard:
        log("FATAL: Could not get baseline assessment")
        sys.exit(1)
    
    # Analyze failing criteria
    failing_criteria = analyze_failing_criteria()
    
    log(f"\n=== SUMMARY ===")
    log(f"Total counties evaluated: {len(scoreboard)}")
    gold_standard_counties = [c for c in scoreboard if c.get("gold_standard")]
    log(f"Counties at Gold Standard (10/10): {len(gold_standard_counties)}")
    
    if gold_standard_counties:
        for county in gold_standard_counties:
            log(f"  ✅ {county['county_slug']}")
    
    log("\n=== NEXT ACTIONS RECOMMENDED ===")
    log("Based on CLAUDE.md instructions, focus on highest-leverage failing letters")
    log("Priority order: B (verified outcomes), C/D (PropertyOnion parity), F (tier1 sold)")
    
    return scoreboard, failing_criteria

if __name__ == "__main__":
    main()