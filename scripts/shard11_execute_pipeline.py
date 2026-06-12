#!/usr/bin/env python3
"""
SHARD-11 Gold Standard Pipeline Executor
Orchestrates complete Letter A-J improvements for manatee, bay, okeechobee, gadsden, wakulla

Executes in optimal order:
1. Bootstrap (A - data ingestion)
2. Staleness fix (H - freshness) 
3. Parcel linkage (E - high leverage)
4. Verified outcomes (B - critical)
5. Parity matching (C/D - dependent on E)
6. Property cards (I - depends on E)
7. Deal thesis (J - depends on I+B)

Usage:
  python scripts/shard11_execute_pipeline.py --full
  python scripts/shard11_execute_pipeline.py --county manatee --letters BEH
  python scripts/shard11_execute_pipeline.py --verify-only
"""
import os
import sys
import json
import httpx
import time
import argparse
import subprocess
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
import logging

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
    "Content-Type": "application/json"
}

# SHARD-11 counties
TARGET_COUNTIES = ['manatee', 'bay', 'okeechobee', 'gadsden', 'wakulla']

# Letter execution order (dependencies considered)
EXECUTION_ORDER = ['A', 'H', 'E', 'B', 'C', 'D', 'I', 'J', 'F', 'G']

# Letter script mapping
LETTER_SCRIPTS = {
    'A': 'shard11_county_bootstrap.py',  # Data ingestion
    'B': 'shard11_verified_outcomes.py', # Independent verified outcomes
    'C': None,  # Parity matching (TODO)
    'D': None,  # Parity matching (TODO) 
    'E': 'shard11_parcel_linkage.py',   # Parcel linking via GIS
    'F': None,  # Tier1 sold amount (TODO)
    'G': None,  # Zoning KPI (TODO)
    'H': 'shard11_fix_staleness.py',    # Freshness fix
    'I': None,  # Property cards (TODO) 
    'J': None   # Deal thesis (TODO)
}

