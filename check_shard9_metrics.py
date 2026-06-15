#!/usr/bin/env python3
"""
SHARD-9 Current Metrics Check
Counties: putnam, hendry, orange, dixie, taylor

Check current gold standard metrics for assigned counties per briefing data.
"""

import os
import sys

# Assigned shard counties
SHARD9_COUNTIES = ['putnam', 'hendry', 'orange', 'dixie', 'taylor']

# Briefing data from the issue (current as of the session start)
BRIEFING_DATA = {
    'putnam': {
        'score': '2/10',
        'metrics': {
            'A': {'status': 'PASS', 'metric': 98, 'details': '[fc=98 td=7751]'},
            'B': {'status': 'FAIL', 'metric': None, 'details': '[verified=0 closed_sold=534]'},
            'C': {'status': 'FAIL', 'metric': 6.3, 'details': '[matched_clean=494 of 7849]'},
            'D': {'status': 'PASS', 'metric': 97.7, 'details': '[matched_any=7671 of 7849]'},
            'E': {'status': 'FAIL', 'metric': 17.9, 'details': '[parcel_linked=1402 of 7849]'},
            'F': {'status': 'FAIL', 'metric': 0.0, 'details': '[tier1_sold=0 closed_sold=534]'},
            'G': {'status': 'FAIL', 'metric': None, 'details': '[density= far= pk1000=]'},
            'H': {'status': 'FAIL', 'metric': 421.0, 'details': '[hours since last_seen (SLA 48h)]'},
            'I': {'status': 'FAIL', 'metric': None, 'details': '[zoned_complete_parcels=0 field_complete_parcels=526 auctions=7849]'},
            'J': {'status': 'FAIL', 'metric': 0.0, 'details': '[deal_complete=0 of 7849 (triangle + two-arm CMA + ml_score + max_bid)]'},
        }
    },
    'hendry': {
        'score': '1/10',
        'metrics': {
            'A': {'status': 'FAIL', 'metric': 0, 'details': '[fc=0 td=62]'},
            'B': {'status': 'FAIL', 'metric': None, 'details': '[verified=0 closed_sold=9]'},
            'C': {'status': 'FAIL', 'metric': 14.5, 'details': '[matched_clean=9 of 62]'},
            'D': {'status': 'PASS', 'metric': 100.0, 'details': '[matched_any=62 of 62]'},
            'E': {'status': 'FAIL', 'metric': 0.0, 'details': '[parcel_linked=0 of 62]'},
            'F': {'status': 'FAIL', 'metric': 0.0, 'details': '[tier1_sold=0 closed_sold=9]'},
            'G': {'status': 'FAIL', 'metric': None, 'details': '[density= far= pk1000=]'},
            'H': {'status': 'FAIL', 'metric': 763.1, 'details': '[hours since last_seen (SLA 48h)]'},
            'I': {'status': 'FAIL', 'metric': None, 'details': '[zoned_complete_parcels=0 field_complete_parcels=0 auctions=62]'},
            'J': {'status': 'FAIL', 'metric': 0.0, 'details': '[deal_complete=0 of 62 (triangle + two-arm CMA + ml_score + max_bid)]'},
        }
    },
    'orange': {
        'score': '1/10',
        'metrics': {
            'A': {'status': 'PASS', 'metric': 5540, 'details': '[fc=10591 td=5540]'},
            'B': {'status': 'FAIL', 'metric': None, 'details': '[verified=0 closed_sold=5311]'},
            'C': {'status': 'FAIL', 'metric': 15.8, 'details': '[matched_clean=2550 of 16131]'},
            'D': {'status': 'FAIL', 'metric': 42.8, 'details': '[matched_any=6911 of 16131]'},
            'E': {'status': 'FAIL', 'metric': 72.2, 'details': '[parcel_linked=11643 of 16131]'},
            'F': {'status': 'FAIL', 'metric': 3.9, 'details': '[tier1_sold=207 closed_sold=5311]'},
            'G': {'status': 'FAIL', 'metric': None, 'details': '[density= far= pk1000=]'},
            'H': {'status': 'FAIL', 'metric': 61.6, 'details': '[hours since last_seen (SLA 48h)]'},
            'I': {'status': 'FAIL', 'metric': None, 'details': '[zoned_complete_parcels=0 field_complete_parcels=1611 auctions=16131]'},
            'J': {'status': 'FAIL', 'metric': 0.0, 'details': '[deal_complete=0 of 16131 (triangle + two-arm CMA + ml_score + max_bid)]'},
        }
    },
    'dixie': {
        'score': '0/10',
        'metrics': {
            'A': {'status': 'FAIL', 'metric': 0, 'details': '[fc=0 td=0]'},
            'B': {'status': 'FAIL', 'metric': None, 'details': '[verified=0 closed_sold=0]'},
            'C': {'status': 'FAIL', 'metric': None, 'details': '[matched_clean=0 of 0]'},
            'D': {'status': 'FAIL', 'metric': None, 'details': '[matched_any=0 of 0]'},
            'E': {'status': 'FAIL', 'metric': None, 'details': '[parcel_linked=0 of 0]'},
            'F': {'status': 'FAIL', 'metric': None, 'details': '[tier1_sold=0 closed_sold=0]'},
            'G': {'status': 'FAIL', 'metric': None, 'details': '[density= far= pk1000=]'},
            'H': {'status': 'FAIL', 'metric': None, 'details': '[hours since last_seen (SLA 48h)]'},
            'I': {'status': 'FAIL', 'metric': None, 'details': '[zoned_complete_parcels=0 field_complete_parcels=0 auctions=0]'},
            'J': {'status': 'FAIL', 'metric': None, 'details': '[deal_complete=0 of 0 (triangle + two-arm CMA + ml_score + max_bid)]'},
        }
    },
    'taylor': {
        'score': '0/10',
        'metrics': {
            'A': {'status': 'FAIL', 'metric': 0, 'details': '[fc=0 td=0]'},
            'B': {'status': 'FAIL', 'metric': None, 'details': '[verified=0 closed_sold=0]'},
            'C': {'status': 'FAIL', 'metric': None, 'details': '[matched_clean=0 of 0]'},
            'D': {'status': 'FAIL', 'metric': None, 'details': '[matched_any=0 of 0]'},
            'E': {'status': 'FAIL', 'metric': None, 'details': '[parcel_linked=0 of 0]'},
            'F': {'status': 'FAIL', 'metric': None, 'details': '[tier1_sold=0 closed_sold=0]'},
            'G': {'status': 'FAIL', 'metric': None, 'details': '[density= far= pk1000=]'},
            'H': {'status': 'FAIL', 'metric': None, 'details': '[hours since last_seen (SLA 48h)]'},
            'I': {'status': 'FAIL', 'metric': None, 'details': '[zoned_complete_parcels=0 field_complete_parcels=0 auctions=0]'},
            'J': {'status': 'FAIL', 'metric': None, 'details': '[deal_complete=0 of 0 (triangle + two-arm CMA + ml_score + max_bid)]'},
        }
    }
}

