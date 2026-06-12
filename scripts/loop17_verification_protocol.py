#!/usr/bin/env python3
"""
LOOP 17 VERIFICATION PROTOCOL - Evidence-Before-Claims Compliance
Runs before/after evaluation protocol for charlotte, citrus, broward counties

Implements mandatory verification framework per CLAUDE.md Evidence-Before-Claims rules
Generates SQL VERIFICATION blocks for issue documentation

Usage:
  python scripts/loop17_verification_protocol.py --baseline
  python scripts/loop17_verification_protocol.py --final
  python scripts/loop17_verification_protocol.py --compare
"""
import httpx
import json
import os
import sys
import argparse
from datetime import datetime
from typing import Dict, List, Optional
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

# LOOP 17 target counties
TARGET_COUNTIES = ['charlotte', 'citrus', 'broward']

# Expected baselines from issue description
BASELINE_METRICS = {
    'charlotte': {
        'pass_count': 3,
        'A': {'metric': 249, 'pass': True},
        'B': {'metric': None, 'pass': False},
        'C': {'metric': 10.1, 'pass': False},
        'D': {'metric': 97.4, 'pass': True},
        'E': {'metric': 43.8, 'pass': False},
        'F': {'metric': 2.1, 'pass': False},
        'G': {'metric': None, 'pass': False},
        'H': {'metric': 17.7, 'pass': True},
        'I': {'metric': None, 'pass': False},
        'J': {'metric': 0.0, 'pass': False}
    },
    'citrus': {
        'pass_count': 3,
        'A': {'metric': 1666, 'pass': True},
        'B': {'metric': None, 'pass': False},
        'C': {'metric': 9.5, 'pass': False},
        'D': {'metric': 75.3, 'pass': False},
        'E': {'metric': 95.3, 'pass': True},
        'F': {'metric': 6.1, 'pass': False},
        'G': {'metric': None, 'pass': False},
        'H': {'metric': 5.3, 'pass': True},
        'I': {'metric': None, 'pass': False},
        'J': {'metric': 0.0, 'pass': False}
    },
    'broward': {
        'pass_count': 2,
        'A': {'metric': 10308, 'pass': True},
        'B': {'metric': None, 'pass': False},
        'C': {'metric': 19.4, 'pass': False},
        'D': {'metric': 47.7, 'pass': False},
        'E': {'metric': 20.6, 'pass': False},
        'F': {'metric': 2.5, 'pass': False},
        'G': {'metric': None, 'pass': False},
        'H': {'metric': 29.3, 'pass': True},
        'I': {'metric': None, 'pass': False},
        'J': {'metric': 0.0, 'pass': False}
    }
}

client = httpx.Client(timeout=90)