class SHARD11PipelineExecutor:
    """Executes SHARD-11 Gold Standard pipeline"""
    
    def __init__(self):
        self.client = httpx.Client(timeout=60)
        self.execution_results = {}
        
    def query_supabase(self, table: str, params: Dict = None) -> List[Dict]:
        """Query Supabase table"""
        try:
            url = f"{BASE}/{table}"
            response = self.client.get(url, headers=HEADERS, params=params)
            return response.json() if response.status_code == 200 else []
        except Exception as e:
            logger.error(f"Query error {table}: {e}")
            return []
    
    def get_county_evaluation(self, county: str) -> Optional[Dict]:
        """Get current evaluation for county"""
        try:
            response = self.client.post(
                f"{BASE}/rpc/pencil_dod_evaluate_county",
                headers=HEADERS,
                json={'county_name': county},
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Evaluation failed for {county}: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Evaluation error for {county}: {e}")
            return None
    
    def get_failing_letters(self, county: str) -> Set[str]:
        """Get failing letters for a county"""
        evaluation = self.get_county_evaluation(county)
        if not evaluation:
            return set(EXECUTION_ORDER)  # Assume all failing if no data
        
        failing = set()
        for letter in EXECUTION_ORDER:
            grade_field = f"grade_{letter.lower()}"
            if evaluation.get(grade_field) != 'PASS':
                failing.add(letter)
        
        return failing
    
    def run_script(self, script_name: str, args: List[str] = None, timeout: int = 3600) -> Dict:
        """Run a pipeline script"""
        if not script_name:
            return {'success': False, 'error': 'No script defined'}
        
        cmd = ['python3', f'scripts/{script_name}']
        if args:
            cmd.extend(args)
        
        logger.info(f"Executing: {' '.join(cmd)}")
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd='/home/runner/work/cli-anything-biddeed/cli-anything-biddeed'
            )
            
            elapsed = time.time() - start_time
            
            return {
                'script': script_name,
                'args': args,
                'success': result.returncode == 0,
                'elapsed_seconds': elapsed,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode
            }
            
        except subprocess.TimeoutExpired:
            return {
                'script': script_name,
                'success': False,
                'elapsed_seconds': timeout,
                'error': 'Script timed out',
                'returncode': -1
            }
        except Exception as e:
            return {
                'script': script_name,
                'success': False,
                'elapsed_seconds': 0,
                'error': str(e),
                'returncode': -1
            }
    
    def execute_letter(self, letter: str, county: str = None) -> Dict:
        """Execute pipeline for a specific letter"""
        script_name = LETTER_SCRIPTS.get(letter)
        
        if not script_name:
            logger.warning(f"Letter {letter} not implemented yet")
            return {'letter': letter, 'success': False, 'error': 'Not implemented'}
        
        # Build arguments based on script
        args = []
        if county:
            args.extend(['--county', county])
        elif script_name == 'shard11_verified_outcomes.py':
            args.append('--all-counties')
        elif script_name == 'shard11_fix_staleness.py':
            args.append('--all-stale')
        elif script_name == 'shard11_parcel_linkage.py':
            args.append('--all-counties')
        
        logger.info(f"📋 Executing Letter {letter}: {script_name}")
        result = self.run_script(script_name, args)
        
        result['letter'] = letter
        return result
    
    def execute_pipeline(self, counties: List[str], letters: Set[str] = None) -> Dict:
        """Execute full pipeline for counties"""
        logger.info(f"🚀 Starting SHARD-11 pipeline execution")
        logger.info(f"Counties: {counties}")
        logger.info(f"Letters: {letters or 'All failing'}")
        
        start_time = datetime.now()
        results = {
            'start_time': start_time.isoformat(),
            'counties': counties,
            'county_results': {},
            'letter_results': {},
            'summary': {}
        }
        
        # Get initial status for all counties
        initial_status = {}
        for county in counties:
            evaluation = self.get_county_evaluation(county)
            if evaluation:
                score = sum(1 for letter in EXECUTION_ORDER 
                          if evaluation.get(f"grade_{letter.lower()}") == 'PASS')
                initial_status[county] = {
                    'score': score,
                    'evaluation': evaluation
                }
            else:
                initial_status[county] = {'score': 0, 'evaluation': None}
            
            logger.info(f"{county}: Initial score {initial_status[county]['score']}/10")
        
        # Determine letters to execute
        if letters:
            target_letters = set(letters)
        else:
            # Get all failing letters across counties
            target_letters = set()
            for county in counties:
                target_letters.update(self.get_failing_letters(county))
        
        logger.info(f"Target letters: {sorted(target_letters)}")
        
        # Execute letters in dependency order
        for letter in EXECUTION_ORDER:
            if letter not in target_letters:
                continue
            
            logger.info(f"\n📌 Processing Letter {letter}...")
            
            if len(counties) == 1:
                # Single county execution
                result = self.execute_letter(letter, counties[0])
                results['letter_results'][letter] = result
            else:
                # Multi-county execution (let scripts handle it)
                result = self.execute_letter(letter)
                results['letter_results'][letter] = result
            
            if result.get('success'):
                logger.info(f"✅ Letter {letter} completed successfully")
            else:
                error = result.get('error', result.get('stderr', 'Unknown error'))
                logger.error(f"❌ Letter {letter} failed: {error}")
        
        # Get final status
        final_status = {}
        for county in counties:
            time.sleep(5)  # Let metrics propagate
            evaluation = self.get_county_evaluation(county)
            if evaluation:
                score = sum(1 for letter in EXECUTION_ORDER 
                          if evaluation.get(f"grade_{letter.lower()}") == 'PASS')
                final_status[county] = {
                    'score': score,
                    'evaluation': evaluation
                }
            else:
                final_status[county] = {'score': 0, 'evaluation': None}
            
            # Calculate improvement
            initial_score = initial_status[county]['score']
            final_score = final_status[county]['score']
            improvement = final_score - initial_score
            
            results['county_results'][county] = {
                'initial_score': initial_score,
                'final_score': final_score,
                'improvement': improvement,
                'initial_evaluation': initial_status[county]['evaluation'],
                'final_evaluation': final_status[county]['evaluation']
            }
            
            logger.info(f"{county}: {initial_score}/10 → {final_score}/10 ({improvement:+d})")
        
        # Summary
        total_improvement = sum(r['improvement'] for r in results['county_results'].values())
        successful_letters = sum(1 for r in results['letter_results'].values() if r.get('success'))
        
        results['end_time'] = datetime.now().isoformat()
        results['summary'] = {
            'total_counties': len(counties),
            'total_improvement': total_improvement,
            'letters_executed': len(results['letter_results']),
            'letters_successful': successful_letters,
            'execution_time_minutes': (datetime.now() - start_time).total_seconds() / 60
        }
        
        return results