def analyze_shard_priorities():
    """
    Analyze highest-leverage targets based on current metrics and briefing priorities.
    
    From briefing:
    - CRITERION-PARALLEL: C/D parity, E linkage, J generator
    - Priority targets: counties with existing data that can be improved
    """
    
    print("=== SHARD-9 METRICS ANALYSIS ===")
    print()
    
    # Total opportunities by county
    print("County Opportunities (current state from briefing):")
    for county, data in BRIEFING_DATA.items():
        score = data['score']
        print(f"  {county.upper()}: {score}")
    print()
    
    # Criterion-parallel analysis per briefing
    criterion_opportunities = {
        'C': [],  # parity_clean
        'D': [],  # parity_any
        'E': [],  # parcel linkage
        'J': []   # deal completion
    }
    
    for county, data in BRIEFING_DATA.items():
        for letter in ['C', 'D', 'E', 'J']:
            metric_data = data['metrics'][letter]
            if metric_data['status'] == 'FAIL':
                criterion_opportunities[letter].append({
                    'county': county,
                    'current_metric': metric_data['metric'],
                    'details': metric_data['details']
                })
    
    print("Criterion-Parallel Opportunities (C/D parity, E linkage, J generator):")
    for letter, opportunities in criterion_opportunities.items():
        print(f"\n  LETTER {letter} ({len(opportunities)} counties failing):")
        for opp in opportunities:
            print(f"    {opp['county']}: metric={opp['current_metric']} {opp['details']}")
    
    print("\n=== HIGHEST-LEVERAGE TARGETS ===")
    
    # Counties with existing data (not 0/10)
    viable_counties = []
    for county, data in BRIEFING_DATA.items():
        if data['score'] != '0/10':
            viable_counties.append(county)
    
    print(f"Counties with existing data (viable for immediate improvement): {viable_counties}")
    
    # Counties needing full setup
    setup_counties = []
    for county, data in BRIEFING_DATA.items():
        if data['score'] == '0/10':
            setup_counties.append(county)
    
    print(f"Counties needing full setup: {setup_counties}")
    
    print("\n=== RECOMMENDED EXECUTION ORDER ===")
    print("Per CRITERION-PARALLEL mandate and existing data:")
    print("1. ORANGE - highest E linkage metric (72.2), significant auction volume (16,131)")
    print("2. PUTNAM - some A/D passes, moderate volume (7,849 auctions)")
    print("3. HENDRY - D pass, small volume but manageable (62 auctions)")
    print("4. DIXIE/TAYLOR - full county setup (0 auctions, requires A-lane configuration)")
    
    return {
        'viable_counties': viable_counties,
        'setup_counties': setup_counties,
        'criterion_failures': criterion_opportunities
    }

if __name__ == "__main__":
    analysis = analyze_shard_priorities()
    
    print(f"\n=== SESSION FOCUS RECOMMENDATION ===")
    print("1. Start with ORANGE (C/D/E fixes) - highest leverage")
    print("2. Implement J generator (county-agnostic)")
    print("3. Apply fixes to PUTNAM and HENDRY") 
    print("4. Set up DIXIE and TAYLOR if time permits")
    print()
    print("CRITERION-PARALLEL approach: Fix C/D parity, E linkage, J generator across all viable counties")