#!/usr/bin/env python3
"""
GOLD STANDARD AUTOPILOT SESSION EXECUTOR
Orchestrates execution of all priority scripts for brevard and duval counties

Usage:
  python3 run_autopilot_session.py
"""
import os
import subprocess
import json
from datetime import datetime, timezone

def log(message, level="INFO"):
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"[{timestamp}] {level}: {message}")

def run_script(script_path, args=None, timeout=300):
    """Run a script and capture results"""
    try:
        cmd = ["python3", script_path]
        if args:
            cmd.extend(args)
        
        log(f"Executing: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd="/home/runner/work/cli-anything-biddeed/cli-anything-biddeed"
        )
        
        return {
            'script': script_path,
            'args': args,
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'success': result.returncode == 0,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
    except subprocess.TimeoutExpired:
        return {
            'script': script_path,
            'args': args,
            'error': 'TIMEOUT',
            'success': False,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return {
            'script': script_path,
            'args': args,
            'error': str(e),
            'success': False,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

def main():
    """Execute GOLD STANDARD AUTOPILOT session"""
    
    session_start = datetime.now(timezone.utc)
    log("🚀 GOLD STANDARD AUTOPILOT SESSION - Starting")
    
    results = {
        'session_id': f"autopilot-{session_start.strftime('%Y%m%d-%H%M%S')}",
        'session_start': session_start.isoformat(),
        'counties': ['brevard', 'duval'],
        'script_executions': [],
        'verification_results': {},
        'errors': []
    }
    
    # Phase 1: Database connectivity test
    log("Phase 1: Database connectivity verification")
    db_test = run_script("test_db_connection.py")
    results['script_executions'].append(db_test)
    
    if not db_test['success']:
        log("Database connectivity failed - aborting session", "ERROR")
        results['errors'].append("Database connectivity failed")
        return results
    
    # Phase 2: Brevard C/D root cause analysis
    log("Phase 2: Brevard C/D root cause analysis")
    brevard_cd = run_script("scripts/brevard_duval_cd_parity_fix.py")
    results['script_executions'].append(brevard_cd)
    
    # Phase 3: J generator for both counties
    log("Phase 3: J generator (bid decisions pipeline)")
    
    # Run for brevard
    j_brevard = run_script("scripts/j_generator_bid_decisions.py", ["--county", "brevard", "--limit", "25"])
    results['script_executions'].append(j_brevard)
    
    # Run for duval
    j_duval = run_script("scripts/j_generator_bid_decisions.py", ["--county", "duval", "--limit", "25"])
    results['script_executions'].append(j_duval)
    
    # Phase 4: Duval G+I substrate build
    log("Phase 4: Duval G+I substrate build")
    duval_gi = run_script("scripts/duval_gi_substrate_build.py")
    results['script_executions'].append(duval_gi)
    
    # Calculate session summary
    session_end = datetime.now(timezone.utc)
    duration = (session_end - session_start).total_seconds() / 60  # minutes
    
    successful_executions = sum(1 for exec in results['script_executions'] if exec['success'])
    total_executions = len(results['script_executions'])
    
    results['summary'] = {
        'session_end': session_end.isoformat(),
        'duration_minutes': round(duration, 2),
        'total_script_executions': total_executions,
        'successful_executions': successful_executions,
        'success_rate': successful_executions / total_executions if total_executions > 0 else 0,
        'counties_processed': ['brevard', 'duval'],
        'priorities_addressed': [
            'brevard_cd_root_cause',
            'brevard_j_generator', 
            'duval_gi_substrate',
            'duval_j_generator'
        ]
    }
    
    # Save results
    results_path = f"/tmp/autopilot_session_{session_start.strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    # Print summary
    print("\n" + "="*80)
    print("GOLD STANDARD AUTOPILOT SESSION RESULTS")
    print("="*80)
    
    for i, execution in enumerate(results['script_executions'], 1):
        status = "✅ SUCCESS" if execution['success'] else "❌ FAILED"
        script_name = execution['script'].replace('scripts/', '')
        args_str = ' '.join(execution.get('args', [])) if execution.get('args') else ''
        print(f"{i}. {script_name} {args_str}: {status}")
        
        if not execution['success'] and execution.get('stderr'):
            print(f"   Error: {execution['stderr'][:200]}...")
    
    print(f"\nSession Duration: {duration:.1f} minutes")
    print(f"Success Rate: {successful_executions}/{total_executions} ({results['summary']['success_rate']:.1%})")
    
    # HONESTY PROTOCOL verification markers
    print(f"\nVERIFICATION STATUS:")
    print(f"- Database connectivity: {'VERIFIED' if db_test['success'] else 'FAILED'}")
    print(f"- C/D parity analysis: {'VERIFIED' if brevard_cd['success'] else 'FAILED'}")
    print(f"- J generator brevard: {'VERIFIED' if j_brevard['success'] else 'FAILED'}")
    print(f"- J generator duval: {'VERIFIED' if j_duval['success'] else 'FAILED'}")
    print(f"- G+I substrate: {'VERIFIED' if duval_gi['success'] else 'FAILED'}")
    
    log(f"✅ AUTOPILOT SESSION COMPLETE - Results saved to {results_path}")
    return results

if __name__ == "__main__":
    main()