def main():
    parser = argparse.ArgumentParser(description="SHARD-11 Gold Standard Pipeline Executor")
    parser.add_argument('--county', choices=TARGET_COUNTIES, help='Execute for single county')
    parser.add_argument('--letters', help='Specific letters to execute (e.g. BEH)')
    parser.add_argument('--full', action='store_true', help='Execute full pipeline for all counties')
    parser.add_argument('--verify-only', action='store_true', help='Only run verification, no execution')
    parser.add_argument('--output', help='Save results to JSON file')
    args = parser.parse_args()
    
    if not SUPABASE_KEY:
        logger.error("❌ SUPABASE_KEY environment variable required")
        sys.exit(1)
    
    print("=" * 60)
    print("SHARD-11 GOLD STANDARD PIPELINE EXECUTOR")
    print("Counties: manatee, bay, okeechobee, gadsden, wakulla")
    print("=" * 60)
    
    # Determine execution parameters
    if args.county:
        counties = [args.county]
    else:
        counties = TARGET_COUNTIES
    
    letters = set(args.letters.upper()) if args.letters else None
    
    executor = SHARD11PipelineExecutor()
    
    if args.verify_only:
        print("\n📊 VERIFICATION ONLY MODE")
        for county in counties:
            evaluation = executor.get_county_evaluation(county)
            if evaluation:
                score = sum(1 for letter in EXECUTION_ORDER 
                          if evaluation.get(f"grade_{letter.lower()}") == 'PASS')
                print(f"{county}: {score}/10")
                
                # Show failing letters
                failing = []
                for letter in EXECUTION_ORDER:
                    grade = evaluation.get(f"grade_{letter.lower()}")
                    if grade != 'PASS':
                        failing.append(letter)
                
                if failing:
                    print(f"  Failing: {', '.join(failing)}")
                else:
                    print(f"  🏆 ALL LETTERS PASSING!")
            else:
                print(f"{county}: No evaluation data")
        
        return
    
    # Execute pipeline
    try:
        results = executor.execute_pipeline(counties, letters)
        
        # Print summary
        print(f"\n{'='*60}")
        print("EXECUTION SUMMARY")
        print(f"{'='*60}")
        
        summary = results['summary']
        print(f"Counties processed: {summary['total_counties']}")
        print(f"Letters executed: {summary['letters_successful']}/{summary['letters_executed']}")
        print(f"Total improvement: {summary['total_improvement']} points")
        print(f"Execution time: {summary['execution_time_minutes']:.1f} minutes")
        
        # County details
        for county, county_result in results['county_results'].items():
            initial = county_result['initial_score']
            final = county_result['final_score']
            improvement = county_result['improvement']
            
            status = "✅" if improvement > 0 else "🔄" if improvement == 0 else "❌"
            print(f"{status} {county}: {initial}/10 → {final}/10 ({improvement:+d})")
        
        # Save results
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"\nDetailed results saved to: {args.output}")
        
        # Write to default location
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        default_file = f"/tmp/shard11_pipeline_{timestamp}.json"
        with open(default_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"Results also saved to: {default_file}")
        
    except KeyboardInterrupt:
        logger.info("Pipeline execution interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()