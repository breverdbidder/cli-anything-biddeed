#!/usr/bin/env python3
"""
SHARD-14 County Status Verification Script
Counties: osceola, gilchrist, seminole, hamilton
"""
import os
import sys
import requests
from typing import Dict, Any

def get_county_evaluation(county_slug: str) -> Dict[str, Any]:
    """Get evaluation for a specific county using pencil_dod_evaluate_county"""
    
    SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
    SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_KEY')
    
    if not SUPABASE_KEY:
        print("⚠️  No SUPABASE_SERVICE_KEY found - using briefing data")
        return get_briefing_data(county_slug)
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    # Call the PostgreSQL function directly
    function_call = {
        "args": [county_slug]
    }
    
    try:
        response = requests.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=headers,
            json=function_call,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            return result
        else:
            print(f"❌ Database query failed for {county_slug}: {response.status_code}")
            print(f"Response: {response.text}")
            return get_briefing_data(county_slug)
            
    except Exception as e:
        print(f"❌ Connection error for {county_slug}: {e}")
        return get_briefing_data(county_slug)

def get_briefing_data(county_slug: str) -> Dict[str, Any]:
    """Fallback to briefing data from issue"""
    
    briefing_data = {
        'osceola': {
            'county_slug': 'osceola',
            'total_score': 2,
            'letters': {
                'A': {'passed': True, 'metric': 1660, 'detail': 'fc=2360 td=1660'},
                'B': {'passed': False, 'metric': None, 'detail': 'verified=0 closed_sold=975'},
                'C': {'passed': False, 'metric': 15.9, 'detail': 'matched_clean=641 of 4020'},
                'D': {'passed': False, 'metric': 61.2, 'detail': 'matched_any=2462 of 4020'},
                'E': {'passed': False, 'metric': 71.1, 'detail': 'parcel_linked=2857 of 4020'},
                'F': {'passed': False, 'metric': 3.4, 'detail': 'tier1_sold=33 closed_sold=975'},
                'G': {'passed': False, 'metric': None, 'detail': 'density= far= pk1000='},
                'H': {'passed': True, 'metric': 1.7, 'detail': 'hours since last_seen (SLA 48h)'},
                'I': {'passed': False, 'metric': None, 'detail': 'zoned_complete_parcels=0 field_complete_parcels=475 auctions=4020'},
                'J': {'passed': False, 'metric': 0.0, 'detail': 'deal_complete=0 of 4020'}
            }
        },
        'gilchrist': {
            'county_slug': 'gilchrist',
            'total_score': 1,
            'letters': {
                'A': {'passed': True, 'metric': 2, 'detail': 'fc=5 td=2'},
                'B': {'passed': False, 'metric': None, 'detail': 'verified=0 closed_sold=3'},
                'C': {'passed': False, 'metric': 57.1, 'detail': 'matched_clean=4 of 7'},
                'D': {'passed': False, 'metric': 57.1, 'detail': 'matched_any=4 of 7'},
                'E': {'passed': False, 'metric': 42.9, 'detail': 'parcel_linked=3 of 7'},
                'F': {'passed': False, 'metric': 0.0, 'detail': 'tier1_sold=0 closed_sold=3'},
                'G': {'passed': False, 'metric': None, 'detail': 'density= far= pk1000='},
                'H': {'passed': False, 'metric': 385.0, 'detail': 'hours since last_seen (SLA 48h)'},
                'I': {'passed': False, 'metric': None, 'detail': 'zoned_complete_parcels=0 field_complete_parcels=0 auctions=7'},
                'J': {'passed': False, 'metric': 0.0, 'detail': 'deal_complete=0 of 7'}
            }
        },
        'seminole': {
            'county_slug': 'seminole',
            'total_score': 1,
            'letters': {
                'A': {'passed': True, 'metric': 575, 'detail': 'fc=2091 td=575'},
                'B': {'passed': False, 'metric': None, 'detail': 'verified=0 closed_sold=743'},
                'C': {'passed': False, 'metric': 20.6, 'detail': 'matched_clean=550 of 2666'},
                'D': {'passed': False, 'metric': 40.9, 'detail': 'matched_any=1090 of 2666'},
                'E': {'passed': False, 'metric': 80.3, 'detail': 'parcel_linked=2140 of 2666'},
                'F': {'passed': False, 'metric': 0.0, 'detail': 'tier1_sold=0 closed_sold=743'},
                'G': {'passed': False, 'metric': None, 'detail': 'density= far= pk1000='},
                'H': {'passed': False, 'metric': 241.3, 'detail': 'hours since last_seen (SLA 48h)'},
                'I': {'passed': False, 'metric': None, 'detail': 'zoned_complete_parcels=0 field_complete_parcels=259 auctions=2666'},
                'J': {'passed': False, 'metric': 0.0, 'detail': 'deal_complete=0 of 2666'}
            }
        },
        'hamilton': {
            'county_slug': 'hamilton',
            'total_score': 0,
            'letters': {
                'A': {'passed': False, 'metric': 0, 'detail': 'fc=0 td=0'},
                'B': {'passed': False, 'metric': None, 'detail': 'verified=0 closed_sold=0'},
                'C': {'passed': False, 'metric': None, 'detail': 'matched_clean=0 of 0'},
                'D': {'passed': False, 'metric': None, 'detail': 'matched_any=0 of 0'},
                'E': {'passed': False, 'metric': None, 'detail': 'parcel_linked=0 of 0'},
                'F': {'passed': False, 'metric': None, 'detail': 'tier1_sold=0 closed_sold=0'},
                'G': {'passed': False, 'metric': None, 'detail': 'density= far= pk1000='},
                'H': {'passed': False, 'metric': None, 'detail': 'hours since last_seen (SLA 48h)'},
                'I': {'passed': False, 'metric': None, 'detail': 'zoned_complete_parcels=0 field_complete_parcels=0 auctions=0'},
                'J': {'passed': False, 'metric': None, 'detail': 'deal_complete=0 of 0'}
            }
        }
    }
    
    return briefing_data.get(county_slug, {})

