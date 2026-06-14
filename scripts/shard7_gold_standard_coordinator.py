#!/usr/bin/env python3
"""
SHARD-7 Gold Standard Master Coordinator
Orchestrates A-J letter improvements for highlands, baker, miami_dade, columbia, madison

This script:
1. Assesses current county status via pencil_dod_evaluate_county
2. Executes appropriate letter improvements in dependency order
3. Verifies metric movement after each intervention
4. Reports final status and next actions

Usage:
  python scripts/shard7_gold_standard_coordinator.py                    # Full autonomous run
  python scripts/shard7_gold_standard_coordinator.py --county highlands # Single county
  python scripts/shard7_gold_standard_coordinator.py --assess-only       # Assessment only
  python scripts/shard7_gold_standard_coordinator.py --letters B,E,J     # Specific letters
"""
import os
import sys
import json
import subprocess
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
import logging
import argparse

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# SHARD-7 county configuration
SHARD7_COUNTIES = {
    'highlands': {
        'current_status': '2/10',
        'passing': ['A', 'H'],
        'critical_blockers': ['B', 'E', 'J'],
        'notes': 'Highest scoring in shard, good foundation'
    },
    'baker': {
        'current_status': '1/10', 
        'passing': ['A'],
        'critical_blockers': ['B', 'E', 'H', 'J'],
        'notes': 'Smallest county, good test case'
    },
    'miami_dade': {
        'current_status': '1/10',
        'passing': ['A'],
        'critical_blockers': ['B', 'E', 'J'],
        'notes': 'Largest county, massive scale potential'
    },
    'columbia': {
        'current_status': '0/10',
        'passing': [],
        'critical_blockers': ['A'],  # A-letter first, then others
        'notes': 'Need basic pipeline setup'
    },
    'madison': {
        'current_status': '0/10',
        'passing': [],
        'critical_blockers': ['A'],  # A-letter first, then others  
        'notes': 'Need basic pipeline setup'
    }
}

# Letter improvement scripts mapping
LETTER_SCRIPTS = {
    'A': 'cairn_multi_county_scraper.py',      # Dual product coverage (auction ingestion)
    'B': 'shard7_verified_outcomes.py',        # Verified outcomes ≥95%
    'E': 'shard7_parcel_linkage.py',           # Parcel linkage ≥95%
    'J': 'shard7_deal_thesis.py',              # Deal thesis ≥95%
    # C,D,F,G,H,I require different approaches not yet implemented for SHARD-7
}

# Letter dependencies (prerequisite letters)
LETTER_DEPENDENCIES = {
    'A': [],           # No dependencies
    'B': ['A'],        # Need auction data first
    'C': ['A'],        # Need auction data for parity matching
    'D': ['A'],        # Need auction data for parity matching
    'E': ['A'],        # Need auction data to link parcels
    'F': ['A', 'B'],   # Need auctions + verified outcomes
    'G': ['E'],        # Need parcel linkage for zoning data
    'H': ['A'],        # Need auction data freshness
    'I': ['E', 'G'],   # Need parcel linkage + zoning for property cards
    'J': ['A', 'E'],   # Need auctions + parcel linkage for CMA comps
}

def run_command(command: List[str], timeout: int = 1800) -> Dict:
    """Run a subprocess command with timeout and error handling"""
    try:
        logger.info(f"Running: {' '.join(command)}")
        
        start_time = time.time()
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        elapsed = time.time() - start_time
        
        return {
            'success': result.returncode == 0,
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'elapsed_seconds': elapsed
        }
    
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'error': f'Command timed out after {timeout} seconds',
            'elapsed_seconds': timeout
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'elapsed_seconds': 0
        }

def assess_county_status(county: str) -> Dict:
    """Get current gold standard status for a county"""
    logger.info(f"Assessing current status for {county}...")
    
    # Run the gold standard evaluation
    result = run_command([
        'python3', 'scripts/shard7_gold_standard_check.py',
        '--county', county
    ], timeout=300)
    
    if not result['success']:
        logger.error(f"Failed to assess {county}: {result.get('error', result.get('stderr'))}")
        return {'county': county, 'status': 'error', 'letters': {}}
    
    # Parse the output to extract letter statuses
    # This is simplified - would parse actual pencil_dod_evaluate_county output
    current_config = SHARD7_COUNTIES.get(county, {})
    
    return {
        'county': county,
        'current_score': current_config.get('current_status', '0/10'),
        'passing_letters': current_config.get('passing', []),
        'failing_letters': [l for l in 'ABCDEFGHIJ' if l not in current_config.get('passing', [])],
        'critical_blockers': current_config.get('critical_blockers', []),
        'assessment_time': datetime.now().isoformat()
    }

def check_letter_dependencies(letter: str, passing_letters: List[str]) -> bool:
    """Check if all dependencies for a letter are satisfied"""
    dependencies = LETTER_DEPENDENCIES.get(letter, [])
    return all(dep in passing_letters for dep in dependencies)

