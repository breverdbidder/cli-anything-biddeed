#!/usr/bin/env python3
"""
SHARD-10 Work Dispatcher: Execute Gold Standard improvements for assigned counties
This script creates GitHub workflow dispatches for counties that need work

ASSIGNED COUNTIES: manatee (51), alachua (11), martin (53), franklin (29), union (73)

Priority order based on current metrics:
1. franklin/union: 0/10 - need Letter A ingestion  
2. alachua/martin: 1/10 - need multi-letter improvements
3. manatee: 2/10 - need advanced letter improvements

SHIP-TO-MAIN: All work commits directly to main branch per fleet mandate
"""
import subprocess
import sys
import json
import time
from datetime import datetime

# SHARD-10 county assignments with work priorities
SHARD_10_WORK_PLAN = {
    'franklin': {
        'co_no': 29,
        'current': '0/10', 
        'priority': 'Letter A - Full parcel ingestion',
        'workflow': 'summit-ingest-county.yml',
        'workflow_inputs': {'county': '29', 'mode': 'full'},
        'expected_improvement': 'A: FAIL → PASS',
        'urgency': 'HIGH'
    },
    'union': {
        'co_no': 73,
        'current': '0/10',
        'priority': 'Letter A - Full parcel ingestion', 
        'workflow': 'summit-ingest-county.yml',
        'workflow_inputs': {'county': '73', 'mode': 'full'},
        'expected_improvement': 'A: FAIL → PASS',
        'urgency': 'HIGH'
    },
    'alachua': {
        'co_no': 11,
        'current': '1/10',
        'priority': 'Letters H, B, C, D - Freshness and outcomes',
        'workflow': None,  # Multiple improvements needed
        'manual_actions': [
            'Run parity-court-scraper for fresh data (Letter H)',
            'Scrape Alachua clerk outcomes (Letter B)',
            'Improve parity matching (Letters C/D)'
        ],
        'urgency': 'MEDIUM'
    },
    'martin': {
        'co_no': 53, 
        'current': '1/10',
        'priority': 'Letters H, B, C, D - Freshness and outcomes',
        'workflow': None,
        'manual_actions': [
            'Run parity-court-scraper for fresh data (Letter H)', 
            'Scrape Martin clerk outcomes (Letter B)',
            'Improve parity matching (Letters C/D)',
            'Link parcels via property appraiser (Letter E)'
        ],
        'urgency': 'MEDIUM'
    },
    'manatee': {
        'co_no': 51,
        'current': '2/10',
        'priority': 'Letters B, F, C, D, E - Outcomes and linkage',
        'workflow': None,
        'manual_actions': [
            'Scrape Manatee clerk outcomes (Letter B)',
            'Verify tier1 sold amounts (Letter F)', 
            'Improve parity matching (Letters C/D)',
            'Link parcels via MCPAO (Letter E)',
            'Enable deal thesis pipeline (Letter J)'
        ],
        'urgency': 'LOW'  # Already has 2/10, other counties more critical
    }
}

