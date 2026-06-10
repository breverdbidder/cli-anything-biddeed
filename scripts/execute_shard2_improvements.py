#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-2 MASTER EXECUTION SCRIPT
Executes all improvement scripts in optimal order for maximum Gold Standard pass rate improvement

Target: Improve pass rates for st_lucie, bay, hernando, okaloosa, calhoun, gulf, liberty
Focus: Highest leverage opportunities first - st_lucie Letter D at 93.6% → 95%

Usage:
  python scripts/execute_shard2_improvements.py --priority-county st_lucie
  python scripts/execute_shard2_improvements.py --all-counties
"""
import subprocess
import sys
import os
import time
import logging
from datetime import datetime
from typing import Dict, List

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# SHARD-2 counties in priority order
COUNTY_PRIORITY = [
    'st_lucie',    # 2/10 - highest scoring, closest to thresholds
    'hernando',    # 1/10 - 73.1% parity_any (good foundation)
    'bay',         # 1/10 - 60.0% parity_any  
    'gulf',        # 0/10 - but has some data (55.6% parity_any)
    'okaloosa',    # 1/10 - 53.6% parity_any
    'calhoun',     # 0/10 - minimal data
    'liberty'      # 0/10 - no data, needs foundation
]

# Execution phases with expected impact
EXECUTION_PHASES = [
    {
        'name': 'Phase 1: Foundation Building (Letter A)',
        'script': 'scripts/fix_letter_a_dual_product.py',
        'target_letters': ['A'],
        'expected_impact': 'liberty, calhoun, gulf get Letter A pass',
        'time_budget': '15min'
    },
    {
        'name': 'Phase 2: Parity Optimization (Letters C/D)', 
        'script': 'scripts/improve_parity_shard2.py',
        'target_letters': ['C', 'D'],
        'expected_impact': 'st_lucie Letter D: 93.6% → 95% (PASS)',
        'time_budget': '45min'
    },
    {
        'name': 'Phase 3: Verified Outcomes (Letter B)',
        'script': 'scripts/scrape_verified_outcomes_shard2.py', 
        'target_letters': ['B'],
        'expected_impact': 'All counties: 0% → sample verified outcomes',
        'time_budget': '30min'
    },
    {
        'name': 'Phase 4: Tier1 Amounts (Letter F)',
        'script': 'scripts/scrape_tier1_shard2.py',
        'target_letters': ['F'],
        'expected_impact': 'RealAuction counties get tier1 data',
        'time_budget': '60min'
    }
]

def check_prerequisites():
    """Check that required environment variables and scripts exist"""
    
    required_env = ['SUPABASE_URL', 'SUPABASE_KEY']
    missing_env = [var for var in required_env if not os.environ.get(var)]
    
    if missing_env:
        logger.error(f"Missing required environment variables: {missing_env}")
        return False
    
    # Check that all scripts exist
    for phase in EXECUTION_PHASES:
        script_path = phase['script']
        if not os.path.exists(script_path):
            logger.error(f"Missing script: {script_path}")
            return False
    
    logger.info("✅ All prerequisites met")
    return True

def run_script(script_path: str, args: List[str] = None, timeout: int = 3600) -> Dict:
    """Run a script with optional arguments and return result"""
    
    cmd = ['python', script_path]
    if args:
        cmd.extend(args)
    
    logger.info(f"Running: {' '.join(cmd)}")
    start_time = time.time()
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.getcwd()
        )
        
        duration = time.time() - start_time
        
        return {
            'success': result.returncode == 0,
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'duration': duration
        }
        
    except subprocess.TimeoutExpired:
        logger.error(f"Script {script_path} timed out after {timeout}s")
        return {
            'success': False,
            'error': 'timeout',
            'duration': timeout
        }
    except Exception as e:
        logger.error(f"Error running {script_path}: {e}")
        return {
            'success': False,
            'error': str(e),
            'duration': time.time() - start_time
        }

def execute_phase(phase: Dict, counties: List[str]) -> Dict:
    """Execute a single improvement phase"""
    
    logger.info(f"\n{'='*60}")
    logger.info(f"STARTING {phase['name']}")
    logger.info(f"Target Letters: {', '.join(phase['target_letters'])}")
    logger.info(f"Expected Impact: {phase['expected_impact']}")
    logger.info(f"Time Budget: {phase['time_budget']}")
    logger.info(f"{'='*60}")
    
    results = {}
    phase_start = time.time()
    
    for county in counties:
        logger.info(f"\n--- Executing {phase['name']} for {county} ---")
        
        # Run script for this county
        result = run_script(phase['script'], ['--county', county])
        results[county] = result
        
        if result['success']:
            logger.info(f"✅ {county} completed successfully ({result['duration']:.1f}s)")
            if result.get('stdout'):
                # Log key output lines
                stdout_lines = result['stdout'].split('\n')
                key_lines = [line for line in stdout_lines if any(keyword in line.lower() 
                    for keyword in ['improvement', 'updated', 'success', 'pass', 'fail', 'error'])]
                for line in key_lines[-5:]:  # Last 5 relevant lines
                    logger.info(f"  {line.strip()}")
        else:
            logger.error(f"❌ {county} failed (exit {result['returncode']})")
            if result.get('stderr'):
                logger.error(f"  Error: {result['stderr'][:200]}")
    
    phase_duration = time.time() - phase_start
    success_count = sum(1 for r in results.values() if r['success'])
    
    logger.info(f"\n{phase['name']} COMPLETE:")
    logger.info(f"  Success: {success_count}/{len(counties)} counties")
    logger.info(f"  Duration: {phase_duration:.1f}s")
    
    return {
        'phase': phase['name'],
        'results': results,
        'success_count': success_count,
        'total_counties': len(counties),
        'duration': phase_duration
    }

def verify_improvements():
    """Run verification to check actual improvement in Gold Standard metrics"""
    
    logger.info("\n" + "="*60)
    logger.info("VERIFICATION PHASE - Checking Gold Standard Metrics")
    logger.info("="*60)
    
    # This would call the pencil_dod_evaluate_county function for each county
    # For now, just log that verification should be run
    
    logger.info("Verification commands to run:")
    for county in COUNTY_PRIORITY:
        logger.info(f"  SELECT public.pencil_dod_evaluate_county('{county}');")
    
    logger.info("\nFinal verification:")
    logger.info("  SELECT * FROM gold_standard_scoreboard WHERE county_slug IN ('st_lucie', 'bay', 'hernando', 'okaloosa', 'calhoun', 'gulf', 'liberty');")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Execute SHARD-2 Gold Standard improvements')
    parser.add_argument('--priority-county', choices=COUNTY_PRIORITY, help='Run for single priority county')
    parser.add_argument('--all-counties', action='store_true', help='Run for all SHARD-2 counties')
    parser.add_argument('--phases', nargs='+', type=int, choices=[1,2,3,4], help='Run specific phases (1-4)')
    parser.add_argument('--dry-run', action='store_true', help='Show execution plan without running')
    
    args = parser.parse_args()
    
    logger.info("GOLD STANDARD SHARD-2 MASTER EXECUTION")
    logger.info(f"Session start: {datetime.now().isoformat()}")
    
    if not check_prerequisites():
        sys.exit(1)
    
    # Determine counties to process
    if args.priority_county:
        counties = [args.priority_county]
    elif args.all_counties:
        counties = COUNTY_PRIORITY
    else:
        # Default to st_lucie as highest priority
        counties = ['st_lucie']
        logger.info("No counties specified, defaulting to st_lucie (highest leverage)")
    
    # Determine phases to run
    phases_to_run = EXECUTION_PHASES
    if args.phases:
        phases_to_run = [EXECUTION_PHASES[i-1] for i in args.phases]
    
    logger.info(f"\nExecution Plan:")
    logger.info(f"  Counties: {', '.join(counties)}")
    logger.info(f"  Phases: {len(phases_to_run)} phases")
    for i, phase in enumerate(phases_to_run, 1):
        logger.info(f"    {i}. {phase['name']} - {phase['expected_impact']}")
    
    if args.dry_run:
        logger.info("\n🔍 DRY RUN - No scripts executed")
        return
    
    # Execute phases
    session_start = time.time()
    phase_results = []
    
    for phase in phases_to_run:
        phase_result = execute_phase(phase, counties)
        phase_results.append(phase_result)
        
        # Stop if phase had too many failures
        if phase_result['success_count'] == 0:
            logger.error(f"Phase failed completely, stopping execution")
            break
    
    session_duration = time.time() - session_start
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("EXECUTION SUMMARY")
    logger.info("="*60)
    
    total_successes = sum(r['success_count'] for r in phase_results)
    total_attempts = sum(r['total_counties'] for r in phase_results)
    
    logger.info(f"Session Duration: {session_duration:.1f}s ({session_duration/60:.1f}min)")
    logger.info(f"Overall Success Rate: {total_successes}/{total_attempts} ({100*total_successes/total_attempts:.1f}%)")
    
    for result in phase_results:
        logger.info(f"  {result['phase']}: {result['success_count']}/{result['total_counties']} counties ({result['duration']:.1f}s)")
    
    # Run verification
    verify_improvements()
    
    logger.info(f"\n🎯 SHARD-2 improvements complete. Check Gold Standard scoreboard for metrics.")

if __name__ == "__main__":
    main()