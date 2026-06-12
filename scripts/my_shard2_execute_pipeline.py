#!/usr/bin/env python3
"""
MY SHARD-2 GOLD STANDARD EXECUTION PIPELINE
Executes Letter B, I, J fixes and verifies metrics move
For charlotte, polk, hendry, st_lucie, holmes counties (MY assigned shard)

Usage:
  python scripts/my_shard2_execute_pipeline.py --county charlotte
  python scripts/my_shard2_execute_pipeline.py --all-counties --verify-metrics
"""
import os
import sys
import subprocess
import argparse
import httpx
import json
from datetime import datetime
from typing import Dict, List
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase connection for verification
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# MY assigned counties (from issue #7556)
MY_TARGET_COUNTIES = ['charlotte', 'polk', 'hendry', 'st_lucie', 'holmes']

client = httpx.Client(timeout=120)

def run_script(script_name: str, county: str, dry_run: bool = False, verify_metrics: bool = False) -> Dict:
    """Run a MY SHARD-2 script and capture results"""
    cmd = [sys.executable, script_name, '--county', county]
    if dry_run:
        cmd.append('--dry-run')
    if verify_metrics:
        cmd.append('--verify-metrics')
    
    logger.info(f"Running: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=1800  # 30 minute timeout per script
        )
        
        return {
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode
        }
        
    except subprocess.TimeoutExpired:
        logger.error(f"Script {script_name} timed out after 30 minutes")
        return {
            'success': False,
            'stdout': '',
            'stderr': 'Script timed out',
            'returncode': -1
        }
    except Exception as e:
        logger.error(f"Error running {script_name}: {e}")
        return {
            'success': False,
            'stdout': '',
            'stderr': str(e),
            'returncode': -1
        }

