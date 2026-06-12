#!/usr/bin/env python3
"""
SHARD-17 PIPELINE EXECUTOR - Immediate Execution
Runs all critical fixes for charlotte, citrus, broward counties (B, I, J letters)

This script EXECUTES immediately to start moving county metrics.
WIRING MANDATE: Code that is not executed scores zero.

Usage:
  python scripts/shard17_execute_pipeline.py --all        # Run all pipelines
  python scripts/shard17_execute_pipeline.py --verify     # Verification only
  python scripts/shard17_execute_pipeline.py --county charlotte --letters B,I,J
"""
import requests
import json
import os
import sys
import argparse
import subprocess
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# SHARD-17 counties
TARGET_COUNTIES = ['charlotte', 'citrus', 'broward']

def test_connection():
    """Test Supabase connection"""
    try:
        response = requests.get(f"{BASE}/audit_log", headers=HEADERS, params={"limit": "1"}, timeout=10)
        if response.status_code == 200:
            logger.info("✅ Supabase connection successful")
            return True
        else:
            logger.error(f"❌ Connection failed: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ Connection error: {e}")
        return False

def evaluate_county_current(county_slug):
    """Run the pencil_dod_evaluate_county function for a single county"""
    try:
        # Call the RPC function
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=HEADERS,
            json={"county_slug_arg": county_slug},
            timeout=60
        )
        
        if r.status_code == 200:
            result = r.json()
            if isinstance(result, list) and len(result) > 0:
                pass_count = sum(1 for item in result if item.get('pass'))
                failing_letters = [item.get('letter') for item in result if not item.get('pass')]
                return {
                    'county': county_slug,
                    'score': f"{pass_count}/10", 
                    'failing': failing_letters,
                    'details': result
                }
        return {'county': county_slug, 'score': 'FAILED', 'failing': [], 'details': []}
            
    except Exception as e:
        logger.error(f"Error evaluating county {county_slug}: {e}")
        return {'county': county_slug, 'score': 'ERROR', 'failing': [], 'details': []}

def run_pipeline_script(script_name, county=None, extra_args=None):
    """Run a pipeline script and return results"""
    try:
        cmd = ['python3', f'scripts/{script_name}']
        
        if county:
            cmd.extend(['--county', county])
        else:
            cmd.append('--all-counties')
            
        if extra_args:
            cmd.extend(extra_args)
        
        logger.info(f"Executing: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
            cwd='/home/runner/work/cli-anything-biddeed/cli-anything-biddeed'
        )
        
        if result.returncode == 0:
            logger.info(f"✅ {script_name} completed successfully")
            return {
                'script': script_name,
                'status': 'SUCCESS',
                'stdout': result.stdout,
                'stderr': result.stderr
            }
        else:
            logger.error(f"❌ {script_name} failed with code {result.returncode}")
            return {
                'script': script_name,
                'status': 'FAILED',
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode
            }
            
    except subprocess.TimeoutExpired:
        logger.error(f"❌ {script_name} timed out")
        return {'script': script_name, 'status': 'TIMEOUT'}
    except Exception as e:
        logger.error(f"❌ Error running {script_name}: {e}")
        return {'script': script_name, 'status': 'ERROR', 'error': str(e)}

def execute_letter_b_pipeline(counties):
    """Execute Letter B (verified outcomes) pipeline"""
    logger.info("🔍 Executing Letter B: Verified Outcomes Pipeline")
    results = []
    
    for county in counties:
        result = run_pipeline_script('shard17_verified_outcomes.py', county)
        results.append(result)
        
        # Brief pause between counties
        if len(counties) > 1:
            import time
            time.sleep(2)
    
    return results

def execute_letter_i_pipeline(counties):
    """Execute Letter I (property cards) pipeline"""
    logger.info("🏠 Executing Letter I: Property Cards Pipeline")
    results = []
    
    for county in counties:
        result = run_pipeline_script('shard17_property_cards.py', county)
        results.append(result)
        
        # Brief pause between counties
        if len(counties) > 1:
            import time
            time.sleep(2)
    
    return results

def execute_letter_j_pipeline(counties):
    """Execute Letter J (deal thesis) pipeline"""
    logger.info("💎 Executing Letter J: Deal Thesis Pipeline")
    results = []
    
    for county in counties:
        result = run_pipeline_script('shard17_deal_thesis.py', county)
        results.append(result)
        
        # Brief pause between counties
        if len(counties) > 1:
            import time
            time.sleep(2)
    
    return results

