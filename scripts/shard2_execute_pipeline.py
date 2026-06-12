#!/usr/bin/env python3
"""
SHARD-2 GOLD STANDARD EXECUTION PIPELINE
Executes Letter B, I, J fixes and verifies metrics move
For citrus, pinellas, collier, santa_rosa, holmes counties

Usage:
  python scripts/shard2_execute_pipeline.py --county citrus
  python scripts/shard2_execute_pipeline.py --all-counties --verify-metrics
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

TARGET_COUNTIES = ['citrus', 'pinellas', 'collier', 'santa_rosa', 'holmes']

client = httpx.Client(timeout=120)

def run_script(script_name: str, county: str, dry_run: bool = False) -> Dict:
    """Run a SHARD-2 script and capture results"""
    cmd = [sys.executable, script_name, '--county', county]
    if dry_run:
        cmd.append('--dry-run')
    
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
        response = client.post(
            f"{BASE}/rpc/pencil_dod_evaluate_county",
            headers=HEADERS,
            json={"county_slug_arg": county},  # Try most common parameter name
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # Parse evaluation results
            metrics = {}
            if isinstance(result, list):
                for item in result:
                    if isinstance(item, dict):
                        letter = item.get('letter', '').upper()
                        metrics[f'grade_{letter.lower()}'] = 'PASS' if item.get('pass') else 'FAIL'
                        metrics[f'metric_{letter.lower()}'] = item.get('metric')
            
            return {
                'success': True,
                'metrics': metrics,
                'raw_result': result,
                'timestamp': datetime.now().isoformat()
            }
        else:
            logger.warning(f"Evaluation API returned {response.status_code}: {response.text}")
            return {
                'success': False,
                'error': f"HTTP {response.status_code}: {response.text}",
                'timestamp': datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error evaluating {county}: {e}")
        return {
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }

def apply_migration():
    """Apply bid_decisions table migration"""
    logger.info("Applying bid_decisions migration...")
    
    # Use Node.js migration runner
    try:
        result = subprocess.run([
            'node', 
            'migrations/run_migration.js', 
            'migrations/20260612_shard2_bid_decisions.sql'
        ], 
        capture_output=True, 
        text=True, 
        timeout=300,
        env={**os.environ, 'SUPABASE_DB_PASSWORD': os.environ.get('SUPABASE_DB_PASSWORD', '')}
        )
        
        if result.returncode == 0:
            logger.info("✅ Migration applied successfully")
            logger.info(result.stdout)
            return True
        else:
            logger.error("❌ Migration failed")
            logger.error(result.stderr)
            return False
            
    except Exception as e:
        logger.error(f"Migration error: {e}")
        return False

def execute_county_pipeline(county: str, verify_metrics: bool = True) -> Dict:
    """Execute complete pipeline for a single county"""
    logger.info(f"\n🎯 EXECUTING PIPELINE FOR {county.upper()}")
    
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
    letter_b_result = run_script('scripts/shard2_verified_outcomes.py', county)
    results['scripts']['letter_b'] = letter_b_result
    
    if letter_b_result['success']:
        logger.info("✅ Letter B script completed successfully")
    else:
        logger.error("❌ Letter B script failed")
        logger.error(letter_b_result['stderr'])
    
    # Execute Letter I: Property Cards  
    logger.info(f"\n🏠 Letter I: Property Cards for {county}")
    letter_i_result = run_script('scripts/shard2_property_cards.py', county)
    results['scripts']['letter_i'] = letter_i_result
    
    if letter_i_result['success']:
        logger.info("✅ Letter I script completed successfully")
    else:
        logger.error("❌ Letter I script failed")
        logger.error(letter_i_result['stderr'])
    
    # Execute Letter J: Deal Thesis
    logger.info(f"\n💰 Letter J: Deal Thesis for {county}")
    letter_j_result = run_script('scripts/shard2_deal_thesis.py', county)
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
            baseline_grade_b = baseline_metrics['metrics'].get('grade_b', 'UNKNOWN')
            final_grade_b = final_metrics['metrics'].get('grade_b', 'UNKNOWN')
            
            baseline_grade_i = baseline_metrics['metrics'].get('grade_i', 'UNKNOWN')
            final_grade_i = final_metrics['metrics'].get('grade_i', 'UNKNOWN')
            
            baseline_grade_j = baseline_metrics['metrics'].get('grade_j', 'UNKNOWN')
            final_grade_j = final_metrics['metrics'].get('grade_j', 'UNKNOWN')
            
            logger.info(f"\n📊 METRIC CHANGES FOR {county.upper()}:")
            logger.info(f"Letter B: {baseline_grade_b} → {final_grade_b}")
            logger.info(f"Letter I: {baseline_grade_i} → {final_grade_i}")
            logger.info(f"Letter J: {baseline_grade_j} → {final_grade_j}")
    
    results['end_time'] = datetime.now().isoformat()
    return results

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="SHARD-2 Gold Standard Pipeline Execution")
    parser.add_argument('--county', choices=TARGET_COUNTIES, help='Specific county to process')
    parser.add_argument('--all-counties', action='store_true', help='Process all SHARD-2 counties')
    parser.add_argument('--verify-metrics', action='store_true', help='Verify metrics move after fixes')
    parser.add_argument('--apply-migration', action='store_true', help='Apply bid_decisions table migration first')
    parser.add_argument('--dry-run', action='store_true', help='Run scripts in dry-run mode')
    
    args = parser.parse_args()
    
    if not SUPABASE_KEY:
        logger.error("SUPABASE_KEY environment variable not set")
        sys.exit(1)
    
    logger.info("🚀 SHARD-2 GOLD STANDARD PIPELINE EXECUTION")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    
    # Apply migration if requested
    if args.apply_migration:
        if not apply_migration():
            logger.error("Migration failed - continuing anyway")
    
    # Determine counties to process
    if args.county:
        counties_to_process = [args.county]
    elif args.all_counties:
        counties_to_process = TARGET_COUNTIES
    else:
        logger.error("Must specify --county or --all-counties")
        sys.exit(1)
    
    logger.info(f"Processing counties: {', '.join(counties_to_process)}")
    
    # Execute pipeline for each county
    all_results = []
    
    for county in counties_to_process:
        try:
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
    logger.info(f"\n🎯 SHARD-2 PIPELINE SUMMARY")
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

if __name__ == "__main__":
    main()