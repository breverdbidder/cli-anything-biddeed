#!/usr/bin/env python3
"""
SHARD-9 County Analysis and Priority Planning
Counties: lee, baker, okaloosa, dixie, taylor

Based on the briefing metrics from the issue, analyze current status and plan priority work.
This follows the GOLD STANDARD campaign priority framework.
"""
from datetime import datetime

# SHARD-9 Counties Current Metrics (from briefing)
SHARD9_STATUS = {
    'lee': {
        'score': '2/10',
        'metrics': {
            'A': {'status': 'PASS', 'metric': 6841, 'details': 'fc=6841 td=9344'},
            'B': {'status': 'FAIL', 'metric': None, 'details': 'verified=0 closed_sold=4722'},
            'C': {'status': 'FAIL', 'metric': 12.2, 'details': 'matched_clean=1981 of 16185'},
            'D': {'status': 'FAIL', 'metric': 63.2, 'details': 'matched_any=10233 of 16185'},
            'E': {'status': 'FAIL', 'metric': 78.5, 'details': 'parcel_linked=12713 of 16185'},
            'F': {'status': 'FAIL', 'metric': 0.0, 'details': 'tier1_sold=0 closed_sold=4722'},
            'G': {'status': 'FAIL', 'metric': None, 'details': 'density= far= pk1000='},
            'H': {'status': 'PASS', 'metric': 47.0, 'details': 'hours since last_seen (SLA 48h)'},
            'I': {'status': 'FAIL', 'metric': None, 'details': 'zoned_complete_parcels=0 field_complete_parcels=3126 auctions=16185'},
            'J': {'status': 'FAIL', 'metric': 0.0, 'details': 'deal_complete=0 of 16185 (triangle + two-arm CMA + ml_score + max_bid)'}
        }
    },
    'baker': {
        'score': '1/10',
        'metrics': {
            'A': {'status': 'PASS', 'metric': 36, 'details': 'fc=36 td=77'},
            'B': {'status': 'FAIL', 'metric': None, 'details': 'verified=0 closed_sold=28'},
            'C': {'status': 'FAIL', 'metric': 29.2, 'details': 'matched_clean=33 of 113'},
            'D': {'status': 'FAIL', 'metric': 84.1, 'details': 'matched_any=95 of 113'},
            'E': {'status': 'FAIL', 'metric': 40.7, 'details': 'parcel_linked=46 of 113'},
            'F': {'status': 'FAIL', 'metric': 0.0, 'details': 'tier1_sold=0 closed_sold=28'},
            'G': {'status': 'FAIL', 'metric': None, 'details': 'density= far= pk1000='},
            'H': {'status': 'FAIL', 'metric': 568.4, 'details': 'hours since last_seen (SLA 48h)'},
            'I': {'status': 'FAIL', 'metric': None, 'details': 'zoned_complete_parcels=0 field_complete_parcels=7 auctions=113'},
            'J': {'status': 'FAIL', 'metric': 0.0, 'details': 'deal_complete=0 of 113 (triangle + two-arm CMA + ml_score + max_bid)'}
        }
    },
    'okaloosa': {
        'score': '1/10',
        'metrics': {
            'A': {'status': 'PASS', 'metric': 850, 'details': 'fc=1166 td=850'},
            'B': {'status': 'FAIL', 'metric': None, 'details': 'verified=0 closed_sold=870'},
            'C': {'status': 'FAIL', 'metric': 17.1, 'details': 'matched_clean=345 of 2016'},
            'D': {'status': 'FAIL', 'metric': 53.7, 'details': 'matched_any=1082 of 2016'},
            'E': {'status': 'FAIL', 'metric': 74.9, 'details': 'parcel_linked=1509 of 2016'},
            'F': {'status': 'FAIL', 'metric': 0.0, 'details': 'tier1_sold=0 closed_sold=870'},
            'G': {'status': 'FAIL', 'metric': None, 'details': 'density= far= pk1000='},
            'H': {'status': 'FAIL', 'metric': 568.4, 'details': 'hours since last_seen (SLA 48h)'},
            'I': {'status': 'FAIL', 'metric': None, 'details': 'zoned_complete_parcels=0 field_complete_parcels=339 auctions=2016'},
            'J': {'status': 'FAIL', 'metric': 0.0, 'details': 'deal_complete=0 of 2016 (triangle + two-arm CMA + ml_score + max_bid)'}
        }
    },
    'dixie': {
        'score': '0/10',
        'metrics': {
            'A': {'status': 'FAIL', 'metric': 0, 'details': 'fc=0 td=0'},
            'B': {'status': 'FAIL', 'metric': None, 'details': 'verified=0 closed_sold=0'},
            'C': {'status': 'FAIL', 'metric': None, 'details': 'matched_clean=0 of 0'},
            'D': {'status': 'FAIL', 'metric': None, 'details': 'matched_any=0 of 0'},
            'E': {'status': 'FAIL', 'metric': None, 'details': 'parcel_linked=0 of 0'},
            'F': {'status': 'FAIL', 'metric': None, 'details': 'tier1_sold=0 closed_sold=0'},
            'G': {'status': 'FAIL', 'metric': None, 'details': 'density= far= pk1000='},
            'H': {'status': 'FAIL', 'metric': None, 'details': 'hours since last_seen (SLA 48h)'},
            'I': {'status': 'FAIL', 'metric': None, 'details': 'zoned_complete_parcels=0 field_complete_parcels=0 auctions=0'},
            'J': {'status': 'FAIL', 'metric': None, 'details': 'deal_complete=0 of 0 (triangle + two-arm CMA + ml_score + max_bid)'}
        }
    },
    'taylor': {
        'score': '0/10',
        'metrics': {
            'A': {'status': 'FAIL', 'metric': 0, 'details': 'fc=0 td=0'},
            'B': {'status': 'FAIL', 'metric': None, 'details': 'verified=0 closed_sold=0'},
            'C': {'status': 'FAIL', 'metric': None, 'details': 'matched_clean=0 of 0'},
            'D': {'status': 'FAIL', 'metric': None, 'details': 'matched_any=0 of 0'},
            'E': {'status': 'FAIL', 'metric': None, 'details': 'parcel_linked=0 of 0'},
            'F': {'status': 'FAIL', 'metric': None, 'details': 'tier1_sold=0 closed_sold=0'},
            'G': {'status': 'FAIL', 'metric': None, 'details': 'density= far= pk1000='},
            'H': {'status': 'FAIL', 'metric': None, 'details': 'hours since last_seen (SLA 48h)'},
            'I': {'status': 'FAIL', 'metric': None, 'details': 'zoned_complete_parcels=0 field_complete_parcels=0 auctions=0'},
            'J': {'status': 'FAIL', 'metric': None, 'details': 'deal_complete=0 of 0 (triangle + two-arm CMA + ml_score + max_bid)'}
        }
    }
}