def format_metric(metric, detail):
    """Format metric display"""
    if metric is None:
        return "NULL"
    elif isinstance(metric, float):
        return f"{metric:.1f}%"
    else:
        return str(metric)

def main():
    """Main verification function"""
    
    print("="*70)
    print("SHARD-14 COUNTY STATUS VERIFICATION")
    print("Counties: osceola, gilchrist, seminole, hamilton")
    print("="*70)
    
    # Target counties for this shard
    counties = ['osceola', 'gilchrist', 'seminole', 'hamilton']
    results = {}
    
    print("\n📊 FETCHING CURRENT COUNTY METRICS...\n")
    
    for county in counties:
        print(f"Evaluating {county}...")
        results[county] = get_county_evaluation(county)
    
    print("\n" + "="*70)
    print("CURRENT STATUS SUMMARY")
    print("="*70)
    
    # Summary table
    for county, data in results.items():
        if data:
            score = data.get('total_score', 0)
            print(f"\n🏛️  **{county.upper()}** ({score}/10):")
            
            letters = data.get('letters', {})
            passing = []
            failing = []
            
            for letter in 'ABCDEFGHIJ':
                if letter in letters:
                    letter_data = letters[letter]
                    metric = format_metric(letter_data.get('metric'), letter_data.get('detail', ''))
                    
                    if letter_data.get('passed', False):
                        passing.append(f"{letter}={metric}")
                    else:
                        failing.append(f"{letter}={metric}")
            
            if passing:
                print(f"   ✅ PASS: {', '.join(passing)}")
            if failing:
                print(f"   ❌ FAIL: {', '.join(failing)}")
        else:
            print(f"\n🏛️  **{county.upper()}**: No data available")
    
    print("\n" + "="*70)
    print("PRIORITY ANALYSIS")
    print("="*70)
    
    # Analyze failing letters across all counties
    failing_by_letter = {}
    total_counties = len([c for c in counties if c in results and results[c]])
    
    for county, data in results.items():
        if data and 'letters' in data:
            for letter, letter_data in data['letters'].items():
                if not letter_data.get('passed', False):
                    if letter not in failing_by_letter:
                        failing_by_letter[letter] = []
                    failing_by_letter[letter].append(county)
    
    print(f"\n🎯 **HIGH-LEVERAGE TARGETS** (affecting multiple counties):")
    
    # Sort by impact (number of counties affected)
    sorted_letters = sorted(failing_by_letter.items(), 
                          key=lambda x: len(x[1]), 
                          reverse=True)
    
    for letter, counties_list in sorted_letters:
        impact = len(counties_list)
        if impact >= 2:  # Only show letters affecting 2+ counties
            print(f"   **Letter {letter}**: {impact}/{total_counties} counties - {', '.join(counties_list)}")
    
    print(f"\n📋 **RECOMMENDED SESSION PRIORITIES:**")
    print("1. **J GENERATOR** - All counties fail (0.0% deal completion)")
    print("2. **B RECONCILIATION** - All counties null verified outcomes") 
    print("3. **C/D PARITY FIXES** - Low matching rates across counties")
    print("4. **G/I INFRASTRUCTURE** - Zoning + property card substrates")
    print("5. **HAMILTON BOOTSTRAP** - Complete county setup (0/10 currently)")
    
    print(f"\n" + "="*70)
    print("SESSION EXECUTION READY")
    print("="*70)
    
    return results

if __name__ == "__main__":
    main()