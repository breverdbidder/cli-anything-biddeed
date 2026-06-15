#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-9: palm_beach, escambia, okaloosa, dixie, taylor
6-hour autonomous session coordinator with ULTRALOOP verification protocol.

SESSION MANDATE:
- Ship directly to main (no side branches)  
- ULTRALOOP: adversarial verification of all claims
- WIRING MANDATE: schedule and execute all scrapers/pipelines
- Evidence-before-claims with VERIFIED/UNTESTED/INFERRED tags

COUNTY STATUS (from issue brief):
- palm_beach: 2/10 (A✓ H✓, priority B,C,D,E,F,G,I,J)
- escambia: 1/10 (A✓, priority B,C,D,E,F,G,H,I,J) 
- okaloosa: 1/10 (A✓, priority B,C,D,E,F,G,H,I,J)
- dixie: 0/10 (all letters failing)
- taylor: 0/10 (all letters failing)
"""
import os
import sys
import time
import json
import httpx
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any

# Shard-9 counties (ONLY work on these)
SHARD_COUNTIES = {
    'palm_beach': {'co_no': 50, 'brief_status': '2/10', 'priority': 1},
    'escambia': {'co_no': 17, 'brief_status': '1/10', 'priority': 2},  
    'okaloosa': {'co_no': 47, 'brief_status': '1/10', 'priority': 3},
    'dixie': {'co_no': 29, 'brief_status': '0/10', 'priority': 4},
    'taylor': {'co_no': 65, 'brief_status': '0/10', 'priority': 5}
}

# Letter priorities based on issue analysis
LETTER_PRIORITIES = {
    'A': 'Dual-product coverage - bootstrap counties without data',
    'B': 'Verified outcomes >=95% - CRITICAL for certification',
    'C': 'Parity clean >=95% - matching accuracy', 
    'D': 'Parity any >=95% - coverage breadth',
    'E': 'Parcel linkage >=95% - enables downstream flows',
    'F': 'Tier1 sold >=95% - financial verification',
    'G': 'Zoning coverage >=95% - density/FAR/parking',
    'H': 'Freshness <=48h - data currency',
    'I': 'Property card complete >=95% - address+geo+value+zone',
    'J': 'Deal thesis >=95% - Shapira formula pipeline'
}

# Supabase connection (per CLAUDE.md)
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

client = httpx.Client(timeout=120, headers={"User-Agent": "GoldStandard-SHARD9-Coordinator"})

def log_action(msg: str, level: str = "INFO", honesty_tag: str = "UNTESTED"):
    """Log with timestamp, level, and honesty protocol tag"""
    timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{timestamp}] {level} [{honesty_tag}]: {msg}")

def sb_headers():
    """Supabase request headers"""
    if not SUPABASE_KEY:
        log_action("No SUPABASE_KEY available - running in dry-run mode", "WARN", "VERIFIED")
        return None
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

def sb_rpc(function_name: str, params: Dict = None) -> Any:
    """Execute Supabase RPC function"""
    headers = sb_headers()
    if not headers:
        log_action(f"RPC {function_name}: SKIPPED (no auth)", "WARN", "VERIFIED")
        return None
        
    try:
        payload = params or {}
        
        response = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/{function_name}",
            headers=headers, 
            json=payload
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            log_action(f"RPC {function_name} failed: {response.status_code} {response.text[:200]}", "ERROR", "VERIFIED")
            return None
            
    except Exception as e:
        log_action(f"RPC {function_name} error: {e}", "ERROR", "VERIFIED")
        return None

def verify_connection() -> bool:
    """ULTRALOOP: Verify database connectivity"""
    log_action("Testing database connectivity...", "INFO", "UNTESTED")
    
    headers = sb_headers()
    if not headers:
        log_action("Database connection: SKIPPED (no auth)", "WARN", "VERIFIED")
        return False
        
    try:
        response = client.get(f"{SUPABASE_URL}/rest/v1/fl_counties?select=count&limit=1", headers=headers)
        
        if response.status_code == 200:
            log_action("Database connection successful", "INFO", "VERIFIED")
            return True
        else:
            log_action(f"Database connection failed: {response.status_code}", "ERROR", "VERIFIED") 
            return False
            
    except Exception as e:
        log_action(f"Database connection error: {e}", "ERROR", "VERIFIED")
        return False

def evaluate_county_live(county_slug: str) -> Dict:
    """ULTRALOOP: Get live county evaluation using pencil_dod_evaluate_county"""
    log_action(f"Evaluating {county_slug} live status...", "INFO", "UNTESTED")
    
    result = sb_rpc("pencil_dod_evaluate_county", {"county_slug_arg": county_slug})
    
    if result:
        pass_count = sum(1 for item in result if item.get('pass', False))
        log_action(f"{county_slug} evaluation: {pass_count}/10 PASS", "INFO", "VERIFIED")
        return {'result': result, 'pass_count': pass_count, 'county': county_slug}
    else:
        log_action(f"{county_slug} evaluation: FAILED", "ERROR", "VERIFIED")
        return {'result': None, 'pass_count': 0, 'county': county_slug}

def analyze_failing_letters(county_data: Dict) -> List[str]:
    """Identify failing letters for a county"""
    if not county_data.get('result'):
        return list(LETTER_PRIORITIES.keys())  # All letters failing
    
    failing = []
    for item in county_data['result']:
        if not item.get('pass', False):
            failing.append(item.get('letter', '?'))
    
    return failing

def prioritize_work(county_evaluations: Dict) -> List[Tuple[str, str, int]]:
    """
    Prioritize work across counties and letters
    Returns: List of (county, letter, priority_score)
    """
    work_items = []
    
    for county, eval_data in county_evaluations.items():
        county_priority = SHARD_COUNTIES[county]['priority']
        failing_letters = analyze_failing_letters(eval_data)
        
        for letter in failing_letters:
            # Calculate priority score (lower = higher priority)
            letter_score = ord(letter) - ord('A')  # A=0, B=1, etc
            priority_score = (county_priority * 10) + letter_score
            work_items.append((county, letter, priority_score))
    
    # Sort by priority score (ascending = highest priority first)
    return sorted(work_items, key=lambda x: x[2])

def execute_letter_fix(county: str, letter: str) -> bool:
    """
    Execute fix for a specific letter in a county
    Returns: True if fix was successful
    """
    log_action(f"Executing {county} letter {letter} fix...", "INFO", "UNTESTED")
    
    # For now, this is a placeholder - would implement specific fixes per letter
    letter_description = LETTER_PRIORITIES.get(letter, f"Letter {letter}")
    log_action(f"{county} {letter}: {letter_description}", "INFO", "INFERRED")
    
    # TODO: Implement actual letter-specific fixes based on:
    # - A: Configure lanes (realauction + clerk_html)  
    # - B: Build verified outcome scrapers
    # - C/D: Fix parity matching 
    # - E: Parcel ID linkage via county GIS
    # - F: Tier1 promotion from verified outcomes
    # - G: Zoning districts and standards
    # - H: Freshness via scraper scheduling
    # - I: Property card enrichment  
    # - J: Bid decisions pipeline
    
    log_action(f"{county} {letter}: FIX IMPLEMENTED (placeholder)", "INFO", "UNTESTED")
    return True

def verify_letter_fix(county: str, letter: str) -> bool:
    """
    ULTRALOOP: Verify that a letter fix actually worked
    """
    log_action(f"Verifying {county} letter {letter} fix...", "INFO", "UNTESTED")
    
    # Re-evaluate the county to check if the letter now passes
    eval_result = evaluate_county_live(county)
    
    if eval_result.get('result'):
        for item in eval_result['result']:
            if item.get('letter') == letter and item.get('pass', False):
                log_action(f"{county} {letter}: VERIFICATION PASSED", "INFO", "VERIFIED")
                return True
    
    log_action(f"{county} {letter}: VERIFICATION FAILED", "ERROR", "VERIFIED")
    return False

def run_shard9_autonomous_session():
    """
    Main autonomous execution loop for SHARD-9
    """
    log_action("🎯 SHARD-9 AUTONOMOUS SESSION START", "INFO", "VERIFIED")
    log_action(f"Counties: {', '.join(SHARD_COUNTIES.keys())}", "INFO", "VERIFIED")
    
    session_start = time.time()
    max_duration = 6 * 60 * 60  # 6 hours in seconds
    
    # Initial verification
    if not verify_connection():
        log_action("Session aborted: Database connection failed", "ERROR", "VERIFIED")
        return False
    
    # Evaluate all counties to get baseline status
    log_action("📊 BASELINE EVALUATION", "INFO", "VERIFIED")
    county_evaluations = {}
    
    for county in SHARD_COUNTIES.keys():
        eval_data = evaluate_county_live(county)
        county_evaluations[county] = eval_data
        
        status = f"{eval_data['pass_count']}/10"
        log_action(f"{county}: {status}", "INFO", "VERIFIED")
    
    # Prioritize work items
    work_queue = prioritize_work(county_evaluations)
    log_action(f"Work queue: {len(work_queue)} items prioritized", "INFO", "VERIFIED")
    
    # Execute fixes in priority order
    fixes_completed = 0
    fixes_successful = 0
    
    for county, letter, priority_score in work_queue:
        elapsed = time.time() - session_start
        remaining = max_duration - elapsed
        
        if remaining < 30 * 60:  # Stop if less than 30 minutes remaining
            log_action(f"Session time limit approaching: {remaining/60:.1f}min remaining", "WARN", "VERIFIED")
            break
        
        log_action(f"Working on: {county} {letter} (priority {priority_score})", "INFO", "VERIFIED")
        
        # Execute fix
        if execute_letter_fix(county, letter):
            # Verify fix worked
            if verify_letter_fix(county, letter):
                fixes_successful += 1
                log_action(f"✅ {county} {letter}: COMPLETED", "INFO", "VERIFIED")
            else:
                log_action(f"❌ {county} {letter}: FIX FAILED VERIFICATION", "ERROR", "VERIFIED")
        else:
            log_action(f"❌ {county} {letter}: EXECUTION FAILED", "ERROR", "VERIFIED")
        
        fixes_completed += 1
        
        # Brief pause between fixes
        time.sleep(1)
    
    # Final evaluation
    log_action("📈 FINAL EVALUATION", "INFO", "VERIFIED")
    final_evaluations = {}
    
    for county in SHARD_COUNTIES.keys():
        eval_data = evaluate_county_live(county)
        final_evaluations[county] = eval_data
        
        baseline = county_evaluations[county]['pass_count']
        final = eval_data['pass_count']
        improvement = final - baseline
        
        status_emoji = "✅" if improvement > 0 else "📊" if improvement == 0 else "❌"
        log_action(f"{county}: {baseline}/10 → {final}/10 ({improvement:+d}) {status_emoji}", "INFO", "VERIFIED")
    
    # Session summary
    elapsed_min = (time.time() - session_start) / 60
    log_action("🏁 SHARD-9 SESSION COMPLETE", "INFO", "VERIFIED")
    log_action(f"Duration: {elapsed_min:.1f} minutes", "INFO", "VERIFIED")
    log_action(f"Fixes attempted: {fixes_completed}", "INFO", "VERIFIED")  
    log_action(f"Fixes successful: {fixes_successful}", "INFO", "VERIFIED")
    
    return True

if __name__ == "__main__":
    success = run_shard9_autonomous_session()
    sys.exit(0 if success else 1)