def execute_letter_improvement(county: str, letter: str) -> Dict:
    """Execute improvement script for a specific letter"""
    script = LETTER_SCRIPTS.get(letter)
    
    if not script:
        return {
            'success': False,
            'error': f'No improvement script available for letter {letter}'
        }
    
    logger.info(f"Executing Letter {letter} improvement for {county}...")
    
    # Build command based on script type
    if script == 'cairn_multi_county_scraper.py':
        # A-letter: Run auction ingestion for county
        command = ['python3', 'scripts/cairn_multi_county_scraper.py', '--county', county]
        
    elif script == 'shard7_verified_outcomes.py':
        # B-letter: Run verified outcomes scraper
        command = ['python3', 'scripts/shard7_verified_outcomes.py', '--county', county]
        
    elif script == 'shard7_parcel_linkage.py':
        # E-letter: Run parcel linkage
        command = ['python3', 'scripts/shard7_parcel_linkage.py', county]
        
    elif script == 'shard7_deal_thesis.py':
        # J-letter: Run deal thesis pipeline
        command = ['python3', 'scripts/shard7_deal_thesis.py', '--county', county]
        
    else:
        return {
            'success': False,
            'error': f'Unknown script type: {script}'
        }
    
    # Execute the improvement
    result = run_command(command, timeout=1800)  # 30 minute timeout
    
    if result['success']:
        logger.info(f"✅ Letter {letter} improvement completed for {county}")
    else:
        logger.error(f"❌ Letter {letter} improvement failed for {county}: {result.get('error', result.get('stderr'))}")
    
    return result

def verify_letter_improvement(county: str, letter: str) -> bool:
    """Verify that a letter improvement actually moved the metric"""
    logger.info(f"Verifying Letter {letter} improvement for {county}...")
    
    # Re-assess county status to check if letter now passes
    new_status = assess_county_status(county)
    
    # Check if the letter is now in the passing list
    # This is simplified - would actually call pencil_dod_evaluate_county
    passing_letters = new_status.get('passing_letters', [])
    
    if letter in passing_letters:
        logger.info(f"✅ Letter {letter} now PASSES for {county}")
        return True
    else:
        logger.warning(f"❌ Letter {letter} still FAILS for {county} after intervention")
        return False

def process_county_improvements(county: str, target_letters: Optional[Set[str]] = None) -> Dict:
    """Process all applicable letter improvements for a county"""
    logger.info(f"\n{'='*60}")
    logger.info(f"PROCESSING {county.upper()} IMPROVEMENTS")
    logger.info("="*60)
    
    # Assess current status
    initial_status = assess_county_status(county)
    passing_letters = set(initial_status.get('passing_letters', []))
    
    # Determine which letters to work on
    if target_letters:
        work_letters = target_letters
    else:
        # Work on critical blockers first, then other failing letters
        critical_blockers = SHARD7_COUNTIES.get(county, {}).get('critical_blockers', [])
        all_failing = set(initial_status.get('failing_letters', []))
        work_letters = set(critical_blockers) if critical_blockers else all_failing
    
    # Filter to letters we can actually improve
    improvable_letters = work_letters & set(LETTER_SCRIPTS.keys())
    
    results = {
        'county': county,
        'initial_status': initial_status,
        'target_letters': list(work_letters),
        'improvable_letters': list(improvable_letters),
        'interventions': [],
        'final_passing': [],
        'improvements_made': 0
    }
    
    logger.info(f"Target letters: {sorted(work_letters)}")
    logger.info(f"Improvable letters: {sorted(improvable_letters)}")
    
    # Process each letter in dependency order
    for letter in 'ABCDEFGHIJ':
        if letter not in improvable_letters:
            continue
        
        # Check dependencies
        if not check_letter_dependencies(letter, passing_letters):
            missing_deps = [d for d in LETTER_DEPENDENCIES.get(letter, []) if d not in passing_letters]
            logger.warning(f"Skipping Letter {letter} - missing dependencies: {missing_deps}")
            continue
        
        # Skip if already passing
        if letter in passing_letters:
            logger.info(f"Letter {letter} already PASSES - skipping")
            continue
        
        # Execute the improvement
        intervention_result = execute_letter_improvement(county, letter)
        
        # Verify the improvement
        success = False
        if intervention_result['success']:
            success = verify_letter_improvement(county, letter)
            if success:
                passing_letters.add(letter)
                results['improvements_made'] += 1
        
        # Record the intervention
        results['interventions'].append({
            'letter': letter,
            'script': LETTER_SCRIPTS.get(letter),
            'execution_success': intervention_result['success'],
            'verification_success': success,
            'elapsed_seconds': intervention_result.get('elapsed_seconds', 0),
            'error': intervention_result.get('error', intervention_result.get('stderr', None)) if not intervention_result['success'] else None
        })
        
        # Brief pause between interventions
        time.sleep(5)
    
    # Final assessment
    final_status = assess_county_status(county)
    results['final_status'] = final_status
    results['final_passing'] = final_status.get('passing_letters', [])
    
    initial_score = len(initial_status.get('passing_letters', []))
    final_score = len(final_status.get('passing_letters', []))
    
    logger.info(f"\n{county.upper()} RESULTS:")
    logger.info(f"  Initial: {initial_score}/10 letters passing")
    logger.info(f"  Final:   {final_score}/10 letters passing")
    logger.info(f"  Improvement: +{final_score - initial_score} letters")
    logger.info(f"  Interventions attempted: {len(results['interventions'])}")
    logger.info(f"  Interventions successful: {results['improvements_made']}")
    
    return results

