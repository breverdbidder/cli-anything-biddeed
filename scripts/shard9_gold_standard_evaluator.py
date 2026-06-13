#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-9 Evaluator Script
Evaluates current metrics for lee, baker, okaloosa, dixie, taylor counties

Usage:
  python scripts/shard9_gold_standard_evaluator.py --baseline
  python scripts/shard9_gold_standard_evaluator.py --county lee
  python scripts/shard9_gold_standard_evaluator.py --verify-all
"""
import os
import sys
import argparse
import json
import requests
from datetime import datetime

# SHARD-9 target counties
SHARD9_COUNTIES = ['lee', 'baker', 'okaloosa', 'dixie', 'taylor']

# Supabase connection
SUPABASE_URL = 'https://mocerqjnksmhcjzxrewo.supabase.co'


def get_supabase_headers():
    """Get Supabase headers for API requests"""
    key = os.environ.get('SUPABASE_SERVICE_KEY', os.environ.get('SUPABASE_KEY', ''))
    if not key:
        raise RuntimeError("No SUPABASE_KEY found in environment")
    
    return {
        'apikey': key,
        'Authorization': f'Bearer {key}',
        'Content-Type': 'application/json'
    }


def evaluate_county(county_name: str) -> dict:
    """Evaluate a single county using pencil_dod_evaluate_county function"""
    try:
        headers = get_supabase_headers()
        url = f'{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county'
        data = {'county_name': county_name}
        
        response = requests.post(url, json=data, headers=headers, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        return {
            'county': county_name,
            'success': True,
            'data': result,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            'county': county_name,
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }


def parse_metrics(data):
    """Parse evaluation data to extract letter metrics"""
    if not data or not isinstance(data, dict):
        return {}
    
    metrics = {}
    for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
        key = f'letter_{letter.lower()}'
        if key in data:
            letter_data = data[key]
            if isinstance(letter_data, dict):
                metrics[letter] = {
                    'pass': letter_data.get('pass', False),
                    'metric': letter_data.get('metric'),
                    'details': letter_data.get('details', {})
                }
            else:
                metrics[letter] = {'pass': False, 'metric': None, 'details': {}}
    
    return metrics


def print_county_summary(county: str, evaluation: dict):
    """Print formatted summary for a county"""
    print(f"\n=== {county.upper()} EVALUATION ===")
    
    if not evaluation['success']:
        print(f"❌ ERROR: {evaluation['error']}")
        return
    
    data = evaluation['data']
    metrics = parse_metrics(data)
    
    if not metrics:
        print("❌ No metrics data found")
        return
    
    pass_count = sum(1 for m in metrics.values() if m.get('pass', False))
    total_count = len(metrics)
    
    print(f"Score: {pass_count}/{total_count}")
    print("Letters:")
    
    for letter, info in metrics.items():
        status = "✓" if info.get('pass', False) else "✗"
        metric_val = info.get('metric')
        if metric_val is not None:
            print(f"  {letter}: {status} {metric_val}")
        else:
            print(f"  {letter}: {status} null")


def get_baseline_all():
    """Get baseline metrics for all SHARD-9 counties"""
    print("GOLD STANDARD SHARD-9 BASELINE EVALUATION")
    print("=" * 50)
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    results = {}
    for county in SHARD9_COUNTIES:
        print(f"\nEvaluating {county}...")
        evaluation = evaluate_county(county)
        results[county] = evaluation
        print_county_summary(county, evaluation)
    
    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY:")
    
    for county in SHARD9_COUNTIES:
        evaluation = results[county]
        if evaluation['success']:
            data = evaluation['data']
            metrics = parse_metrics(data)
            pass_count = sum(1 for m in metrics.values() if m.get('pass', False))
            print(f"  {county:12s}: {pass_count}/10")
        else:
            print(f"  {county:12s}: ERROR")
    
    return results


def main():
    parser = argparse.ArgumentParser(description='SHARD-9 Gold Standard Evaluator')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--baseline', action='store_true', 
                      help='Get baseline for all SHARD-9 counties')
    group.add_argument('--county', choices=SHARD9_COUNTIES,
                      help='Evaluate specific county')
    group.add_argument('--verify-all', action='store_true',
                      help='Verify all counties (same as --baseline)')
    
    args = parser.parse_args()
    
    try:
        if args.baseline or args.verify_all:
            get_baseline_all()
        elif args.county:
            evaluation = evaluate_county(args.county)
            print_county_summary(args.county, evaluation)
            
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()