def analyze_priorities():
    """Analyze county priorities based on current metrics and briefing guidance"""
    
    print("=== SHARD-9 PRIORITY ANALYSIS ===")
    print(f"Analysis time: {datetime.now().isoformat()}")
    print("Counties: lee, baker, okaloosa, dixie, taylor")
    
    # Count auctions per county (from details)
    print("\n=== County Auction Volumes ===")
    auction_counts = {}
    for county, data in SHARD9_STATUS.items():
        # Extract auction count from details
        if 'auctions=' in data['metrics']['I']['details']:
            count_str = data['metrics']['I']['details'].split('auctions=')[1]
            auction_counts[county] = int(count_str)
        else:
            auction_counts[county] = 0
            
        print(f"  {county}: {auction_counts[county]} auctions")
    
    # Priority analysis based on briefing guidance
    print("\n=== PRIORITY RANKING ===")
    print("Based on: auction volume, current scores, and potential impact")
    
    priority_counties = []
    
    # Lee: 16,185 auctions, 2/10 score - highest volume, some progress
    priority_counties.append(('lee', 16185, '2/10', 'HIGH - Largest volume with some foundation (A,H pass)'))
    
    # Okaloosa: 2,016 auctions, 1/10 score - medium volume
    priority_counties.append(('okaloosa', 2016, '1/10', 'MEDIUM - Good auction volume, A passes'))
    
    # Baker: 113 auctions, 1/10 score - small but manageable
    priority_counties.append(('baker', 113, '1/10', 'MEDIUM - Small volume, quick wins possible'))
    
    # Dixie & Taylor: 0 auctions - need initial data ingestion
    priority_counties.append(('dixie', 0, '0/10', 'LOW - No data, needs A letter (lane configuration)'))
    priority_counties.append(('taylor', 0, '0/10', 'LOW - No data, needs A letter (lane configuration)'))
    
    for i, (county, auctions, score, reasoning) in enumerate(priority_counties, 1):
        print(f"  {i}. {county}: {auctions} auctions, {score} → {reasoning}")
    
    # Letter priority analysis (from briefing - critical three: B, I, J)
    print("\n=== LETTER PRIORITY ANALYSIS ===")
    print("Focus on critical three: B (verified outcomes), I (property cards), J (deal thesis)")
    print("Plus: A (data ingestion for dixie/taylor)")
    
    letter_priorities = [
        ('A', 'Data ingestion - REQUIRED for dixie/taylor (0 auctions)'),
        ('B', 'Verified outcomes - 0 for all counties, independent source needed'),
        ('J', 'Deal thesis - 0 for all counties, generator missing'),
        ('C/D', 'Parity matching - poor rates across all counties'),
        ('E', 'Parcel linkage - fair to poor across counties'),
        ('I', 'Property cards - 0 zoned parcels for all counties'),
        ('G', 'Zoning KPI - null for all counties (needs zoning data)'),
        ('F', 'Tier1 sold - 0% for all counties'),
        ('H', 'Freshness - only lee passes (47h), others >500h')
    ]
    
    for priority, description in letter_priorities:
        print(f"  {priority}: {description}")
    
    return priority_counties