def log_action(message):
    """Log timestamped action"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] {message}")

def run_command(cmd, description):
    """Run shell command and return result"""
    log_action(f"Running: {description}")
    log_action(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if result.stdout:
            log_action(f"✅ {description} succeeded")
            log_action(f"Output: {result.stdout.strip()}")
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        log_action(f"❌ {description} failed")
        log_action(f"Error: {e.stderr}")
        return False, e.stderr

def dispatch_workflow(workflow_name, inputs):
    """Dispatch a GitHub workflow with inputs"""
    cmd = ['gh', 'workflow', 'run', workflow_name]
    
    for key, value in inputs.items():
        cmd.extend(['-f', f'{key}={value}'])
    
    return run_command(cmd, f"Dispatch {workflow_name}")

def check_workflow_status(workflow_name, limit=3):
    """Check recent workflow runs"""
    cmd = ['gh', 'run', 'list', '--workflow', workflow_name, '--limit', str(limit), '--json', 'status,conclusion,createdAt']
    
    success, output = run_command(cmd, f"Check {workflow_name} status")
    if success:
        try:
            runs = json.loads(output)
            for run in runs:
                status = run.get('status', 'unknown')
                conclusion = run.get('conclusion', 'unknown')
                created = run.get('createdAt', 'unknown')
                log_action(f"  Run: {status}/{conclusion} at {created}")
        except json.JSONDecodeError:
            log_action(f"Could not parse workflow status")

def execute_shard10_work():
    """Execute the SHARD-10 work plan"""
    
    log_action("🏔️ SHARD-10 WORK DISPATCHER STARTING")
    log_action("Assigned counties: manatee, alachua, martin, franklin, union")
    log_action("Fleet session goal: Move metrics on highest-leverage failing letters")
    
    # Phase 1: HIGH urgency - 0/10 counties need Letter A
    high_priority = {k: v for k, v in SHARD_10_WORK_PLAN.items() if v['urgency'] == 'HIGH'}
    
    log_action(f"\n🚨 PHASE 1: HIGH PRIORITY - {len(high_priority)} counties need Letter A")
    
    for county, plan in high_priority.items():
        log_action(f"\n--- {county.upper()} (CO_NO {plan['co_no']}) ---")
        log_action(f"Current: {plan['current']}")
        log_action(f"Priority: {plan['priority']}")
        log_action(f"Expected: {plan['expected_improvement']}")
        
        if plan['workflow']:
            # Dispatch the workflow
            success, output = dispatch_workflow(plan['workflow'], plan['workflow_inputs'])
            
            if success:
                log_action(f"✅ Dispatched {plan['workflow']} for {county}")
                log_action("⏳ Waiting 30s for workflow to initialize...")
                time.sleep(30)
                check_workflow_status(plan['workflow'])
            else:
                log_action(f"❌ Failed to dispatch workflow for {county}")
    
    # Phase 2: Check if we can proceed to medium priority
    log_action(f"\n📊 PHASE 2: STATUS CHECK")
    log_action("Checking if HIGH priority counties are processing...")
    
    for county, plan in high_priority.items():
        if plan['workflow']:
            check_workflow_status(plan['workflow'], 1)
    
    # Phase 3: Medium priority work (requires manual intervention)
    medium_priority = {k: v for k, v in SHARD_10_WORK_PLAN.items() if v['urgency'] == 'MEDIUM'}
    
    log_action(f"\n⚠️ PHASE 3: MEDIUM PRIORITY - {len(medium_priority)} counties")
    log_action("These require manual execution of multiple scripts")
    
    for county, plan in medium_priority.items():
        log_action(f"\n--- {county.upper()} (CO_NO {plan['co_no']}) ---")
        log_action(f"Current: {plan['current']}")
        log_action(f"Priority: {plan['priority']}")
        
        if plan.get('manual_actions'):
            log_action("Manual actions needed:")
            for i, action in enumerate(plan['manual_actions'], 1):
                log_action(f"  {i}. {action}")
    
    # Summary
    log_action(f"\n📋 SHARD-10 EXECUTION SUMMARY")
    log_action(f"HIGH priority dispatched: {len(high_priority)} counties (Letter A ingestion)")
    log_action(f"MEDIUM priority identified: {len(medium_priority)} counties (multi-letter work)")
    log_action(f"Total counties in shard: {len(SHARD_10_WORK_PLAN)}")
    
    log_action("\n⏭️ NEXT STEPS:")
    log_action("1. Monitor HIGH priority workflows in GitHub Actions")
    log_action("2. Once Letter A completes, verify with: SELECT public.pencil_dod_evaluate_county('franklin|union')")
    log_action("3. Execute MEDIUM priority manual actions")
    log_action("4. Run final verification: SELECT public.gold_standard_loop(); SELECT public.gold_standard_certify();")
    
    log_action("\n🔗 MONITORING LINKS:")
    log_action("- Workflows: https://github.com/breverdbidder/cli-anything-biddeed/actions")
    log_action("- Ingest workflow: https://github.com/breverdbidder/cli-anything-biddeed/actions/workflows/summit-ingest-county.yml")

if __name__ == "__main__":
    execute_shard10_work()