def run_verification_protocol():
    """Run verification protocol and return results"""
    logger.info("📊 Running Verification Protocol")
    
    # Get baseline scores
    baseline_scores = {}
    for county in TARGET_COUNTIES:
        baseline_scores[county] = evaluate_county_current(county)
    
    return baseline_scores

def execute_all_pipelines(counties, letters):
    """Execute all specified pipelines"""
    results = {
        'timestamp': datetime.now().isoformat(),
        'counties': counties,
        'letters': letters,
        'pipelines': {},
        'verification': {}
    }
    
    # Get baseline verification
    logger.info("📊 Getting baseline metrics...")
    results['verification']['baseline'] = run_verification_protocol()
    
    # Execute specified pipelines
    if 'B' in letters:
        results['pipelines']['B'] = execute_letter_b_pipeline(counties)
    
    if 'I' in letters:
        results['pipelines']['I'] = execute_letter_i_pipeline(counties)
    
    if 'J' in letters:
        results['pipelines']['J'] = execute_letter_j_pipeline(counties)
    
    # Get post-execution verification
    logger.info("📊 Getting post-execution metrics...")
    results['verification']['final'] = run_verification_protocol()
    
    return results

def report_results(results):
    """Generate summary report of execution results"""
    logger.info("\n" + "="*60)
    logger.info("🏆 SHARD-17 PIPELINE EXECUTION SUMMARY")
    logger.info("="*60)
    
    # County score comparison
    baseline = results['verification'].get('baseline', {})
    final = results['verification'].get('final', {})
    
    logger.info("\n📊 COUNTY SCORES (Before → After):")
    for county in results['counties']:
        baseline_score = baseline.get(county, {}).get('score', 'N/A')
        final_score = final.get(county, {}).get('score', 'N/A')
        logger.info(f"   {county:10s}: {baseline_score:>5s} → {final_score:>5s}")
    
    # Pipeline execution status
    logger.info("\n🔧 PIPELINE EXECUTION STATUS:")
    for letter, pipeline_results in results['pipelines'].items():
        success_count = sum(1 for r in pipeline_results if r.get('status') == 'SUCCESS')
        total_count = len(pipeline_results)
        logger.info(f"   Letter {letter}: {success_count}/{total_count} counties successful")
    
    # Detailed failing letters
    logger.info("\n❌ REMAINING FAILING LETTERS:")
    for county in results['counties']:
        county_final = final.get(county, {})
        failing = county_final.get('failing', [])
        if failing:
            logger.info(f"   {county}: {', '.join(failing)}")
    
    logger.info("="*60)

def main():
    parser = argparse.ArgumentParser(description='SHARD-17 Pipeline Executor')
    parser.add_argument('--all', action='store_true', help='Run all pipelines for all counties')
    parser.add_argument('--verify', action='store_true', help='Run verification only')
    parser.add_argument('--county', choices=TARGET_COUNTIES, help='Specific county')
    parser.add_argument('--letters', default='B,I,J', help='Letters to process (comma-separated)')
    parser.add_argument('--output', help='Save results to JSON file')
    
    args = parser.parse_args()
    
    # Validate environment
    if not SUPABASE_KEY:
        logger.error("❌ SUPABASE_KEY environment variable not set")
        sys.exit(1)
    
    if not test_connection():
        logger.error("❌ Failed to connect to Supabase")
        sys.exit(1)
    
    # Determine execution parameters
    if args.verify:
        logger.info("🔍 Running verification protocol only...")
        verification = run_verification_protocol()
        for county, data in verification.items():
            logger.info(f"{county}: {data['score']} - Failing: {', '.join(data['failing'])}")
        return
    
    counties = TARGET_COUNTIES if args.all or not args.county else [args.county]
    letters = [l.strip().upper() for l in args.letters.split(',')]
    
    logger.info(f"🎯 SHARD-17 Pipeline Execution Starting:")
    logger.info(f"   Counties: {', '.join(counties)}")
    logger.info(f"   Letters: {', '.join(letters)}")
    logger.info(f"   Timestamp: {datetime.now().isoformat()}")
    
    # Execute pipelines
    results = execute_all_pipelines(counties, letters)
    
    # Report results
    report_results(results)
    
    # Save results if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"📁 Results saved to: {args.output}")
    
    logger.info("\n🎯 SHARD-17 Pipeline execution complete!")

if __name__ == "__main__":
    main()