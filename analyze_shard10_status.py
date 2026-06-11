#!/usr/bin/env python3
"""
Comprehensive analysis of SHARD-10 counties Gold Standard status
Based on pencil_dod_evaluate_county function and current metrics
"""
import os
import json
import requests
from datetime import datetime

# Configuration
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

TARGET_COUNTIES = ['manatee', 'alachua', 'martin', 'franklin', 'union']
COUNTY_DOR_NUMBERS = {
    'manatee': 51,   # CO_NO from fl_counties_manifest.yml
    'alachua': 11,  
    'martin': 53,
    'franklin': 29,
    'union': 73
}

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def make_request(url, method='GET', data=None):
    """Make authenticated request to Supabase"""
    try:
        if method == 'GET':
            response = requests.get(url, headers=sb_headers(), timeout=30)
        elif method == 'POST':
            response = requests.post(url, headers=sb_headers(), json=data, timeout=30)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Request failed: {response.status_code} - {response.text[:200]}")
            return None
    except Exception as e:
        print(f"❌ Request error: {e}")
        return None

def evaluate_county(county_slug):
    """Evaluate county using pencil_dod_evaluate_county RPC"""
    print(f"\n🔍 Evaluating {county_slug.upper()}")
    
    result = make_request(
        f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
        method='POST',
        data={"county_slug_arg": county_slug}
    )
    
    if not result:
        print(f"❌ Failed to evaluate {county_slug}")
        return None
    
    analysis = {
        'county': county_slug,
        'letters': {},
        'pass_count': 0,
        'failing_letters': [],
        'priority_fixes': []
    }
    
    for letter_data in result:
        letter = letter_data.get('letter', '?')
        is_pass = letter_data.get('pass', False)
        metric = letter_data.get('metric', 0)
        detail = letter_data.get('detail', '')
        threshold = letter_data.get('threshold', '')
        
        analysis['letters'][letter] = {
            'pass': is_pass,
            'metric': metric,
            'detail': detail,
            'threshold': threshold
        }
        
        if is_pass:
            analysis['pass_count'] += 1
            print(f"  {letter}: ✅ PASS metric={metric}")
        else:
            analysis['failing_letters'].append(letter)
            print(f"  {letter}: ❌ FAIL metric={metric} - {detail}")
            
            # Identify priority fixes based on metrics
            if letter == 'A' and metric < 2:
                analysis['priority_fixes'].append(f"Letter A: Need dual-product coverage - run county ingestion")
            elif letter == 'E' and metric > 80:
                analysis['priority_fixes'].append(f"Letter E: {metric:.1f}% parcel linkage - close to 95% threshold")
            elif letter == 'H' and metric > 48:
                analysis['priority_fixes'].append(f"Letter H: {metric:.1f}h stale - need scraper reactivation")
    
    print(f"  📊 TOTAL: {analysis['pass_count']}/10")
    return analysis

def check_basic_data(county_slug):
    """Check basic auction data availability"""
    co_no = COUNTY_DOR_NUMBERS.get(county_slug)
    
    # Check multi_county_auctions
    auction_data = make_request(
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.{county_slug}&select=count"
    )
    auction_count = len(auction_data) if auction_data else 0
    
    # Check sample_properties  
    if co_no:
        property_data = make_request(
            f"{SUPABASE_URL}/rest/v1/sample_properties?co_no=eq.{co_no}&select=count"
        )
        property_count = len(property_data) if property_data else 0
    else:
        property_count = 0
    
    # Check pipeline.counties configuration
    pipeline_data = make_request(
        f"{SUPABASE_URL}/rest/v1/counties?slug=eq.{county_slug}&select=*"
    )
    
    return {
        'county': county_slug,
        'co_no': co_no,
        'auction_count': auction_count,
        'property_count': property_count,
        'pipeline_configured': bool(pipeline_data),
        'has_baseline_data': auction_count > 0 or property_count > 0
    }

def analyze_improvement_priorities(evaluations):
    """Analyze and prioritize improvements across all counties"""
    print(f"\n📈 IMPROVEMENT PRIORITY ANALYSIS")
    
    # County priority scoring
    priorities = []
    for county, eval_data in evaluations.items():
        if not eval_data:
            continue
            
        score = 0
        urgency = []
        
        # Zero-data counties get highest priority 
        if eval_data['pass_count'] == 0:
            score += 100
            urgency.append("NO DATA - needs county ingestion")
        
        # Counties close to thresholds get high priority
        letters = eval_data.get('letters', {})
        for letter, data in letters.items():
            metric = data.get('metric', 0)
            
            if letter == 'E' and 80 <= metric < 95:
                score += 50
                urgency.append(f"Letter E at {metric:.1f}% - close to 95% threshold")
            elif letter == 'H' and metric > 48:
                score += 30
                urgency.append(f"Letter H stale ({metric:.1f}h)")
            elif letter in ['B', 'I', 'J'] and not data.get('pass'):
                score += 20
                urgency.append(f"Letter {letter} - critical three")
        
        priorities.append({
            'county': county,
            'score': score,
            'pass_count': eval_data['pass_count'],
            'urgency': urgency
        })
    
    # Sort by priority score
    priorities.sort(key=lambda x: x['score'], reverse=True)
    
    print(f"\n🎯 RECOMMENDED EXECUTION ORDER:")
    for i, county_data in enumerate(priorities, 1):
        county = county_data['county']
        score = county_data['score']
        pass_count = county_data['pass_count']
        urgency = county_data['urgency']
        
        print(f"  {i}. {county.upper()} (score={score}, {pass_count}/10)")
        for reason in urgency:
            print(f"     → {reason}")
    
    return priorities

