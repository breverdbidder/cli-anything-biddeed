#!/usr/bin/env python3
"""
SHARD BREVARD+DUVAL AUTONOMOUS SESSION - Gold Standard Autopilot
AUTOPILOT RUN 20 - SHIP-TO-MAIN

Assigned shard (loop run 20):
- brevard (2/10): A✓ H✓ | B=134.1% ANOMALY | C=20.9 | D=34.0 | E=73.9 | F=40.6 | G=48.9 | I=34.5 | J=0
- duval (2/10):   A✓ H✓ | B=110.2% ANOMALY | C=16.1 | D=52.9 | E=79.2 | F=63.3 | G=null | I=null | J=0

PRIORITY ORDERS (from issue briefing):
BREVARD: 1) C/D ROOT CAUSE → 2) J GENERATOR → 3) G HIT LIST → 4) B RECONCILIATION
DUVAL:   1) G+I SUBSTRATE → 2) C/D ROOT CAUSE → 3) J GENERATOR → 4) B RECONCILIATION

Usage:
  python scripts/shard_brevard_duval_autonomous.py --execute-session
"""
import os
import sys
import json
import httpx
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import logging
import argparse

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

# Our shard assignment
TARGET_COUNTIES = ['brevard', 'duval']

# County DOR numbers for reference
COUNTY_DOR_NUMBERS = {
    'brevard': 9,   # Brevard County
    'duval': 16     # Duval County
}

client = httpx.Client(timeout=120)  # Extended timeout for long operations

def log(message, level="INFO"):
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"[{timestamp}] {level}: {message}")
    if level == "ERROR":
        logger.error(message)
    else:
        logger.info(message)

def verify_database_connection():
    """Test Supabase connection and permissions - VERIFIED approach"""
    try:
        response = client.get(f"{BASE}/audit_log", headers=HEADERS, params={"limit": "1"})
        if response.status_code == 200:
            log("✅ Supabase connection successful")
            return True
        else:
            log(f"❌ Connection failed: {response.status_code} - {response.text}", "ERROR")
            return False
    except Exception as e:
        log(f"❌ Connection error: {e}", "ERROR")
        return False

