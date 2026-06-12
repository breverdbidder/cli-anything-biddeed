#!/usr/bin/env python3
"""
SHARD-19 County Evaluation Script
Evaluates current status for charlotte, citrus, broward counties

This script queries the current Gold Standard metrics for the assigned counties
and determines the highest-leverage improvements needed.
"""

import os
import sys
import json
import httpx
from datetime import datetime, timezone

# Target counties for SHARD-19
TARGET_COUNTIES = ['charlotte', 'citrus', 'broward']

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"

if not SUPABASE_KEY:
    print("❌ No Supabase key found in environment")
    print("Available environment variables:")
    for key in os.environ.keys():
        if 'SUPABASE' in key or 'DATABASE' in key:
            print(f"  {key}: {'SET' if os.environ[key] else 'NOT SET'}")
    sys.exit(1)

HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

def evaluate_county(county_name: str) -> dict:
    """Evaluate a single county using the pencil_dod_evaluate_county function"""
    
    try:
        client = httpx.Client(timeout=120)
        
        print(f"Evaluating {county_name}...")
        response = client.post(
            f"{BASE}/rpc/pencil_dod_evaluate_county",
            headers=HEADERS,
            json={'county_param': county_name},
            timeout=120
        )
        
        if response.status_code == 200:
            result = response.json()
            return {
                'county': county_name,
                'success': True,
                'data': result
            }
        else:
            return {
                'county': county_name,
                'success': False,
                'error': f"Status {response.status_code}: {response.text[:200]}"
            }
            
    except Exception as e:
        return {
            'county': county_name,
            'success': False,
            'error': str(e)
        }

def analyze_failing_criteria(evaluation_results: list) -> dict:
    """Analyze the evaluation results to identify failing criteria and prioritize fixes"""
    
    analysis = {
        'counties': {},
        'failing_letters': set(),
        'priorities': []
    }
    
    # Letters and their thresholds (from issue description)
    thresholds = {
        'A': None,  # dual-product coverage
        'B': 95.0,  # verified outcomes
        'C': 95.0,  # parity_clean
        'D': 95.0,  # parity_any
        'E': 95.0,  # parcel linkage
        'F': 95.0,  # tier1 sold-amount
        'G': 95.0,  # zoning KPI
        'H': 48.0,  # freshness <=48h
        'I': 95.0,  # property card complete
        'J': 95.0   # deal complete
    }
    
    for result in evaluation_results:
        if not result['success']:
            continue
            
        county = result['county']
        data = result['data']
        
        analysis['counties'][county] = {
            'passing': 0,
            'failing': 0,
            'metrics': {}
        }
        
        # Parse the evaluation data (format may vary)
        if isinstance(data, list) and data:
            metrics = data[0] if data else {}
        else:
            metrics = data
        
        analysis['counties'][county]['raw_data'] = metrics
    
    return analysis

def generate_priority_plan(analysis: dict) -> list:
    """Generate prioritized action plan based on failing criteria"""
    
    plan = []
    
    # High-impact fixes (affect multiple counties or have automation)
    plan.append({
        'priority': 'HIGH',
        'letter': 'B',
        'description': 'Verified outcomes - independent clerk sources',
        'approach': 'Build clerk-source verified-outcome scrapers',
        'affects': 'All counties'
    })
    
    plan.append({
        'priority': 'HIGH', 
        'letter': 'E',
        'description': 'Parcel linkage via county property appraiser',
        'approach': 'Link parcel_id via ArcGIS FeatureServer',
        'affects': 'All counties'
    })
    
    plan.append({
        'priority': 'MEDIUM',
        'letter': 'C/D',
        'description': 'Parity matching improvements',
        'approach': 'Reconcile parity_status, backfill missing auction dates',
        'affects': 'All counties'
    })
    
    plan.append({
        'priority': 'MEDIUM',
        'letter': 'J',
        'description': 'Deal thesis pipeline', 
        'approach': 'Populate bid_decisions with Shapira Formula',
        'affects': 'All counties'
    })
    
    plan.append({
        'priority': 'LOW',
        'letter': 'G/I',
        'description': 'Zoning and property cards',
        'approach': 'Extend zoning ingestion, enrich address/geo/value',
        'affects': 'All counties'
    })
    
    return plan

def main():
    print("=" * 80)
    print("SHARD-19 COUNTY EVALUATION - GOLD STANDARD RUN 19")
    print("=" * 80)
    print(f"Target Counties: {', '.join(TARGET_COUNTIES)}")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"Supabase URL: {SUPABASE_URL}")
    print()
    
    # Evaluate each county
    evaluation_results = []
    for county in TARGET_COUNTIES:
        result = evaluate_county(county)
        evaluation_results.append(result)
        
        if result['success']:
            print(f"✅ {county}: Evaluation successful")
        else:
            print(f"❌ {county}: {result['error']}")
    
    print()
    
    # Analyze results
    analysis = analyze_failing_criteria(evaluation_results)
    
    # Display current status
    print("CURRENT STATUS:")
    print("-" * 40)
    
    for result in evaluation_results:
        if result['success']:
            county = result['county']
            data = result['data']
            print(f"{county}:")
            print(f"  Raw data: {json.dumps(data, indent=2)}")
        else:
            print(f"{result['county']}: EVALUATION FAILED - {result['error']}")
    
    print()
    
    # Generate and display priority plan
    priority_plan = generate_priority_plan(analysis)
    
    print("PRIORITY ACTION PLAN:")
    print("-" * 40)
    
    for i, action in enumerate(priority_plan, 1):
        print(f"{i}. [{action['priority']}] Letter {action['letter']}: {action['description']}")
        print(f"   Approach: {action['approach']}")
        print(f"   Affects: {action['affects']}")
        print()
    
    print("NEXT STEPS:")
    print("-" * 40)
    print("1. Execute highest-priority fixes first (B, E)")
    print("2. Implement scrapers and data pipelines")
    print("3. Verify improvements with fresh evaluation")
    print("4. Commit directly to main per ship-to-main mandate")
    print("5. Report final results with SQL verification")
    
    # Save evaluation results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"shard19_evaluation_{timestamp}.json"
    
    try:
        with open(results_file, 'w') as f:
            json.dump({
                'timestamp': timestamp,
                'counties': TARGET_COUNTIES,
                'evaluation_results': evaluation_results,
                'analysis': analysis,
                'priority_plan': priority_plan
            }, f, indent=2)
        print(f"\n📄 Results saved to: {results_file}")
    except Exception as e:
        print(f"\n⚠️ Could not save results file: {e}")

if __name__ == "__main__":
    main()