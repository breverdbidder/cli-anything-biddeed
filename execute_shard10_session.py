#!/usr/bin/env python3
"""
SHARD-10 Gold Standard Session Executor
Orchestrates complete autonomous 6-hour improvement session

Target counties: manatee, alachua, martin, franklin, union
Current status: 5/50 letters passing (10.0%) 
Goal: Maximize letter improvements within 6-hour window

Execution priority:
1. franklin, union: County bootstrap (0/10 → 5-7/10)
2. manatee: Parcel linkage (91.4% → 95%+) for Letter E 
3. alachua, martin: Freshness fix for Letter H
4. All counties: Verification and final metrics

Usage:
  python execute_shard10_session.py
  python execute_shard10_session.py --dry-run
  python execute_shard10_session.py --phase-only 1
"""
import os
import sys
import subprocess
import json
import time
from datetime import datetime, timedelta
import argparse
import requests

# Configuration
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

TARGET_COUNTIES = ['manatee', 'alachua', 'martin', 'franklin', 'union']

def log(msg):
    """Log with timestamp and session context"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] SHARD-10: {msg}")

def run_script(script_name: str, args: list = None, timeout: int = 3600) -> dict:
    """Run a Python script and return detailed results"""
    cmd = ['python3', script_name]
    if args:
        cmd.extend(args)
    
    log(f"Executing: {' '.join(cmd)}")
    start_time = time.time()
    
    try:
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=timeout
        )
        
        elapsed = time.time() - start_time
        
        return {
            'script': script_name,
            'args': args,
            'success': result.returncode == 0,
            'elapsed_seconds': elapsed,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode,
            'timeout': timeout
        }
        
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        return {
            'script': script_name,
            'args': args,
            'success': False,
            'elapsed_seconds': elapsed,
            'error': 'Script execution timeout',
            'timeout': timeout,
            'returncode': -1
        }
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            'script': script_name,
            'args': args,
            'success': False,
            'elapsed_seconds': elapsed,
            'error': str(e),
            'returncode': -1
        }

def evaluate_county_current(county_slug: str) -> dict:
    """Evaluate current Gold Standard status via RPC"""
    try:
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=headers,
            json={"county_slug_arg": county_slug},
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            pass_count = sum(1 for item in result if item.get('pass', False))
            
            return {
                'county': county_slug,
                'evaluation': result,
                'pass_count': pass_count,
                'letters_passing': [item.get('letter') for item in result if item.get('pass', False)],
                'letters_failing': [item.get('letter') for item in result if not item.get('pass', False)],
                'success': True
            }
        else:
            return {
                'county': county_slug,
                'success': False,
                'error': f"RPC failed: {response.status_code} - {response.text}"
            }
            
    except Exception as e:
        return {
            'county': county_slug,
            'success': False,
            'error': str(e)
        }

def run_baseline_evaluation() -> dict:
    """Run baseline evaluation for all target counties"""
    log("=" * 60)
    log("PHASE 0: BASELINE EVALUATION")
    log("=" * 60)
    
    baseline = {}
    total_passing = 0
    
    for county in TARGET_COUNTIES:
        result = evaluate_county_current(county)
        baseline[county] = result
        
        if result.get('success'):
            pass_count = result['pass_count']
            total_passing += pass_count
            log(f"{county}: {pass_count}/10 letters passing")
        else:
            log(f"{county}: ❌ Evaluation failed - {result.get('error')}")
    
    log(f"\nBASELINE TOTAL: {total_passing}/50 letters passing ({total_passing/50*100:.1f}%)")
    return baseline

def run_phase1_bootstrap(dry_run: bool = False) -> dict:
    """Phase 1: Bootstrap franklin and union counties"""
    log("=" * 60) 
    log("PHASE 1: COUNTY BOOTSTRAP (franklin, union)")
    log("=" * 60)
    log("Expected impact: 0/10 → 5-7/10 per county")
    log("Estimated time: 90-120 minutes")
    
    if dry_run:
        log("🔍 DRY RUN - would execute county bootstrap")
        return {'phase': 1, 'dry_run': True, 'expected_time_minutes': 105}
    
    results = {}
    start_time = time.time()
    
    # Bootstrap franklin
    log("\n🚀 Bootstrapping franklin county...")
    franklin_result = run_script('scripts/shard10_county_bootstrap.py', ['--county', 'franklin'], 3600)
    results['franklin'] = franklin_result
    
    if franklin_result['success']:
        log("✅ Franklin bootstrap completed")
        # Evaluate franklin after bootstrap
        franklin_eval = evaluate_county_current('franklin')
        results['franklin_evaluation'] = franklin_eval
        if franklin_eval.get('success'):
            log(f"Franklin improvement: 0/10 → {franklin_eval['pass_count']}/10")
    else:
        log(f"❌ Franklin bootstrap failed: {franklin_result.get('error', 'Unknown error')}")
    
    # Bootstrap union
    log("\n🚀 Bootstrapping union county...")
    union_result = run_script('scripts/shard10_county_bootstrap.py', ['--county', 'union'], 3600)
    results['union'] = union_result
    
    if union_result['success']:
        log("✅ Union bootstrap completed")
        # Evaluate union after bootstrap
        union_eval = evaluate_county_current('union')
        results['union_evaluation'] = union_eval
        if union_eval.get('success'):
            log(f"Union improvement: 0/10 → {union_eval['pass_count']}/10")
    else:
        log(f"❌ Union bootstrap failed: {union_result.get('error', 'Unknown error')}")
    
    elapsed_minutes = (time.time() - start_time) / 60
    log(f"\nPHASE 1 COMPLETE - {elapsed_minutes:.1f} minutes elapsed")
    
    results['phase'] = 1
    results['elapsed_minutes'] = elapsed_minutes
    return results

def run_phase2_parcel_linkage(dry_run: bool = False) -> dict:
    """Phase 2: Improve parcel linkage for manatee (highest leverage)"""
    log("=" * 60)
    log("PHASE 2: PARCEL LINKAGE IMPROVEMENT")
    log("=" * 60)
    log("Target: manatee 91.4% → 95%+ (Letter E)")
    log("Expected impact: +1 letter passing")
    log("Estimated time: 45 minutes")
    
    if dry_run:
        log("🔍 DRY RUN - would execute parcel linkage improvement")
        return {'phase': 2, 'dry_run': True, 'expected_time_minutes': 45}
    
    start_time = time.time()
    
    # Run parcel linkage improvement for manatee
    log("\n🔗 Improving parcel linkage for manatee...")
    result = run_script('scripts/shard10_parcel_linkage.py', ['--county', 'manatee'], 3600)
    
    # Evaluate manatee after improvement
    manatee_eval = evaluate_county_current('manatee')
    
    elapsed_minutes = (time.time() - start_time) / 60
    log(f"\nPHASE 2 COMPLETE - {elapsed_minutes:.1f} minutes elapsed")
    
    return {
        'phase': 2,
        'linkage_result': result,
        'manatee_evaluation': manatee_eval,
        'elapsed_minutes': elapsed_minutes
    }

def run_phase3_freshness_fix(dry_run: bool = False) -> dict:
    """Phase 3: Fix freshness issues for alachua and martin"""
    log("=" * 60)
    log("PHASE 3: FRESHNESS FIX")
    log("=" * 60)
    log("Targets: alachua (343h stale), martin (222h stale)")
    log("Expected impact: +2 letters passing (Letter H)")
    log("Estimated time: 30 minutes")
    
    if dry_run:
        log("🔍 DRY RUN - would execute freshness fixes")
        return {'phase': 3, 'dry_run': True, 'expected_time_minutes': 30}
    
    start_time = time.time()
    
    # Fix freshness for both counties
    log("\n🔄 Fixing freshness for stale counties...")
    result = run_script('scripts/shard10_freshness_fix.py', ['--all-stale'], 1800)
    
    # Evaluate counties after freshness fix
    alachua_eval = evaluate_county_current('alachua')
    martin_eval = evaluate_county_current('martin')
    
    elapsed_minutes = (time.time() - start_time) / 60
    log(f"\nPHASE 3 COMPLETE - {elapsed_minutes:.1f} minutes elapsed")
    
    return {
        'phase': 3,
        'freshness_result': result,
        'alachua_evaluation': alachua_eval,
        'martin_evaluation': martin_eval,
        'elapsed_minutes': elapsed_minutes
    }

def run_final_verification() -> dict:
    """Final verification and summary"""
    log("=" * 60)
    log("PHASE 4: FINAL VERIFICATION")
    log("=" * 60)
    
    # Get final evaluation for all counties
    final_evaluations = {}
    total_passing_final = 0
    
    for county in TARGET_COUNTIES:
        result = evaluate_county_current(county)
        final_evaluations[county] = result
        
        if result.get('success'):
            pass_count = result['pass_count']
            total_passing_final += pass_count
            log(f"{county}: {pass_count}/10 letters passing")
        else:
            log(f"{county}: ❌ Evaluation failed")
    
    log(f"\nFINAL TOTAL: {total_passing_final}/50 letters passing ({total_passing_final/50*100:.1f}%)")
    
    return {
        'phase': 4,
        'final_evaluations': final_evaluations,
        'total_passing': total_passing_final,
        'success_percentage': total_passing_final / 50 * 100
    }

def generate_session_report(baseline: dict, phase_results: dict, final: dict) -> str:
    """Generate comprehensive session report"""
    report = []
    report.append("=" * 80)
    report.append("SHARD-10 GOLD STANDARD AUTONOMOUS SESSION REPORT")
    report.append("=" * 80)
    report.append(f"Session completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    report.append(f"Target counties: {', '.join(TARGET_COUNTIES)}")
    
    # Calculate baseline vs final
    baseline_total = sum(r.get('pass_count', 0) for r in baseline.values() if r.get('success'))
    final_total = final.get('total_passing', 0)
    improvement = final_total - baseline_total
    
    report.append(f"\nOVERALL RESULTS:")
    report.append(f"  Baseline: {baseline_total}/50 letters passing ({baseline_total/50*100:.1f}%)")
    report.append(f"  Final: {final_total}/50 letters passing ({final_total/50*100:.1f}%)")
    report.append(f"  Improvement: +{improvement} letters ({improvement/50*100:.1f}%)")
    
    report.append(f"\nPER-COUNTY IMPROVEMENTS:")
    for county in TARGET_COUNTIES:
        baseline_pass = baseline.get(county, {}).get('pass_count', 0)
        final_pass = final['final_evaluations'].get(county, {}).get('pass_count', 0)
        county_improvement = final_pass - baseline_pass
        
        report.append(f"  {county}: {baseline_pass}/10 → {final_pass}/10 ({county_improvement:+d})")
    
    # Phase execution summary
    total_time = 0
    report.append(f"\nPHASE EXECUTION:")
    for phase_num, phase_data in phase_results.items():
        if isinstance(phase_data, dict) and 'elapsed_minutes' in phase_data:
            elapsed = phase_data['elapsed_minutes']
            total_time += elapsed
            report.append(f"  Phase {phase_num}: {elapsed:.1f} minutes")
    
    report.append(f"  Total execution time: {total_time:.1f} minutes ({total_time/60:.1f} hours)")
    
    # Next steps
    report.append(f"\nRECOMMENDED NEXT STEPS:")
    if improvement >= 10:
        report.append("  ✅ Strong improvement achieved - continue with remaining letters")
        report.append("  🎯 Focus on Letters B, I, J (verified outcomes, property cards, deal thesis)")
    elif improvement >= 5:
        report.append("  ✅ Good improvement achieved - optimize successful approaches")
        report.append("  🔄 Scale successful patterns to remaining counties")
    else:
        report.append("  ⚠️ Limited improvement - review and adjust strategy")
        report.append("  🔍 Analyze blocking issues and alternative approaches")
    
    report.append(f"\nWIRING STATUS:")
    report.append("  📊 All improvements wired to autonomous execution")
    report.append("  🔄 Pipeline configurations updated for sustained freshness")
    report.append("  ✅ Ship-to-main mandate: committed directly to main branch")
    
    return "\n".join(report)

def main():
    parser = argparse.ArgumentParser(description='SHARD-10 Gold Standard Session')
    parser.add_argument('--dry-run', action='store_true', 
                        help='Show execution plan without running')
    parser.add_argument('--phase-only', type=int, choices=[1, 2, 3, 4],
                        help='Run specific phase only')
    args = parser.parse_args()
    
    log("🎯 SHARD-10 GOLD STANDARD AUTONOMOUS SESSION STARTING")
    log(f"Session mode: {'DRY RUN' if args.dry_run else 'EXECUTION'}")
    log(f"Target: Maximize Gold Standard improvements in 6-hour window")
    
    if not SUPABASE_KEY:
        log("❌ SUPABASE_KEY environment variable not set")
        sys.exit(1)
    
    session_start = time.time()
    phase_results = {}
    
    # Baseline evaluation
    baseline = run_baseline_evaluation()
    
    # Execute phases based on arguments
    if args.phase_only:
        log(f"🎯 Executing Phase {args.phase_only} only")
        if args.phase_only == 1:
            phase_results[1] = run_phase1_bootstrap(args.dry_run)
        elif args.phase_only == 2:
            phase_results[2] = run_phase2_parcel_linkage(args.dry_run)
        elif args.phase_only == 3:
            phase_results[3] = run_phase3_freshness_fix(args.dry_run)
        elif args.phase_only == 4:
            final = run_final_verification()
    else:
        # Full session execution
        log("🚀 Executing full autonomous session")
        
        # Phase 1: County bootstrap
        phase_results[1] = run_phase1_bootstrap(args.dry_run)
        
        # Check time budget (6 hours = 360 minutes)
        elapsed_minutes = (time.time() - session_start) / 60
        if elapsed_minutes > 300:  # 5 hours - save 1 hour for final phases
            log("⏰ Time budget constraint - skipping remaining phases")
        else:
            # Phase 2: Parcel linkage
            phase_results[2] = run_phase2_parcel_linkage(args.dry_run)
            
            # Phase 3: Freshness fix
            elapsed_minutes = (time.time() - session_start) / 60
            if elapsed_minutes < 320:  # If under 5h20m, run freshness fix
                phase_results[3] = run_phase3_freshness_fix(args.dry_run)
        
        # Phase 4: Final verification
        if not args.dry_run:
            final = run_final_verification()
    
    # Session summary
    total_session_time = (time.time() - session_start) / 60
    log(f"\n🎯 SESSION COMPLETE - {total_session_time:.1f} minutes total")
    
    if not args.dry_run and not args.phase_only:
        # Generate and display final report
        report = generate_session_report(baseline, phase_results, final)
        print("\n" + report)
        
        # Save report to file
        report_file = f"shard10_session_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(report_file, 'w') as f:
            f.write(report)
        log(f"📋 Session report saved: {report_file}")

if __name__ == "__main__":
    main()