def get_current_metrics():
    """Get current A-J metrics for both counties - VERIFIED approach"""
    log("📊 Getting current metrics for brevard and duval counties")
    
    metrics = {}
    
    for county in TARGET_COUNTIES:
        try:
            # Use pencil_dod_evaluate_county function per briefing
            payload = {"county_name": county}
            response = client.post(
                f"{BASE}/rpc/pencil_dod_evaluate_county",
                headers=HEADERS,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                evaluation = response.json()
                
                # Extract all letter metrics
                county_metrics = {}
                passing_count = 0
                
                for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
                    grade_field = f"grade_{letter.lower()}"
                    metric_field = f"metric_{letter.lower()}"
                    
                    grade = evaluation.get(grade_field, 'UNKNOWN')
                    metric = evaluation.get(metric_field)
                    
                    county_metrics[letter] = {
                        'grade': grade,
                        'metric': metric,
                        'passing': grade == 'PASS'
                    }
                    
                    if grade == 'PASS':
                        passing_count += 1
                
                metrics[county] = {
                    'score': f"{passing_count}/10",
                    'letters': county_metrics,
                    'sql_evidence': f"SELECT public.pencil_dod_evaluate_county('{county}')",
                    'verification_status': "VERIFIED",
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                
                # Log summary
                status_str = " ".join([f"{letter}:{data['grade'][:4]}" for letter, data in county_metrics.items()])
                log(f"{county.upper()}: {passing_count}/10 | {status_str}")
                
            else:
                log(f"Failed to get metrics for {county}: {response.status_code}", "ERROR")
                
        except Exception as e:
            log(f"Error getting metrics for {county}: {e}", "ERROR")
    
    return metrics

def identify_priority_work(metrics: Dict):
    """Identify next priority work items based on briefing directives - INFERRED from metrics"""
    log("🎯 Identifying priority work items per briefing order")
    
    priorities = {}
    
    for county, data in metrics.items():
        letters = data.get('letters', {})
        failing_letters = [letter for letter, info in letters.items() if not info.get('passing', False)]
        
        county_priorities = []
        
        if county == 'brevard':
            # BREVARD Priority Order per briefing
            if 'C' in failing_letters or 'D' in failing_letters:
                county_priorities.append({
                    'task': 'C/D ROOT CAUSE', 
                    'description': 'clerk/official-records litmus (pre-authorized)',
                    'letters': ['C', 'D'],
                    'urgency': 'HIGH'
                })
            
            if 'J' in failing_letters:
                county_priorities.append({
                    'task': 'J GENERATOR',
                    'description': 'bid_decisions pipeline',
                    'letters': ['J'],
                    'urgency': 'HIGH'
                })
            
            if 'G' in failing_letters:
                county_priorities.append({
                    'task': 'G HIT LIST',
                    'description': 'zone_standards backfill for ~15 districts',
                    'letters': ['G'],
                    'urgency': 'MEDIUM'
                })
            
            if 'B' in failing_letters and letters.get('B', {}).get('metric', 0) > 105:
                county_priorities.append({
                    'task': 'B RECONCILIATION',
                    'description': 'fix 134.1% anomaly',
                    'letters': ['B'],
                    'urgency': 'MEDIUM'
                })
        
        elif county == 'duval':
            # DUVAL Priority Order per briefing
            if 'G' in failing_letters or 'I' in failing_letters:
                county_priorities.append({
                    'task': 'G+I SUBSTRATE BUILD',
                    'description': 'parcel_zones and zoning_districts',
                    'letters': ['G', 'I'],
                    'urgency': 'HIGH'
                })
            
            if 'C' in failing_letters or 'D' in failing_letters:
                county_priorities.append({
                    'task': 'C/D ROOT CAUSE',
                    'description': 'clerk/official-records litmus',
                    'letters': ['C', 'D'],
                    'urgency': 'HIGH'
                })
            
            if 'J' in failing_letters:
                county_priorities.append({
                    'task': 'J GENERATOR',
                    'description': 'if not built by brevard shard',
                    'letters': ['J'],
                    'urgency': 'HIGH'
                })
            
            if 'B' in failing_letters and letters.get('B', {}).get('metric', 0) > 105:
                county_priorities.append({
                    'task': 'B RECONCILIATION',
                    'description': 'fix 110.2% anomaly',
                    'letters': ['B'],
                    'urgency': 'MEDIUM'
                })
        
        priorities[county] = county_priorities
    
    return priorities

def report_session_plan(metrics: Dict, priorities: Dict):
    """Generate session plan report - VERIFIED"""
    log("📋 GENERATING SESSION PLAN")
    print("\n" + "="*80)
    print("SHARD BREVARD+DUVAL AUTONOMOUS SESSION PLAN")
    print("="*80)
    
    print(f"\n🕒 Session Start: {datetime.now(timezone.utc).isoformat()}")
    print("⏱️  Budget: 6 hours (GitHub Actions ceiling)")
    print("🚢 Ship-to-Main: All work commits directly to main branch")
    print("📝 Verification: SQL proof required for every metric change")
    
    print(f"\n📊 Current Status:")
    for county, data in metrics.items():
        score = data.get('score', 'N/A')
        print(f"  {county.upper()}: {score}")
        
        for letter, info in data.get('letters', {}).items():
            grade = info.get('grade', 'UNKNOWN')
            metric = info.get('metric', 'null')
            status = "✅" if grade == "PASS" else "❌"
            print(f"    {letter}: {status} {grade} [metric={metric}]")
    
    print(f"\n🎯 Priority Work Plan:")
    for county, county_priorities in priorities.items():
        if county_priorities:
            print(f"\n  {county.upper()} PRIORITIES:")
            for i, task in enumerate(county_priorities, 1):
                print(f"    {i}. {task['task']}: {task['description']}")
                print(f"       Letters: {', '.join(task['letters'])} | Urgency: {task['urgency']}")
    
    print(f"\n📋 Verification Protocol:")
    print("  - Use pencil_dod_evaluate_county() before and after each fix")
    print("  - Log SQL VERIFICATION blocks with exact queries")
    print("  - HONESTY PROTOCOL: VERIFIED/UNTESTED/INFERRED tags required")
    print("  - Evidence-before-claims: Execute → Verify → Read output → Compare → Claim")

def execute_session(args):
    """Execute the autonomous session workflow"""
    log("🚀 Starting SHARD BREVARD+DUVAL autonomous session")
    
    # Pre-flight checks
    if not SUPABASE_KEY:
        log("❌ No SUPABASE_KEY found", "ERROR")
        return False
    
    if not verify_database_connection():
        log("❌ Database connection failed", "ERROR") 
        return False
    
    # Get baseline metrics
    log("📊 STEP 1: Baseline metrics assessment")
    baseline_metrics = get_current_metrics()
    
    if not baseline_metrics:
        log("❌ Failed to get baseline metrics", "ERROR")
        return False
    
    # Identify work priorities
    log("🎯 STEP 2: Priority identification") 
    priorities = identify_priority_work(baseline_metrics)
    
    # Report plan
    report_session_plan(baseline_metrics, priorities)
    
    # NOTE: Actual work execution would continue here with specific letter implementations
    # This is the coordination script - specific letter work will be in separate scripts
    
    log("✅ Session coordination complete - ready for letter-specific work")
    return True

def main():
    parser = argparse.ArgumentParser(description="SHARD BREVARD+DUVAL Autonomous Session")
    parser.add_argument("--execute-session", action="store_true", 
                       help="Execute full autonomous session")
    parser.add_argument("--metrics-only", action="store_true",
                       help="Get current metrics only")
    
    args = parser.parse_args()
    
    if args.execute_session:
        success = execute_session(args)
        sys.exit(0 if success else 1)
    elif args.metrics_only:
        metrics = get_current_metrics()
        if metrics:
            print(json.dumps(metrics, indent=2))
        sys.exit(0 if metrics else 1)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()