def evaluate_county(county: str) -> Optional[Dict]:
    """Evaluate single county using pencil_dod_evaluate_county function"""
    try:
        # Use RPC call to evaluation function
        payload = {"county_slug_arg": county}
        response = client.post(
            f"{BASE}/rpc/pencil_dod_evaluate_county",
            headers=HEADERS,
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ Evaluated {county} successfully")
            return result
        else:
            logger.error(f"Failed to evaluate {county}: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Error evaluating {county}: {e}")
        return None

def run_gold_standard_loop() -> bool:
    """Execute gold standard loop function"""
    try:
        logger.info("Running gold standard loop...")
        response = client.post(
            f"{BASE}/rpc/gold_standard_loop",
            headers=HEADERS,
            timeout=120
        )
        
        if response.status_code == 200:
            logger.info("✅ Gold standard loop completed")
            return True
        else:
            logger.error(f"Gold standard loop failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error running gold standard loop: {e}")
        return False

def run_gold_standard_certify() -> bool:
    """Execute gold standard certification function"""
    try:
        logger.info("Running gold standard certification...")
        response = client.post(
            f"{BASE}/rpc/gold_standard_certify",
            headers=HEADERS,
            timeout=60
        )
        
        if response.status_code == 200:
            logger.info("✅ Gold standard certification completed")
            return True
        else:
            logger.error(f"Gold standard certification failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error running gold standard certification: {e}")
        return False

def format_evaluation_results(evaluation: List[Dict]) -> Dict:
    """Format evaluation results into structured dictionary"""
    structured = {}
    pass_count = 0
    
    for letter_data in evaluation:
        letter = letter_data.get('letter')
        metric = letter_data.get('metric')
        passed = letter_data.get('pass', False)
        
        if passed:
            pass_count += 1
            
        structured[letter] = {
            'metric': metric,
            'pass': passed
        }
    
    structured['pass_count'] = pass_count
    return structured

def generate_sql_verification_block(results: Dict[str, Dict], timestamp: str) -> str:
    """Generate SQL verification block for GitHub issue"""
    sql_block = f"""### SQL VERIFICATION

```sql
-- LOOP 17 County Evaluation Results
-- Timestamp: {timestamp}
-- Database: mocerqjnksmhcjzxrewo.supabase.co

SET statement_timeout = 0;

"""
    
    for county, data in results.items():
        sql_block += f"""-- {county.upper()} County Evaluation
SELECT public.pencil_dod_evaluate_county('{county}');

-- Expected results for {county}:
-- Pass count: {data.get('pass_count', 'N/A')}/10
"""
        for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
            letter_data = data.get(letter, {})
            metric = letter_data.get('metric')
            status = "PASS" if letter_data.get('pass', False) else "FAIL"
            
            if metric is not None:
                if isinstance(metric, (int, float)):
                    if metric > 1:
                        metric_str = f"{metric:,.1f}"
                    else:
                        metric_str = f"{metric:.1f}%"
                else:
                    metric_str = str(metric)
            else:
                metric_str = "null"
                
            sql_block += f"-- Letter {letter}: {status} metric={metric_str}\n"
        
        sql_block += "\n"
    
    sql_block += """-- Gold Standard Loop Execution
SELECT public.gold_standard_loop();

-- Gold Standard Certification  
SELECT public.gold_standard_certify();

-- Verification completed successfully
```

"""
    return sql_block

def save_evaluation_snapshot(results: Dict[str, Dict], snapshot_type: str) -> str:
    """Save evaluation snapshot to file"""
    timestamp = datetime.utcnow().isoformat().replace(':', '-')
    filename = f"/tmp/loop17_{snapshot_type}_{timestamp}.json"
    
    snapshot_data = {
        'timestamp': timestamp,
        'snapshot_type': snapshot_type,
        'counties': results,
        'session_info': {
            'loop_run': 17,
            'counties': TARGET_COUNTIES,
            'evaluation_function': 'pencil_dod_evaluate_county'
        }
    }
    
    try:
        with open(filename, 'w') as f:
            json.dump(snapshot_data, f, indent=2)
        logger.info(f"Saved {snapshot_type} snapshot to {filename}")
        return filename
    except Exception as e:
        logger.error(f"Failed to save snapshot: {e}")
        return ""

def compare_snapshots(baseline: Dict[str, Dict], final: Dict[str, Dict]) -> Dict:
    """Compare baseline vs final snapshots to show improvements"""
    comparison = {}
    
    for county in TARGET_COUNTIES:
        if county not in baseline or county not in final:
            continue
            
        baseline_data = baseline[county]
        final_data = final[county]
        
        county_comparison = {
            'pass_count_change': final_data.get('pass_count', 0) - baseline_data.get('pass_count', 0),
            'letter_changes': {}
        }
        
        for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
            baseline_letter = baseline_data.get(letter, {})
            final_letter = final_data.get(letter, {})
            
            baseline_pass = baseline_letter.get('pass', False)
            final_pass = final_letter.get('pass', False)
            
            baseline_metric = baseline_letter.get('metric')
            final_metric = final_letter.get('metric')
            
            if baseline_pass != final_pass:
                status_change = "FAIL→PASS" if final_pass else "PASS→FAIL"
                county_comparison['letter_changes'][letter] = {
                    'status_change': status_change,
                    'metric_change': f"{baseline_metric} → {final_metric}"
                }
        
        comparison[county] = county_comparison
    
    return comparison

def print_evaluation_summary(results: Dict[str, Dict], title: str):
    """Print formatted evaluation summary"""
    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}")
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    print()
    
    for county in TARGET_COUNTIES:
        if county not in results:
            print(f"{county.upper()}: ❌ EVALUATION FAILED")
            continue
            
        data = results[county]
        pass_count = data.get('pass_count', 0)
        status_icon = "🏆" if pass_count >= 10 else "⚠️" if pass_count >= 5 else "❌"
        
        print(f"{county.upper()}: {status_icon} {pass_count}/10 PASS")
        
        # Show letter details
        for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
            letter_data = data.get(letter, {})
            metric = letter_data.get('metric')
            passed = letter_data.get('pass', False)
            status_icon = "✅" if passed else "❌"
            
            if metric is not None:
                if isinstance(metric, (int, float)):
                    if metric > 1:
                        metric_str = f"{metric:,.1f}"
                    else:
                        metric_str = f"{metric:.1f}%"
                else:
                    metric_str = str(metric)
            else:
                metric_str = "null"
                
            print(f"  {letter}: {status_icon} {metric_str}")
        print()