def generate_execution_plan(priorities):
    """Generate concrete execution plan"""
    print(f"\n⚡ EXECUTION PLAN (6-hour session)")
    
    plan = {
        'phase_1_setup': [],
        'phase_2_high_impact': [],
        'phase_3_optimization': [],
        'estimated_time': {}
    }
    
    for county_data in priorities:
        county = county_data['county']
        urgency = county_data['urgency']
        pass_count = county_data['pass_count']
        
        if pass_count == 0:
            plan['phase_1_setup'].append({
                'county': county,
                'action': 'run_county_ingestion',
                'command': f"python scripts/ingest_county.py --county {COUNTY_DOR_NUMBERS[county]} --full",
                'estimated_minutes': 60,
                'expected_improvement': '+5 to +7 letters (A, C, D, E, potentially H)'
            })
        elif any('Letter E' in u for u in urgency):
            plan['phase_2_high_impact'].append({
                'county': county,
                'action': 'improve_parcel_linkage',
                'description': 'Query county property appraiser APIs for parcel matching',
                'estimated_minutes': 45,
                'expected_improvement': 'Letter E to PASS (+1)'
            })
        elif any('Letter H' in u for u in urgency):
            plan['phase_3_optimization'].append({
                'county': county,
                'action': 'fix_scraper_freshness',
                'description': 'Reconfigure scraper scheduling in pipeline.counties',
                'estimated_minutes': 20,
                'expected_improvement': 'Letter H to PASS (+1)'
            })
    
    # Calculate time estimates
    total_phase1 = sum(item['estimated_minutes'] for item in plan['phase_1_setup'])
    total_phase2 = sum(item['estimated_minutes'] for item in plan['phase_2_high_impact'])
    total_phase3 = sum(item['estimated_minutes'] for item in plan['phase_3_optimization'])
    
    print(f"\n  PHASE 1 - County Setup ({total_phase1} min):")
    for item in plan['phase_1_setup']:
        print(f"    • {item['county']}: {item['action']} ({item['estimated_minutes']}min)")
        print(f"      → {item['expected_improvement']}")
    
    print(f"\n  PHASE 2 - High Impact ({total_phase2} min):")
    for item in plan['phase_2_high_impact']:
        print(f"    • {item['county']}: {item['action']} ({item['estimated_minutes']}min)")
        print(f"      → {item['expected_improvement']}")
    
    print(f"\n  PHASE 3 - Optimization ({total_phase3} min):")
    for item in plan['phase_3_optimization']:
        print(f"    • {item['county']}: {item['action']} ({item['estimated_minutes']}min)")
        print(f"      → {item['expected_improvement']}")
    
    total_time = total_phase1 + total_phase2 + total_phase3 + 30  # +30 for verification
    print(f"\n  📊 TOTAL ESTIMATED TIME: {total_time} minutes ({total_time/60:.1f} hours)")
    
    return plan

def main():
    print("=" * 60)
    print("SHARD-10 GOLD STANDARD STATUS ANALYSIS")
    print("=" * 60)
    print(f"Target counties: {', '.join(TARGET_COUNTIES)}")
    print(f"Analysis time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    if not SUPABASE_KEY:
        print("❌ No Supabase API key available")
        return
    
    # Phase 1: Evaluate all counties
    print(f"\n🔍 PHASE 1: CURRENT STATUS EVALUATION")
    evaluations = {}
    data_status = {}
    
    for county in TARGET_COUNTIES:
        evaluations[county] = evaluate_county(county)
        data_status[county] = check_basic_data(county)
        print(f"  Basic data: {data_status[county]['auction_count']} auctions, {data_status[county]['property_count']} properties")
    
    # Phase 2: Analyze priorities
    print(f"\n🎯 PHASE 2: PRIORITY ANALYSIS") 
    priorities = analyze_improvement_priorities(evaluations)
    
    # Phase 3: Generate execution plan
    print(f"\n⚡ PHASE 3: EXECUTION PLAN")
    plan = generate_execution_plan(priorities)
    
    # Summary
    print(f"\n📋 SUMMARY")
    total_letters_passing = sum(e['pass_count'] for e in evaluations.values() if e)
    total_possible = len(TARGET_COUNTIES) * 10
    current_pct = (total_letters_passing / total_possible) * 100
    
    print(f"  Current status: {total_letters_passing}/{total_possible} letters passing ({current_pct:.1f}%)")
    print(f"  Zero-data counties: {len([c for c, d in data_status.items() if not d['has_baseline_data']])}")
    print(f"  High-priority fixes identified: {len(plan['phase_1_setup']) + len(plan['phase_2_high_impact'])}")

if __name__ == "__main__":
    main()