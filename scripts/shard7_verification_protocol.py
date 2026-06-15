#!/usr/bin/env python3
"""
SHARD-7 Verification Protocol
Execute verification after all fixes and run final close-out

Per issue brief: "After each fix: SELECT public.pencil_dod_evaluate_county('<county>'); 
confirm the letter metric moved."

Final verification requirements:
- Before/after JSON comparison for each county
- Final close-out: SET statement_timeout=0; SELECT public.gold_standard_loop(); 
  SELECT public.gold_standard_certify();
"""

import os
import sys
import json
import httpx
import logging
import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# SHARD-7 counties and their baseline metrics from issue
SHARD7_BASELINE_METRICS = {
    'marion': {
        'A': {'baseline': 3021, 'pass': True},
        'B': {'baseline': 0, 'pass': False},
        'C': {'baseline': 9.6, 'pass': False},
        'D': {'baseline': 55.1, 'pass': False}, 
        'E': {'baseline': 67.6, 'pass': False},
        'F': {'baseline': 8.6, 'pass': False},
        'G': {'baseline': None, 'pass': False},
        'H': {'baseline': 3.2, 'pass': True},
        'I': {'baseline': None, 'pass': False},
        'J': {'baseline': 0.0, 'pass': False}
    },
    'collier': {
        'A': {'baseline': 559, 'pass': True},
        'B': {'baseline': 0, 'pass': False},
        'C': {'baseline': 17.3, 'pass': False},
        'D': {'baseline': 59.2, 'pass': False},
        'E': {'baseline': 64.8, 'pass': False},
        'F': {'baseline': 0.0, 'pass': False},
        'G': {'baseline': None, 'pass': False},
        'H': {'baseline': 610.4, 'pass': False},
        'I': {'baseline': None, 'pass': False},
        'J': {'baseline': 0.0, 'pass': False}
    },
    'miami_dade': {
        'A': {'baseline': 11343, 'pass': True},
        'B': {'baseline': 0, 'pass': False},
        'C': {'baseline': 19.3, 'pass': False},
        'D': {'baseline': 48.7, 'pass': False},
        'E': {'baseline': 16.7, 'pass': False},
        'F': {'baseline': 0.0, 'pass': False},
        'G': {'baseline': None, 'pass': False},
        'H': {'baseline': 314.0, 'pass': False},
        'I': {'baseline': None, 'pass': False},
        'J': {'baseline': 0.0, 'pass': False}
    },
    'columbia': {
        'A': {'baseline': 0, 'pass': False},
        'B': {'baseline': None, 'pass': False},
        'C': {'baseline': None, 'pass': False},
        'D': {'baseline': None, 'pass': False},
        'E': {'baseline': None, 'pass': False},
        'F': {'baseline': None, 'pass': False},
        'G': {'baseline': None, 'pass': False},
        'H': {'baseline': None, 'pass': False},
        'I': {'baseline': None, 'pass': False},
        'J': {'baseline': None, 'pass': False}
    },
    'madison': {
        'A': {'baseline': 0, 'pass': False},
        'B': {'baseline': None, 'pass': False},
        'C': {'baseline': None, 'pass': False},
        'D': {'baseline': None, 'pass': False},
        'E': {'baseline': None, 'pass': False},
        'F': {'baseline': None, 'pass': False},
        'G': {'baseline': None, 'pass': False},
        'H': {'baseline': None, 'pass': False},
        'I': {'baseline': None, 'pass': False},
        'J': {'baseline': None, 'pass': False}
    }
}

client = httpx.AsyncClient(timeout=90)