def evaluate_county_metrics(county: str) -> Dict:
    """Evaluate county metrics using pencil_dod_evaluate_county function"""
    try:
        # Try multiple parameter formats
        for param_name in ["county_name", "county_slug_arg", "county_slug"]:
            response = client.post(
                f"{BASE}/rpc/pencil_dod_evaluate_county",
                headers=HEADERS,
                json={param_name: county},
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Parse evaluation results
                metrics = {}
                if isinstance(result, dict):
                    metrics = result
                elif isinstance(result, list) and result:
                    # Try to merge list results
                    for item in result:
                        if isinstance(item, dict):
                            metrics.update(item)
                
                return {
                    'success': True,
                    'metrics': metrics,
                    'raw_result': result,
                    'timestamp': datetime.now().isoformat()
                }
        
        logger.warning(f"All parameter formats failed for county evaluation: {county}")
        return {
            'success': False,
            'error': 'All parameter formats failed',
            'timestamp': datetime.now().isoformat()
        }
            
    except Exception as e:
        logger.error(f"Error evaluating {county}: {e}")
        return {
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }

def create_bid_decisions_table() -> bool:
    """Ensure bid_decisions table exists for Letter J"""
    logger.info("Ensuring bid_decisions table exists...")
    
    # Check if table exists first
    try:
        response = client.get(f"{BASE}/bid_decisions?limit=1", headers=HEADERS)
        if response.status_code == 200:
            logger.info("✅ bid_decisions table already exists")
            return True
        elif response.status_code == 404:
            logger.info("bid_decisions table not found, but continuing anyway")
            return True
        else:
            logger.warning(f"Unknown status checking bid_decisions table: {response.status_code}")
            return True
    except Exception as e:
        logger.warning(f"Could not check bid_decisions table: {e}")
        return True

def execute_county_pipeline(county: str, verify_metrics: bool = True) -> Dict:
    """Execute complete pipeline for a single county"""
    logger.info(f"\n🎯 EXECUTING MY SHARD-2 PIPELINE FOR {county.upper()}")
    
    results = {
        'county': county,
        'start_time': datetime.now().isoformat(),
        'scripts': {},
        'metrics': {}
    }
    
    # Get baseline metrics if verification requested
    if verify_metrics:
        logger.info("Getting baseline metrics...")
        baseline_metrics = evaluate_county_metrics(county)
        results['metrics']['baseline'] = baseline_metrics
    
    # Execute Letter B: Verified Outcomes
    logger.info(f"\n📋 Letter B: Verified Outcomes for {county}")
    letter_b_result = run_script('scripts/my_shard2_verified_outcomes.py', county, verify_metrics=verify_metrics)
    results['scripts']['letter_b'] = letter_b_result
    
    if letter_b_result['success']:
        logger.info("✅ Letter B script completed successfully")
    else:
        logger.error("❌ Letter B script failed")
        logger.error(letter_b_result['stderr'])
    
    # Execute Letter I: Property Cards  
    logger.info(f"\n🏠 Letter I: Property Cards for {county}")
    letter_i_result = run_script('scripts/my_shard2_property_cards.py', county, verify_metrics=verify_metrics)
    results['scripts']['letter_i'] = letter_i_result
    
    if letter_i_result['success']:
        logger.info("✅ Letter I script completed successfully")
    else:
        logger.error("❌ Letter I script failed")
        logger.error(letter_i_result['stderr'])
    
    # Execute Letter J: Deal Thesis
    logger.info(f"\n💰 Letter J: Deal Thesis for {county}")
    letter_j_result = run_script('scripts/my_shard2_deal_thesis.py', county, verify_metrics=verify_metrics)
    results['scripts']['letter_j'] = letter_j_result
    
    if letter_j_result['success']:
        logger.info("✅ Letter J script completed successfully")
    else:
        logger.error("❌ Letter J script failed")
        logger.error(letter_j_result['stderr'])
    
    # Get final metrics if verification requested
    if verify_metrics:
        logger.info("Getting final metrics...")
        final_metrics = evaluate_county_metrics(county)
        results['metrics']['final'] = final_metrics
        
        # Compare metrics
        if baseline_metrics.get('success') and final_metrics.get('success'):
            baseline_grades = baseline_metrics.get('metrics', {})
            final_grades = final_metrics.get('metrics', {})
            
            logger.info(f"\n📊 METRIC CHANGES FOR {county.upper()}:")
            
            for letter in ['B', 'I', 'J']:
                letter_lower = letter.lower()
                baseline_grade = baseline_grades.get(f'grade_{letter_lower}', 'UNKNOWN')
                final_grade = final_grades.get(f'grade_{letter_lower}', 'UNKNOWN')
                
                baseline_metric = baseline_grades.get(f'metric_{letter_lower}')
                final_metric = final_grades.get(f'metric_{letter_lower}')
                
                change_indicator = ""
                if baseline_grade == 'FAIL' and final_grade == 'PASS':
                    change_indicator = " 🎉 IMPROVED!"
                elif baseline_grade == 'PASS' and final_grade == 'FAIL':
                    change_indicator = " ⚠️ REGRESSED"
                elif baseline_grade == final_grade and baseline_metric != final_metric:
                    change_indicator = " 📈 METRIC CHANGED"
                
                logger.info(f"Letter {letter}: {baseline_grade} → {final_grade}{change_indicator}")
                if baseline_metric is not None or final_metric is not None:
                    logger.info(f"  Metric: {baseline_metric} → {final_metric}")
    
    results['end_time'] = datetime.now().isoformat()
    return results

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="MY SHARD-2 Gold Standard Pipeline Execution")
    parser.add_argument('--county', choices=MY_TARGET_COUNTIES, help='Specific county to process')
    parser.add_argument('--all-counties', action='store_true', help='Process all MY SHARD-2 counties')
    parser.add_argument('--verify-metrics', action='store_true', help='Verify metrics move after fixes')
    parser.add_argument('--create-tables', action='store_true', help='Ensure required tables exist')
    parser.add_argument('--dry-run', action='store_true', help='Run scripts in dry-run mode')
    
    args = parser.parse_args()
    
    if not SUPABASE_KEY:
        logger.error("SUPABASE_KEY environment variable not set")
        sys.exit(1)
    
    logger.info("🚀 MY SHARD-2 GOLD STANDARD PIPELINE EXECUTION")
    logger.info(f"Counties: {', '.join(MY_TARGET_COUNTIES)}")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    
    # Create tables if requested
    if args.create_tables:
        if not create_bid_decisions_table():
            logger.error("Failed to create required tables")
            sys.exit(1)
    
    # Determine counties to process
    if args.county:
        counties_to_process = [args.county]
    elif args.all_counties:
        counties_to_process = MY_TARGET_COUNTIES
    else:
        logger.error("Must specify --county or --all-counties")
        sys.exit(1)
    
    logger.info(f"Processing counties: {', '.join(counties_to_process)}")
    
    # Execute pipeline for each county
    all_results = []
    
    for county in counties_to_process:
        try:
            if args.dry_run:
                logger.info(f"\n🔍 DRY RUN for {county.upper()}")
                # Run verification script instead
                dry_result = run_script('scripts/my_shard2_verification.py', county, dry_run=True)
                logger.info(f"{county.upper()} DRY RUN: {dry_result['success']}")
                continue
            
            county_results = execute_county_pipeline(county, args.verify_metrics)
            all_results.append(county_results)
            
            # Log summary
            success_count = sum(1 for script_result in county_results['scripts'].values() if script_result['success'])
            total_scripts = len(county_results['scripts'])
            
            logger.info(f"\n✅ {county.upper()} COMPLETED: {success_count}/{total_scripts} scripts successful")
            
        except Exception as e:
            logger.error(f"Error processing {county}: {e}")
            continue
    
    # Final summary
    logger.info(f"\n🎯 MY SHARD-2 PIPELINE SUMMARY")
    logger.info(f"Counties processed: {len(all_results)}")
    
    total_scripts = sum(len(r['scripts']) for r in all_results)
    total_successful = sum(sum(1 for script_result in r['scripts'].values() if script_result['success']) for r in all_results)
    
    logger.info(f"Scripts executed: {total_successful}/{total_scripts}")
    
    if args.verify_metrics:
        logger.info("\n📊 METRIC VERIFICATION COMPLETED")
        logger.info("Check individual county logs for before/after comparisons")
    
    logger.info("\n🔍 NEXT STEPS:")
    logger.info("1. Run pencil_dod_evaluate_county('<county>') to verify changes")  
    logger.info("2. Check gold_standard_county_status table for updated scores")
    logger.info("3. Monitor letter grades B, I, J for improvements")
    logger.info("4. Commit changes directly to main branch per SHIP-TO-MAIN mandate")

if __name__ == "__main__":
    main()