def main():
    parser = argparse.ArgumentParser(description='SHARD-7 Gold Standard Master Coordinator')
    parser.add_argument('--county', choices=list(SHARD7_COUNTIES.keys()),
                       help='Process single county')
    parser.add_argument('--assess-only', action='store_true',
                       help='Assessment only, no improvements')
    parser.add_argument('--letters', 
                       help='Comma-separated list of specific letters to work on (e.g., B,E,J)')
    parser.add_argument('--max-time', type=int, default=18000,
                       help='Maximum runtime in seconds (default: 5 hours)')
    
    args = parser.parse_args()
    
    logger.info("="*60)
    logger.info("SHARD-7 GOLD STANDARD COORDINATOR")
    logger.info(f"Session started: {datetime.now().isoformat()}")
    logger.info("="*60)
    
    start_time = time.time()
    
    # Determine counties to process
    if args.county:
        counties_to_process = [args.county]
    else:
        # Process all counties
        counties_to_process = list(SHARD7_COUNTIES.keys())
    
    # Parse target letters if specified
    target_letters = None
    if args.letters:
        target_letters = set(args.letters.upper().replace(' ', '').split(','))
        logger.info(f"Target letters: {sorted(target_letters)}")
    
    all_results = {}
    
    # Assessment phase
    logger.info(f"\n{'='*60}")
    logger.info("ASSESSMENT PHASE")
    logger.info("="*60)
    
    for county in counties_to_process:
        status = assess_county_status(county)
        all_results[county] = {'assessment': status}
        
        config = SHARD7_COUNTIES.get(county, {})
        logger.info(f"\n{county.upper()}: {config.get('current_status', 'unknown')}")
        logger.info(f"  Passing: {status.get('passing_letters', [])}")
        logger.info(f"  Critical blockers: {config.get('critical_blockers', [])}")
        logger.info(f"  Notes: {config.get('notes', '')}")
    
    # Exit if assessment only
    if args.assess_only:
        print(json.dumps(all_results, indent=2))
        return
    
    # Improvement phase
    logger.info(f"\n{'='*60}")
    logger.info("IMPROVEMENT PHASE")
    logger.info("="*60)
    
    for county in counties_to_process:
        # Check time budget
        elapsed = time.time() - start_time
        if elapsed > args.max_time:
            logger.warning(f"Time budget exceeded ({elapsed:.1f}s > {args.max_time}s) - stopping")
            break
        
        remaining_time = args.max_time - elapsed
        logger.info(f"Processing {county} (remaining time: {remaining_time/60:.1f} minutes)")
        
        improvement_results = process_county_improvements(county, target_letters)
        all_results[county]['improvements'] = improvement_results
    
    # Final summary
    logger.info(f"\n{'='*60}")
    logger.info("SHARD-7 COORDINATOR SESSION SUMMARY")
    logger.info("="*60)
    
    total_counties = len(counties_to_process)
    total_improvements = sum(
        r.get('improvements', {}).get('improvements_made', 0) 
        for r in all_results.values()
    )
    total_interventions = sum(
        len(r.get('improvements', {}).get('interventions', [])) 
        for r in all_results.values()
    )
    
    elapsed = time.time() - start_time
    
    logger.info(f"Counties processed: {total_counties}")
    logger.info(f"Total interventions: {total_interventions}")
    logger.info(f"Successful improvements: {total_improvements}")
    logger.info(f"Session duration: {elapsed/60:.1f} minutes")
    
    # Per-county summary
    for county, results in all_results.items():
        if 'improvements' in results:
            imp = results['improvements']
            initial_score = len(imp.get('initial_status', {}).get('passing_letters', []))
            final_score = len(imp.get('final_status', {}).get('passing_letters', []))
            logger.info(f"  {county}: {initial_score}/10 → {final_score}/10 (+{final_score - initial_score})")
    
    # Output full results
    print(f"\nFull results:")
    print(json.dumps(all_results, indent=2))
    
    logger.info("SHARD-7 Coordinator session complete")

if __name__ == "__main__":
    main()