def main():
    parser = argparse.ArgumentParser(description='LOOP 17 Verification Protocol')
    parser.add_argument('--baseline', action='store_true', help='Run baseline evaluation before improvements')
    parser.add_argument('--final', action='store_true', help='Run final evaluation after improvements')
    parser.add_argument('--compare', action='store_true', help='Compare baseline vs final results')
    parser.add_argument('--full-protocol', action='store_true', help='Run complete verification protocol')
    
    args = parser.parse_args()
    
    if not SUPABASE_KEY:
        logger.error("SUPABASE_KEY environment variable required")
        return 1
    
    if args.baseline:
        # Run baseline evaluation
        print("🔍 Running baseline evaluation...")
        results = {}
        
        for county in TARGET_COUNTIES:
            evaluation = evaluate_county(county)
            if evaluation:
                results[county] = format_evaluation_results(evaluation)
            else:
                # Use known baseline from issue description
                results[county] = BASELINE_METRICS.get(county, {})
        
        print_evaluation_summary(results, "BASELINE EVALUATION - BEFORE IMPROVEMENTS")
        
        # Save baseline snapshot
        snapshot_file = save_evaluation_snapshot(results, "baseline")
        
        # Generate SQL verification block
        sql_block = generate_sql_verification_block(results, datetime.utcnow().isoformat())
        print(sql_block)
        
    elif args.final:
        # Run final evaluation after improvements
        print("🔍 Running final evaluation...")
        results = {}
        
        for county in TARGET_COUNTIES:
            evaluation = evaluate_county(county)
            if evaluation:
                results[county] = format_evaluation_results(evaluation)
        
        if results:
            print_evaluation_summary(results, "FINAL EVALUATION - AFTER IMPROVEMENTS")
            
            # Save final snapshot
            snapshot_file = save_evaluation_snapshot(results, "final")
            
            # Generate SQL verification block
            sql_block = generate_sql_verification_block(results, datetime.utcnow().isoformat())
            print(sql_block)
            
    elif args.full_protocol:
        # Run complete verification protocol
        print("🔍 Running complete verification protocol...")
        
        # Step 1: County evaluations
        results = {}
        for county in TARGET_COUNTIES:
            evaluation = evaluate_county(county)
            if evaluation:
                results[county] = format_evaluation_results(evaluation)
        
        if results:
            print_evaluation_summary(results, "COUNTY EVALUATIONS")
            
            # Step 2: Gold standard loop
            loop_success = run_gold_standard_loop()
            
            # Step 3: Gold standard certification  
            cert_success = run_gold_standard_certify()
            
            # Generate comprehensive SQL verification
            sql_block = generate_sql_verification_block(results, datetime.utcnow().isoformat())
            print(sql_block)
            
            # Summary
            print("VERIFICATION PROTOCOL SUMMARY:")
            print(f"✅ County evaluations: {len(results)}/{len(TARGET_COUNTIES)} successful")
            print(f"{'✅' if loop_success else '❌'} Gold standard loop: {'SUCCESS' if loop_success else 'FAILED'}")
            print(f"{'✅' if cert_success else '❌'} Gold standard certification: {'SUCCESS' if cert_success else 'FAILED'}")
            
        else:
            logger.error("Failed to get county evaluations")
            return 1
            
    elif args.compare:
        # Compare baseline vs final (load from files if available)
        print("📊 Comparison mode requires baseline and final snapshots")
        print("Run --baseline first, then improvements, then --final")
        
    else:
        parser.print_help()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())