def recommend_session_plan():
    """Recommend 6-hour session execution plan"""
    print("\n=== 6-HOUR SESSION EXECUTION PLAN ===")
    print("Based on CRITERION-PARALLEL PIVOT and briefing priorities")
    
    plan = [
        {
            'phase': '1. Data Foundation (0.5-1h)',
            'tasks': [
                'Configure A letter for dixie/taylor (lane setup in pipeline.counties)',
                'Execute data ingestion to get baseline auction counts',
                'Verify pipeline.counties configuration for all 5 counties'
            ]
        },
        {
            'phase': '2. Critical B Letter - Verified Outcomes (2-3h)',  
            'tasks': [
                'Build independent verified outcome scrapers per county',
                'Focus on lee first (largest volume), then okaloosa',
                'Implement clerk-source data_source (NOT PropertyOnion)',
                'Target: move B from 0% to >95% for top 2 counties'
            ]
        },
        {
            'phase': '3. J Letter - Deal Thesis Generator (2-2.5h)',
            'tasks': [
                'Build bid_decisions generator per evaluator contract',
                'Implement: arv + max_bid + ml_score + 5 factor keys', 
                'Use Shapira V14 for ml_score, gen_valuations_comps_batch for CMA',
                'County-agnostic pipeline, test on lee/okaloosa first'
            ]
        },
        {
            'phase': '4. Verification & Close-out (0.5h)',
            'tasks': [
                'Run pencil_dod_evaluate_county for all 5 counties',
                'Document before/after metrics with SQL verification',
                'Commit all changes to main',
                'Execute gold_standard_loop if no other sessions active'
            ]
        }
    ]
    
    for phase_data in plan:
        print(f"\n{phase_data['phase']}:")
        for task in phase_data['tasks']:
            print(f"  - {task}")
    
    print("\n=== EXPECTED OUTCOMES ===")
    print("Conservative targets for 6h session:")
    print("  - dixie/taylor: 0/10 → 1/10 (A letter working)")
    print("  - lee: 2/10 → 4/10 (B,J working)")
    print("  - okaloosa: 1/10 → 3/10 (B,J working)")  
    print("  - baker: 1/10 → 2/10 (J working)")
    print("  - Fleet J letter: 0% → functional generator pipeline")
    
def main():
    """Main analysis execution"""
    analyze_priorities()
    recommend_session_plan()
    
    print(f"\n=== ANALYSIS COMPLETE ===")
    print(f"Time: {datetime.now().isoformat()}")
    print("Ready to execute session plan...")
    print("Next: Begin Phase 1 - Data Foundation work")

if __name__ == "__main__":
    main()