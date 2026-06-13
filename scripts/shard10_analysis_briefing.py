#!/usr/bin/env python3
"""
SHARD-10 Analysis from Briefing Data
Based on issue briefing metrics for autonomous gold standard session

Counties: leon, bay, okeechobee, franklin, union
"""
import os
from datetime import datetime

def main():
    print("🔍 SHARD-10 ANALYSIS FROM BRIEFING DATA")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("="*60)
    
    # Data from the issue briefing (run 22 metrics)
    briefing_data = {
        'leon': {
            'score': 2,  # A✓, H✓
            'metrics': {
                'A': {'grade': 'PASS', 'metric': 822, 'details': '[fc=1231 td=822]'},
                'B': {'grade': 'FAIL', 'metric': None, 'details': '[verified=0 closed_sold=863]'},
                'C': {'grade': 'FAIL', 'metric': 12.7, 'details': '[matched_clean=261 of 2053]'},
                'D': {'grade': 'FAIL', 'metric': 51.0, 'details': '[matched_any=1047 of 2053]'},
                'E': {'grade': 'FAIL', 'metric': 6.7, 'details': '[parcel_linked=138 of 2053]'},
                'F': {'grade': 'FAIL', 'metric': 7.1, 'details': '[tier1_sold=61 closed_sold=863]'},
                'G': {'grade': 'FAIL', 'metric': None, 'details': '[density= far= pk1000=]'},
                'H': {'grade': 'PASS', 'metric': 26.0, 'details': '[hours since last_seen (SLA 48h)]'},
                'I': {'grade': 'FAIL', 'metric': None, 'details': '[zoned_complete_parcels=0 field_complete_parcels=0 auctions=2053]'},
                'J': {'grade': 'FAIL', 'metric': 0.0, 'details': '[deal_complete=0 of 2053 (triangle + two-arm CMA + ml_score + max_bid)]'}
            }
        },
        'bay': {
            'score': 1,  # A✓
            'metrics': {
                'A': {'grade': 'PASS', 'metric': 1362, 'details': '[fc=1362 td=1585]'},
                'B': {'grade': 'FAIL', 'metric': None, 'details': '[verified=0 closed_sold=1239]'},
                'C': {'grade': 'FAIL', 'metric': 15.6, 'details': '[matched_clean=460 of 2947]'},
                'D': {'grade': 'FAIL', 'metric': 60.1, 'details': '[matched_any=1772 of 2947]'},
                'E': {'grade': 'FAIL', 'metric': 81.3, 'details': '[parcel_linked=2396 of 2947]'},
                'F': {'grade': 'FAIL', 'metric': 0.0, 'details': '[tier1_sold=0 closed_sold=1239]'},
                'G': {'grade': 'FAIL', 'metric': None, 'details': '[density= far= pk1000=]'},
                'H': {'grade': 'FAIL', 'metric': 361.0, 'details': '[hours since last_seen (SLA 48h)]'},
                'I': {'grade': 'FAIL', 'metric': None, 'details': '[zoned_complete_parcels=0 field_complete_parcels=679 auctions=2947]'},
                'J': {'grade': 'FAIL', 'metric': 0.0, 'details': '[deal_complete=0 of 2947 (triangle + two-arm CMA + ml_score + max_bid)]'}
            }
        },
        'okeechobee': {
            'score': 1,  # A✓
            'metrics': {
                'A': {'grade': 'PASS', 'metric': 164, 'details': '[fc=164 td=286]'},
                'B': {'grade': 'FAIL', 'metric': None, 'details': '[verified=0 closed_sold=162]'},
                'C': {'grade': 'FAIL', 'metric': 17.3, 'details': '[matched_clean=78 of 450]'},
                'D': {'grade': 'FAIL', 'metric': 74.2, 'details': '[matched_any=334 of 450]'},
                'E': {'grade': 'FAIL', 'metric': 85.6, 'details': '[parcel_linked=385 of 450]'},
                'F': {'grade': 'FAIL', 'metric': 0.0, 'details': '[tier1_sold=0 closed_sold=162]'},
                'G': {'grade': 'FAIL', 'metric': None, 'details': '[density= far= pk1000=]'},
                'H': {'grade': 'FAIL', 'metric': 385.0, 'details': '[hours since last_seen (SLA 48h)]'},
                'I': {'grade': 'FAIL', 'metric': None, 'details': '[zoned_complete_parcels=0 field_complete_parcels=136 auctions=450]'},
                'J': {'grade': 'FAIL', 'metric': 0.0, 'details': '[deal_complete=0 of 450 (triangle + two-arm CMA + ml_score + max_bid)]'}
            }
        },
        'franklin': {
            'score': 0,  # All failing
            'metrics': {
                'A': {'grade': 'FAIL', 'metric': 0, 'details': '[fc=0 td=0]'},
                'B': {'grade': 'FAIL', 'metric': None, 'details': '[verified=0 closed_sold=0]'},
                'C': {'grade': 'FAIL', 'metric': None, 'details': '[matched_clean=0 of 0]'},
                'D': {'grade': 'FAIL', 'metric': None, 'details': '[matched_any=0 of 0]'},
                'E': {'grade': 'FAIL', 'metric': None, 'details': '[parcel_linked=0 of 0]'},
                'F': {'grade': 'FAIL', 'metric': None, 'details': '[tier1_sold=0 closed_sold=0]'},
                'G': {'grade': 'FAIL', 'metric': None, 'details': '[density= far= pk1000=]'},
                'H': {'grade': 'FAIL', 'metric': None, 'details': '[hours since last_seen (SLA 48h)]'},
                'I': {'grade': 'FAIL', 'metric': None, 'details': '[zoned_complete_parcels=0 field_complete_parcels=0 auctions=0]'},
                'J': {'grade': 'FAIL', 'metric': None, 'details': '[deal_complete=0 of 0 (triangle + two-arm CMA + ml_score + max_bid)]'}
            }
        },
        'union': {
            'score': 0,  # All failing
            'metrics': {
                'A': {'grade': 'FAIL', 'metric': 0, 'details': '[fc=0 td=0]'},
                'B': {'grade': 'FAIL', 'metric': None, 'details': '[verified=0 closed_sold=0]'},
                'C': {'grade': 'FAIL', 'metric': None, 'details': '[matched_clean=0 of 0]'},
                'D': {'grade': 'FAIL', 'metric': None, 'details': '[matched_any=0 of 0]'},
                'E': {'grade': 'FAIL', 'metric': None, 'details': '[parcel_linked=0 of 0]'},
                'F': {'grade': 'FAIL', 'metric': None, 'details': '[tier1_sold=0 closed_sold=0]'},
                'G': {'grade': 'FAIL', 'metric': None, 'details': '[density= far= pk1000=]'},
                'H': {'grade': 'FAIL', 'metric': None, 'details': '[hours since last_seen (SLA 48h)]'},
                'I': {'grade': 'FAIL', 'metric': None, 'details': '[zoned_complete_parcels=0 field_complete_parcels=0 auctions=0]'},
                'J': {'grade': 'FAIL', 'metric': None, 'details': '[deal_complete=0 of 0 (triangle + two-arm CMA + ml_score + max_bid)]'}
            }
        }
    }
    
    # County numbers from fl_counties_manifest.yml
    county_numbers = {
        'leon': 47,
        'bay': 13,
        'okeechobee': 57,
        'franklin': 29,
        'union': 73
    }
    
    print("📊 CURRENT COUNTY STATUS:")
    for county, data in briefing_data.items():
        print(f"\n### {county.upper()} (co_no={county_numbers[county]})")
        print(f"**Score**: {data['score']}/10")
        
        passing = [letter for letter, info in data['metrics'].items() if info['grade'] == 'PASS']
        failing = [letter for letter, info in data['metrics'].items() if info['grade'] == 'FAIL']
        
        if passing:
            print(f"**Passing**: {', '.join(passing)}")
        print(f"**Failing**: {', '.join(failing)}")
        
        # Show specific metrics for key failing letters
        for letter in ['C', 'D', 'E']:
            if letter in failing:
                metric = data['metrics'][letter]['metric']
                details = data['metrics'][letter]['details']
                if metric is not None:
                    print(f"  - **{letter}**: {metric}% {details}")
    
    # Analyze failing letters across counties
    failing_by_letter = {}
    for county, data in briefing_data.items():
        for letter, info in data['metrics'].items():
            if info['grade'] == 'FAIL':
                if letter not in failing_by_letter:
                    failing_by_letter[letter] = []
                failing_by_letter[letter].append(county)
    
    print(f"\n" + "="*60)
    print("FAILING LETTERS ANALYSIS")
    print("="*60)
    
    # Priority order for SHARD-10 based on impact
    priority_letters = ['A', 'C', 'D', 'E', 'J', 'B', 'G', 'I', 'F', 'H']
    
    print("\n📊 FAILING LETTERS ACROSS SHARD:")
    for letter in priority_letters:
        counties = failing_by_letter.get(letter, [])
        if counties:
            count = len(counties)
            print(f"**{letter}**: {', '.join(counties)} ({count}/5 counties)")
    
    print(f"\n" + "="*60)
    print("SHARD-10 PRIORITY ANALYSIS")
    print("="*60)
    
    print("\n🎯 **Immediate High-Impact Priorities:**")
    
    print("\n**1. LETTER A - Franklin/Union (2 counties, foundational blocker)**")
    print("   - Status: 0/0 auctions ingested")
    print("   - Action: Run ingest_county.py for co_no=29 (franklin) and co_no=73 (union)")
    print("   - Impact: Enables all other letters for these counties")
    print("   - Command: `python scripts/ingest_county.py --county 29 --full`")
    print("   - Command: `python scripts/ingest_county.py --county 73 --full`")
    
    print("\n**2. LETTER E - Parcel Linkage (Bay 81.3% close to passing)**")
    print("   - Bay: 2396/2947 linked (need 99 more for 85%+ pass)")
    print("   - Okeechobee: 385/450 linked (need 43 more)")  
    print("   - Leon: 138/2053 linked (major gap)")
    print("   - Action: County GIS parcel_id mapping via ArcGIS endpoints")
    
    print("\n**3. LETTER J - Deal Pipeline (Fleet-wide blocker, 5/5 counties fail)**")
    print("   - Status: 0.0% across all counties")
    print("   - Action: Build bid_decisions generator with Shapira Formula")
    print("   - Impact: Most points available (5 counties × 1 letter = 5 points)")
    
    print("\n**4. LETTER C/D - Parity Matching (3 counties with data)**")
    print("   - Leon C: 12.7% (261/2053), D: 51.0% (1047/2053)")
    print("   - Bay C: 15.6% (460/2947), D: 60.1% (1772/2947)")  
    print("   - Okeechobee C: 17.3% (78/450), D: 74.2% (334/450)")
    print("   - Action: PropertyOnion vs clerk records supplementary litmus")
    
    print("\n**5. LETTER B - Verified Outcomes (5/5 counties fail)**")
    print("   - Status: All verified=0 (no independent data sources)")
    print("   - Action: Build clerk outcome verification pipelines")
    
    print(f"\n" + "="*60)
    print("EXECUTION SEQUENCE")
    print("="*60)
    
    print("\n📝 **Phase 1 - Foundation (30 min)**")
    print("1. Ingest Franklin county data: `python scripts/ingest_county.py --county 29 --full`")
    print("2. Ingest Union county data: `python scripts/ingest_county.py --county 73 --full`") 
    print("3. Verify A letter improvement via pencil_dod_evaluate_county")
    
    print("\n📝 **Phase 2 - High-Impact Fixes (3-4 hours)**")
    print("1. **Bay E Linkage** - 99 parcel links to reach pass threshold")
    print("2. **J Generator** - Build bid_decisions pipeline (all 5 counties)")
    print("3. **C/D Parity** - Supplementary litmus for PropertyOnion gaps")
    
    print("\n📝 **Phase 3 - Infrastructure (1-2 hours)**")
    print("1. **B Outcomes** - Clerk verification for counties with closed sales")
    print("2. **Leon E Linkage** - County GIS integration")
    print("3. **Verification Protocol** - SQL proof for all changes")
    
    print("\n📝 **Success Metrics:**")
    print("- Franklin: 0→5+ letters (A foundation unlocks others)")
    print("- Union: 0→5+ letters (A foundation unlocks others)")
    print("- Bay: 1→4+ letters (E parcel linkage + J + C/D)")
    print("- Leon: 2→5+ letters (E major improvement + J + C/D)")
    print("- Okeechobee: 1→4+ letters (E improvement + J + C/D)")
    print("- Target: +15-20 total letter improvements")

if __name__ == "__main__":
    main()