async def evaluate_county_current(county: str) -> Dict:
    """Execute pencil_dod_evaluate_county for verification"""
    try:
        logger.info(f"Evaluating {county} using pencil_dod_evaluate_county...")
        
        payload = {"county_slug_arg": county}
        response = await client.post(
            f"{BASE}/rpc/pencil_dod_evaluate_county",
            headers=HEADERS,
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            results = response.json()
            
            # Convert to structured format
            evaluation = {
                'county': county,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'evaluation_successful': True,
                'letters': {}
            }
            
            for item in results:
                letter = item.get('letter', '?')
                evaluation['letters'][letter] = {
                    'metric': item.get('metric'),
                    'pass': item.get('pass', False),
                    'details': item.get('details', ''),
                    'description': item.get('description', '')
                }
            
            # Calculate pass count
            evaluation['pass_count'] = sum(1 for letter in evaluation['letters'].values() if letter.get('pass'))
            evaluation['total_letters'] = len(evaluation['letters'])
            
            return evaluation
        else:
            logger.error(f"Failed to evaluate {county}: {response.status_code} - {response.text}")
            return {
                'county': county,
                'evaluation_successful': False,
                'error': f"HTTP {response.status_code}",
                'error_details': response.text[:500]
            }
            
    except Exception as e:
        logger.error(f"Error evaluating {county}: {e}")
        return {
            'county': county, 
            'evaluation_successful': False,
            'error': str(e)
        }

async def compare_before_after_metrics(county: str, current_evaluation: Dict) -> Dict:
    """Compare baseline vs current metrics to show improvement"""
    
    baseline = SHARD7_BASELINE_METRICS.get(county, {})
    current_letters = current_evaluation.get('letters', {})
    
    comparison = {
        'county': county,
        'letters_compared': {},
        'improvements': [],
        'regressions': [],
        'new_passes': [],
        'summary': {
            'baseline_passes': 0,
            'current_passes': 0,
            'net_improvement': 0
        }
    }
    
    # Compare each letter
    for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
        baseline_data = baseline.get(letter, {})
        current_data = current_letters.get(letter, {})
        
        baseline_metric = baseline_data.get('baseline')
        current_metric = current_data.get('metric')
        baseline_pass = baseline_data.get('pass', False)
        current_pass = current_data.get('pass', False)
        
        letter_comparison = {
            'letter': letter,
            'baseline_metric': baseline_metric,
            'current_metric': current_metric,
            'baseline_pass': baseline_pass,
            'current_pass': current_pass,
            'improved': False,
            'new_pass': False
        }
        
        # Check for improvements
        if baseline_metric is not None and current_metric is not None:
            # For most metrics, higher is better (except H which is hours)
            if letter == 'H':  # H is hours - lower is better
                if current_metric < baseline_metric:
                    letter_comparison['improved'] = True
                    comparison['improvements'].append(f"{letter}: {baseline_metric}h → {current_metric}h")
                elif current_metric > baseline_metric:
                    comparison['regressions'].append(f"{letter}: {baseline_metric}h → {current_metric}h")
            else:  # Other metrics - higher is better
                if current_metric > baseline_metric:
                    letter_comparison['improved'] = True
                    comparison['improvements'].append(f"{letter}: {baseline_metric} → {current_metric}")
                elif current_metric < baseline_metric:
                    comparison['regressions'].append(f"{letter}: {baseline_metric} → {current_metric}")
        
        # Check for new passes
        if not baseline_pass and current_pass:
            letter_comparison['new_pass'] = True
            comparison['new_passes'].append(letter)
        
        comparison['letters_compared'][letter] = letter_comparison
        
        # Count passes
        if baseline_pass:
            comparison['summary']['baseline_passes'] += 1
        if current_pass:
            comparison['summary']['current_passes'] += 1
    
    comparison['summary']['net_improvement'] = (
        comparison['summary']['current_passes'] - comparison['summary']['baseline_passes']
    )
    
    return comparison

async def run_gold_standard_loop() -> Dict:
    """Execute the final gold standard loop and certification"""
    logger.info("Running final gold_standard_loop and certification...")
    
    try:
        # First, set statement timeout to 0 for long operations
        logger.info("Setting statement timeout to 0...")
        response = await client.post(
            f"{BASE}/rpc/sql",
            headers=HEADERS,
            json={"query": "SET statement_timeout = 0;"},
            timeout=30
        )
        
        # Run gold_standard_loop
        logger.info("Executing gold_standard_loop()...")
        response = await client.post(
            f"{BASE}/rpc/gold_standard_loop",
            headers=HEADERS,
            json={},
            timeout=300  # 5 minute timeout for loop
        )
        
        loop_result = None
        if response.status_code == 200:
            loop_result = response.json()
            logger.info("✅ gold_standard_loop completed successfully")
        else:
            logger.error(f"gold_standard_loop failed: {response.status_code}")
        
        # Run gold_standard_certify
        logger.info("Executing gold_standard_certify()...")
        response = await client.post(
            f"{BASE}/rpc/gold_standard_certify",
            headers=HEADERS,
            json={},
            timeout=300  # 5 minute timeout for certify
        )
        
        certify_result = None
        if response.status_code == 200:
            certify_result = response.json()
            logger.info("✅ gold_standard_certify completed successfully")
        else:
            logger.error(f"gold_standard_certify failed: {response.status_code}")
        
        return {
            'gold_standard_loop_executed': loop_result is not None,
            'gold_standard_certify_executed': certify_result is not None,
            'loop_result': loop_result,
            'certify_result': certify_result,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error running gold standard operations: {e}")
        return {
            'gold_standard_loop_executed': False,
            'gold_standard_certify_executed': False,
            'error': str(e)
        }

async def run_shard7_verification_protocol():
    """Execute complete SHARD-7 verification protocol"""
    logger.info("🔍 SHARD-7 Verification Protocol - Final Verification")
    logger.info("="*60)
    
    shard7_counties = ['marion', 'collier', 'miami_dade', 'columbia', 'madison']
    
    verification_results = {
        'session_timestamp': datetime.now(timezone.utc).isoformat(),
        'counties_verified': {},
        'overall_summary': {
            'counties_processed': 0,
            'counties_improved': 0,
            'total_new_passes': 0,
            'total_improvements': 0
        },
        'gold_standard_operations': {}
    }
    
    # Step 1: Verify each county
    for county in shard7_counties:
        logger.info(f"\n--- Verifying {county.upper()} ---")
        
        # Get current evaluation
        current_evaluation = await evaluate_county_current(county)
        
        if current_evaluation.get('evaluation_successful'):
            # Compare with baseline
            comparison = await compare_before_after_metrics(county, current_evaluation)
            
            verification_results['counties_verified'][county] = {
                'current_evaluation': current_evaluation,
                'comparison': comparison,
                'verification_successful': True
            }
            
            # Print summary for this county
            print(f"\n{county.upper()} Verification Results:")
            print(f"  📊 Pass count: {current_evaluation.get('pass_count', 0)}/10")
            print(f"  📈 Net improvement: +{comparison['summary']['net_improvement']} letters")
            print(f"  ✅ New passes: {', '.join(comparison['new_passes']) if comparison['new_passes'] else 'None'}")
            print(f"  🔧 Improvements: {len(comparison['improvements'])}")
            
            for improvement in comparison['improvements'][:3]:  # Show first 3
                print(f"    • {improvement}")
            
            # Update overall summary
            verification_results['overall_summary']['counties_processed'] += 1
            if comparison['summary']['net_improvement'] > 0:
                verification_results['overall_summary']['counties_improved'] += 1
            verification_results['overall_summary']['total_new_passes'] += len(comparison['new_passes'])
            verification_results['overall_summary']['total_improvements'] += len(comparison['improvements'])
        else:
            verification_results['counties_verified'][county] = {
                'verification_successful': False,
                'error': current_evaluation.get('error', 'Unknown error')
            }
            print(f"  ❌ Verification failed for {county}")
    
    # Step 2: Run gold standard operations 
    logger.info(f"\n--- Final Gold Standard Operations ---")
    gold_ops_result = await run_gold_standard_loop()
    verification_results['gold_standard_operations'] = gold_ops_result
    
    if gold_ops_result.get('gold_standard_loop_executed'):
        print("  ✅ gold_standard_loop() executed successfully")
    else:
        print("  ❌ gold_standard_loop() failed")
    
    if gold_ops_result.get('gold_standard_certify_executed'):
        print("  ✅ gold_standard_certify() executed successfully")
    else:
        print("  ❌ gold_standard_certify() failed")
    
    return verification_results

def main():
    """Main verification function"""
    logger.info("SHARD-7 Verification Protocol - Post-Fix Verification & Close-out")
    
    # Run complete verification
    results = asyncio.run(run_shard7_verification_protocol())
    
    # Print final summary
    print(f"\n{'='*60}")
    print(f"SHARD-7 VERIFICATION PROTOCOL COMPLETE")
    print(f"{'='*60}")
    
    summary = results.get('overall_summary', {})
    print(f"Counties processed: {summary.get('counties_processed', 0)}/5")
    print(f"Counties with improvements: {summary.get('counties_improved', 0)}")
    print(f"Total new letter passes: {summary.get('total_new_passes', 0)}")
    print(f"Total metric improvements: {summary.get('total_improvements', 0)}")
    
    # Show final county scores
    print(f"\nFinal County Pass Counts:")
    for county, data in results.get('counties_verified', {}).items():
        if data.get('verification_successful'):
            pass_count = data.get('current_evaluation', {}).get('pass_count', 0)
            print(f"  {county}: {pass_count}/10")
        else:
            print(f"  {county}: VERIFICATION FAILED")
    
    # JSON output for session record
    print(f"\n### SQL VERIFICATION")
    print(f"```sql")
    print(f"-- SHARD-7 Verification completed at {results.get('session_timestamp')}")
    for county in ['marion', 'collier', 'miami_dade', 'columbia', 'madison']:
        county_data = results.get('counties_verified', {}).get(county, {})
        if county_data.get('verification_successful'):
            pass_count = county_data.get('current_evaluation', {}).get('pass_count', 0)
            print(f"-- {county}: {pass_count}/10 letters passing")
        else:
            print(f"-- {county}: verification failed")
    print(f"```")
    
    # Detailed JSON for record keeping
    print(f"\nDetailed Verification Results:")
    print(json.dumps(results, indent=2, default=str))

if __name__ == "__main__":
    main()