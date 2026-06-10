#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-3 Master Execution Pipeline
==============================================
Master controller that executes all SHARD-3 scripts in sequence to achieve 
10/10 gold standard status for assigned counties.

Execution sequence:
1. County bootstrap (Letter A - dual product coverage)
2. Verified outcomes (Letter B - independent verification)  
3. Parity & freshness (Letters C, D, F, H)
4. Gold standard pipeline (Letters G, I, J)
5. Verification protocol
6. Scoreboard reporting

Target counties: sumter, clay, jackson, okeechobee, columbia, hamilton, madison

Usage:
  python scripts/shard3_master_execution.py --county sumter
  python scripts/shard3_master_execution.py --all-counties
  python scripts/shard3_master_execution.py --verify-only
"""
import os
import sys
import argparse
import subprocess
import httpx
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# SHARD-3 Counties with current status from issue
SHARD3_COUNTIES = {
    'sumter': {'co_no': 70, 'current_status': '2/10', 'priority': 1, 'failing_letters': ['A', 'B', 'C', 'F', 'G', 'H', 'I', 'J']},
    'clay': {'co_no': 20, 'current_status': '1/10', 'priority': 2, 'failing_letters': ['B', 'C', 'D', 'F', 'G', 'H', 'I', 'J']}, 
    'jackson': {'co_no': 42, 'current_status': '1/10', 'priority': 3, 'failing_letters': ['B', 'C', 'F', 'G', 'H', 'I', 'J']},
    'okeechobee': {'co_no': 57, 'current_status': '1/10', 'priority': 4, 'failing_letters': ['B', 'C', 'F', 'G', 'H', 'I', 'J']},
    'columbia': {'co_no': 22, 'current_status': '0/10', 'priority': 5, 'failing_letters': ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']},
    'hamilton': {'co_no': 34, 'current_status': '0/10', 'priority': 6, 'failing_letters': ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']},
    'madison': {'co_no': 50, 'current_status': '0/10', 'priority': 7, 'failing_letters': ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']}
}

# Script execution sequence
EXECUTION_SEQUENCE = [
    {
        'name': 'County Bootstrap',
        'script': 'scripts/shard3_county_bootstrap.py',
        'letters': ['A'],
        'description': 'Sets up dual product coverage (foreclosure + tax deed)',
        'required_for': 'all counties'
    },
    {
        'name': 'Verified Outcomes', 
        'script': 'scripts/shard3_verified_outcomes.py',
        'letters': ['B'],
        'description': 'Creates independent verified outcome records',
        'required_for': 'all counties'
    },
    {
        'name': 'Parity & Freshness',
        'script': 'scripts/shard3_parity_and_freshness.py', 
        'letters': ['C', 'D', 'F', 'H'],
        'description': 'Fixes parity matching and freshness SLA',
        'required_for': 'counties with auction data'
    },
    {
        'name': 'Gold Standard Pipeline',
        'script': 'scripts/shard3_gold_standard_pipeline.py',
        'letters': ['G', 'I', 'J'],
        'description': 'Zoning KPI, property cards, and deal thesis',
        'required_for': 'all counties'
    }
]

def sb_headers():
    """Supabase REST API headers"""
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def sb_rpc(function_name, params=None):
    """Call Supabase RPC function"""
    client = httpx.Client(timeout=60)
    r = client.post(f"{SUPABASE_URL}/rest/v1/rpc/{function_name}", headers=sb_headers(), json=params or {})
    return r.json() if r.status_code == 200 else None

def run_script(script_path, args, timeout=1800):
    """Run a Python script with arguments"""
    try:
        cmd = ['python3', script_path] + args
        print(f"🚀 Running: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=timeout,
            cwd=os.path.dirname(os.path.abspath(__file__ + '/../'))
        )
        
        if result.returncode == 0:
            print(f"✅ Script completed successfully")
            if result.stdout.strip():
                print(f"Output: {result.stdout[-500:]}")  # Last 500 chars
            return True
        else:
            print(f"❌ Script failed with return code {result.returncode}")
            if result.stderr:
                print(f"Error: {result.stderr}")
            if result.stdout:
                print(f"Output: {result.stdout}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"⏰ Script timed out after {timeout} seconds")
        return False
    except Exception as e:
        print(f"❌ Error running script: {e}")
        return False

def get_county_evaluation(county_slug):
    """Get current gold standard evaluation for a county"""
    try:
        result = sb_rpc('pencil_dod_evaluate_county', {'p_county': county_slug})
        if result:
            letters_status = {}
            pass_count = 0
            
            for letter_data in result:
                letter = letter_data.get('letter', '?')
                passed = letter_data.get('pass', False)
                metric = letter_data.get('metric')
                
                letters_status[letter] = {
                    'passed': passed,
                    'metric': metric,
                    'details': letter_data.get('details', '')
                }
                
                if passed:
                    pass_count += 1
            
            return {
                'pass_count': pass_count,
                'total_letters': len(letters_status),
                'letters': letters_status,
                'gold_standard': pass_count == 10
            }
        else:
            print(f"❌ Failed to evaluate {county_slug}")
            return None
            
    except Exception as e:
        print(f"❌ Error evaluating {county_slug}: {e}")
        return None

def execute_county_pipeline(county_slug, skip_steps=None):
    """Execute full pipeline for a single county"""
    skip_steps = skip_steps or []
    
    print(f"\n{'='*80}")
    print(f"EXECUTING GOLD STANDARD PIPELINE FOR {county_slug.upper()}")
    print(f"{'='*80}")
    
    county_info = SHARD3_COUNTIES.get(county_slug, {})
    current_status = county_info.get('current_status', 'unknown')
    failing_letters = county_info.get('failing_letters', [])
    
    print(f"Current status: {current_status}")
    print(f"Failing letters: {', '.join(failing_letters)}")
    
    # Get baseline evaluation
    print(f"\n📊 Baseline evaluation...")
    baseline_eval = get_county_evaluation(county_slug)
    baseline_pass_count = baseline_eval['pass_count'] if baseline_eval else 0
    print(f"Baseline: {baseline_pass_count}/10 letters passing")
    
    # Execute sequence
    step_results = []
    
    for i, step in enumerate(EXECUTION_SEQUENCE, 1):
        step_name = step['name']
        
        if step_name in skip_steps:
            print(f"\n⏭️ Step {i}: Skipping {step_name}")
            continue
            
        print(f"\n🎯 Step {i}: {step_name}")
        print(f"   Letters: {', '.join(step['letters'])}")
        print(f"   Description: {step['description']}")
        
        # Check if this step is needed for this county
        step_letters = step['letters']
        relevant_letters = [l for l in step_letters if l in failing_letters]
        
        if not relevant_letters:
            print(f"   ✅ No failing letters for this step in {county_slug}")
            step_results.append((step_name, True, []))
            continue
        
        print(f"   📋 Relevant letters: {', '.join(relevant_letters)}")
        
        # Run the script
        script_args = ['--county', county_slug]
        success = run_script(step['script'], script_args)
        
        step_results.append((step_name, success, relevant_letters))
        
        if success:
            print(f"   ✅ {step_name} completed")
        else:
            print(f"   ❌ {step_name} failed")
            
        time.sleep(2)  # Brief pause between steps
    
    # Final evaluation
    print(f"\n📊 Final evaluation...")
    final_eval = get_county_evaluation(county_slug)
    final_pass_count = final_eval['pass_count'] if final_eval else 0
    
    improvement = final_pass_count - baseline_pass_count
    
    print(f"\n🎯 RESULTS FOR {county_slug.upper()}:")
    print(f"   Baseline: {baseline_pass_count}/10 letters")
    print(f"   Final: {final_pass_count}/10 letters")
    print(f"   Improvement: +{improvement} letters")
    print(f"   Gold Standard: {'✅ ACHIEVED' if final_pass_count == 10 else '❌ NOT YET'}")
    
    # Detailed letter breakdown
    if final_eval and final_eval['letters']:
        print(f"\n📋 Letter Status:")
        for letter, status in final_eval['letters'].items():
            status_icon = "✅" if status['passed'] else "❌"
            metric = status.get('metric', 'N/A')
            print(f"   {letter}: {status_icon} {metric}")
    
    # Step summary
    print(f"\n📈 Step Results:")
    for step_name, success, letters in step_results:
        status_icon = "✅" if success else "❌"
        letters_str = f"({', '.join(letters)})" if letters else "(skipped)"
        print(f"   {status_icon} {step_name} {letters_str}")
    
    return {
        'county': county_slug,
        'baseline_pass_count': baseline_pass_count,
        'final_pass_count': final_pass_count,
        'improvement': improvement,
        'gold_standard': final_pass_count == 10,
        'step_results': step_results,
        'final_evaluation': final_eval
    }

def run_gold_standard_loop():
    """Run the gold standard loop and certification"""
    print(f"\n🔄 Running gold standard loop and certification...")
    
    try:
        # Run the gold standard loop
        print("   Running gold_standard_loop()...")
        loop_result = sb_rpc('gold_standard_loop')
        
        # Run certification
        print("   Running gold_standard_certify()...")
        cert_result = sb_rpc('gold_standard_certify')
        
        print("   ✅ Gold standard loop completed")
        return True
        
    except Exception as e:
        print(f"   ❌ Error running gold standard loop: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='SHARD-3 Master Execution Pipeline')
    parser.add_argument('--county', choices=list(SHARD3_COUNTIES.keys()),
                       help='Execute pipeline for specific county')
    parser.add_argument('--all-counties', action='store_true',
                       help='Execute pipeline for all SHARD-3 counties')
    parser.add_argument('--verify-only', action='store_true',
                       help='Run verification protocol only (no execution)')
    parser.add_argument('--skip-steps', nargs='+', 
                       choices=[step['name'] for step in EXECUTION_SEQUENCE],
                       help='Skip specific pipeline steps')
    parser.add_argument('--timeout', type=int, default=1800,
                       help='Timeout per script in seconds (default: 1800)')
    args = parser.parse_args()
    
    if not SUPABASE_KEY:
        print("❌ SUPABASE_KEY environment variable not set")
        sys.exit(1)
    
    print("GOLD STANDARD SHARD-3 Master Execution Pipeline")
    print("=" * 80)
    print(f"Session started: {datetime.utcnow().isoformat()}Z")
    
    counties_to_process = []
    if args.county:
        counties_to_process = [args.county]
    elif args.all_counties:
        # Process in priority order (highest current status first)
        counties_to_process = sorted(SHARD3_COUNTIES.keys(), 
                                   key=lambda x: SHARD3_COUNTIES[x]['priority'])
    elif args.verify_only:
        counties_to_process = list(SHARD3_COUNTIES.keys())
    else:
        parser.print_help()
        return
    
    print(f"Target counties: {', '.join(counties_to_process)}")
    if args.skip_steps:
        print(f"Skipping steps: {', '.join(args.skip_steps)}")
    
    # Verification only mode
    if args.verify_only:
        print(f"\n🔍 VERIFICATION MODE - Status check only")
        
        for county in counties_to_process:
            print(f"\n--- {county.upper()} ---")
            evaluation = get_county_evaluation(county)
            if evaluation:
                pass_count = evaluation['pass_count']
                print(f"Status: {pass_count}/10 letters passing")
                if evaluation['letters']:
                    for letter, status in evaluation['letters'].items():
                        icon = "✅" if status['passed'] else "❌"
                        print(f"  {letter}: {icon} {status.get('metric', 'N/A')}")
            else:
                print("❌ Could not evaluate county")
        
        # Run verification protocol
        run_gold_standard_loop()
        return
    
    # Full execution mode
    session_results = []
    total_improvement = 0
    gold_standard_counties = []
    
    for county in counties_to_process:
        try:
            result = execute_county_pipeline(county, args.skip_steps)
            session_results.append(result)
            total_improvement += result['improvement']
            
            if result['gold_standard']:
                gold_standard_counties.append(county)
                
        except Exception as e:
            print(f"❌ Error processing {county}: {e}")
    
    # Final verification protocol
    print(f"\n🔄 VERIFICATION PROTOCOL")
    run_gold_standard_loop()
    
    # Session summary
    print(f"\n🎯 SESSION SUMMARY")
    print(f"=" * 80)
    print(f"Counties processed: {len(session_results)}")
    print(f"Total improvement: +{total_improvement} letters")
    print(f"Gold standard achieved: {len(gold_standard_counties)} counties")
    
    if gold_standard_counties:
        print(f"✅ Gold standard counties: {', '.join(gold_standard_counties)}")
    
    # Detailed results
    print(f"\n📊 DETAILED RESULTS:")
    for result in session_results:
        county = result['county']
        baseline = result['baseline_pass_count']
        final = result['final_pass_count']
        improvement = result['improvement']
        gold = result['gold_standard']
        
        status_icon = "✅" if gold else "🔄" if improvement > 0 else "❌"
        print(f"   {status_icon} {county}: {baseline}/10 → {final}/10 (+{improvement})")
    
    print(f"\nSession completed: {datetime.utcnow().isoformat()}Z")

if __name__ == "__main__":
    main()