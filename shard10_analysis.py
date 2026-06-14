#!/usr/bin/env python3
"""
SHARD-10 Analysis from briefing data
Process manatee, collier, okeechobee, franklin, union
"""
import os

def main():
    print("🔍 SHARD-10 Analysis from Issue Briefing")
    print("="*60)
    
    # Data from the issue briefing
    briefing_data = {
        'manatee': {
            'score': 2,
            'metrics': {
                'A': {'grade': 'PASS', 'metric': 1487, 'details': 'fc=3017 td=1487'},
                'B': {'grade': 'FAIL', 'metric': None, 'details': 'verified=0 closed_sold=1350'},
                'C': {'grade': 'FAIL', 'metric': 20.0, 'details': 'matched_clean=902 of 4504'},
                'D': {'grade': 'FAIL', 'metric': 48.8, 'details': 'matched_any=2199 of 4504'},
                'E': {'grade': 'FAIL', 'metric': 87.9, 'details': 'parcel_linked=3961 of 4504'},
                'F': {'grade': 'FAIL', 'metric': 8.8, 'details': 'tier1_sold=119 closed_sold=1350'},
                'G': {'grade': 'FAIL', 'metric': None, 'details': 'density= far= pk1000='},
                'H': {'grade': 'PASS', 'metric': 13.5, 'details': 'hours since last_seen (SLA 48h)'},
                'I': {'grade': 'FAIL', 'metric': None, 'details': 'zoned_complete_parcels=0 field_complete_parcels=696 auctions=4504'},
                'J': {'grade': 'FAIL', 'metric': 0.0, 'details': 'deal_complete=0 of 4504'}
            }
        },
        'collier': {
            'score': 1,
            'metrics': {
                'A': {'grade': 'PASS', 'metric': 559, 'details': 'fc=1111 td=559'},
                'B': {'grade': 'FAIL', 'metric': None, 'details': 'verified=0 closed_sold=610'},
                'C': {'grade': 'FAIL', 'metric': 17.3, 'details': 'matched_clean=289 of 1670'},
                'D': {'grade': 'FAIL', 'metric': 59.2, 'details': 'matched_any=988 of 1670'},
                'E': {'grade': 'FAIL', 'metric': 64.8, 'details': 'parcel_linked=1082 of 1670'},
                'F': {'grade': 'FAIL', 'metric': 0.0, 'details': 'tier1_sold=0 closed_sold=610'},
                'G': {'grade': 'FAIL', 'metric': None, 'details': 'density= far= pk1000='},
                'H': {'grade': 'FAIL', 'metric': 574.4, 'details': 'hours since last_seen (SLA 48h)'},
                'I': {'grade': 'FAIL', 'metric': None, 'details': 'zoned_complete_parcels=0 field_complete_parcels=224 auctions=1670'},
                'J': {'grade': 'FAIL', 'metric': 0.0, 'details': 'deal_complete=0 of 1670'}
            }
        },
        'okeechobee': {
            'score': 1,
            'metrics': {
                'A': {'grade': 'PASS', 'metric': 164, 'details': 'fc=164 td=286'},
                'B': {'grade': 'FAIL', 'metric': None, 'details': 'verified=0 closed_sold=162'},
                'C': {'grade': 'FAIL', 'metric': 17.3, 'details': 'matched_clean=78 of 450'},
                'D': {'grade': 'FAIL', 'metric': 74.2, 'details': 'matched_any=334 of 450'},
                'E': {'grade': 'FAIL', 'metric': 85.6, 'details': 'parcel_linked=385 of 450'},
                'F': {'grade': 'FAIL', 'metric': 0.0, 'details': 'tier1_sold=0 closed_sold=162'},
                'G': {'grade': 'FAIL', 'metric': None, 'details': 'density= far= pk1000='},
                'H': {'grade': 'FAIL', 'metric': 397.0, 'details': 'hours since last_seen (SLA 48h)'},
                'I': {'grade': 'FAIL', 'metric': None, 'details': 'zoned_complete_parcels=0 field_complete_parcels=136 auctions=450'},
                'J': {'grade': 'FAIL', 'metric': 0.0, 'details': 'deal_complete=0 of 450'}
            }
        },
        'franklin': {
            'score': 0,
            'metrics': {
                'A': {'grade': 'FAIL', 'metric': 0, 'details': 'fc=0 td=0'},
                'B': {'grade': 'FAIL', 'metric': None, 'details': 'verified=0 closed_sold=0'},
                'C': {'grade': 'FAIL', 'metric': None, 'details': 'matched_clean=0 of 0'},
                'D': {'grade': 'FAIL', 'metric': None, 'details': 'matched_any=0 of 0'},
                'E': {'grade': 'FAIL', 'metric': None, 'details': 'parcel_linked=0 of 0'},
                'F': {'grade': 'FAIL', 'metric': None, 'details': 'tier1_sold=0 closed_sold=0'},
                'G': {'grade': 'FAIL', 'metric': None, 'details': 'density= far= pk1000='},
                'H': {'grade': 'FAIL', 'metric': None, 'details': 'hours since last_seen (SLA 48h)'},
                'I': {'grade': 'FAIL', 'metric': None, 'details': 'zoned_complete_parcels=0 field_complete_parcels=0 auctions=0'},
                'J': {'grade': 'FAIL', 'metric': None, 'details': 'deal_complete=0 of 0'}
            }
        },
        'union': {
            'score': 0,
            'metrics': {
                'A': {'grade': 'FAIL', 'metric': 0, 'details': 'fc=0 td=0'},
                'B': {'grade': 'FAIL', 'metric': None, 'details': 'verified=0 closed_sold=0'},
                'C': {'grade': 'FAIL', 'metric': None, 'details': 'matched_clean=0 of 0'},
                'D': {'grade': 'FAIL', 'metric': None, 'details': 'matched_any=0 of 0'},
                'E': {'grade': 'FAIL', 'metric': None, 'details': 'parcel_linked=0 of 0'},
                'F': {'grade': 'FAIL', 'metric': None, 'details': 'tier1_sold=0 closed_sold=0'},
                'G': {'grade': 'FAIL', 'metric': None, 'details': 'density= far= pk1000='},
                'H': {'grade': 'FAIL', 'metric': None, 'details': 'hours since last_seen (SLA 48h)'},
                'I': {'grade': 'FAIL', 'metric': None, 'details': 'zoned_complete_parcels=0 field_complete_parcels=0 auctions=0'},
                'J': {'grade': 'FAIL', 'metric': None, 'details': 'deal_complete=0 of 0'}
            }
        }
    }
    
    print("📊 COUNTY SUMMARY:")
    for county, data in briefing_data.items():
        score = data['score']
        passing = [letter for letter, info in data['metrics'].items() if info['grade'] == 'PASS']
        failing = [letter for letter, info in data['metrics'].items() if info['grade'] == 'FAIL']
        print(f"**{county}**: {score}/10 - Passing: {', '.join(passing) if passing else 'None'} | Failing: {', '.join(failing)}")
    
    # Analyze failing letters across counties
    failing_by_letter = {}
    for county, data in briefing_data.items():
        for letter, info in data['metrics'].items():
            if info['grade'] == 'FAIL':
                if letter not in failing_by_letter:
                    failing_by_letter[letter] = []
                failing_by_letter[letter].append(county)
    
    # Priority order from CRITERION-PARALLEL briefing
    priority_letters = ['C', 'D', 'J', 'B', 'G', 'I', 'E', 'F', 'A', 'H']
    
    print("\n" + "="*60)
    print("CRITERION-PARALLEL ANALYSIS")
    print("="*60)
    
    print("\n📊 FAILING LETTERS ACROSS SHARD-10:")
    for letter in priority_letters:
        counties = failing_by_letter.get(letter, [])
        if counties:
            print(f"**{letter}**: {', '.join(counties)} ({len(counties)} counties)")
    
    print("\n" + "="*60)
    print("PRIORITY ANALYSIS & ACTION PLAN")
    print("="*60)
    
    print("\n🎯 **Critical Blockers (Zero Counties Pass):**")
    zero_pass_letters = [letter for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J'] 
                        if all(briefing_data[county]['metrics'][letter]['grade'] == 'FAIL' 
                              for county in briefing_data.keys())]
    
    for letter in zero_pass_letters:
        counties = failing_by_letter.get(letter, [])
        print(f"**{letter}**: {len(counties)}/5 counties fail - FLEET-WIDE FIX NEEDED")
    
    print("\n🔍 **Specific County Issues:**")
    print("**FRANKLIN & UNION** (0/10 score):")
    print("  - A-lane complete failure: fc=0, td=0")
    print("  - No auction data ingested at all")
    print("  - Priority: Basic pipeline setup required")
    
    print("\n**MANATEE** (2/10 score, best performer):")
    print("  - Good A (1487 auctions), H freshness")
    print("  - C/D parity issues (20%/49% vs 95% target)")
    print("  - E linkage at 88% (close to 95% threshold)")
    print("  - F tier1 very low (8.8%)")
    print("  - B/G/I/J all fail")
    
    print("\n**COLLIER & OKEECHOBEE** (1/10 score each):")
    print("  - Only A passes")
    print("  - H freshness issues (574h, 397h vs 48h SLA)")
    print("  - Similar pattern to manatee but worse metrics")
    
    print("\n" + "="*60)
    print("RECOMMENDED SESSION EXECUTION ORDER")
    print("="*60)
    
    print("\n**Phase 1: FRANKLIN/UNION A-LANE SETUP (High Impact)**")
    print("1. Check pipeline.counties configuration")
    print("2. Configure dual-lane scraping (realauction + clerk)")
    print("3. Trigger initial ingestion")
    print("4. Verify A metric moves from 0 to >0")
    
    print("\n**Phase 2: FLEET-WIDE J GENERATOR (Highest Leverage)**")
    print("1. Build bid_decisions pipeline (Shapira Formula)")
    print("2. Implement arv + max_bid + ml_score + factors")
    print("3. Connect to existing CMA pipeline")
    print("4. All 5 counties benefit immediately")
    
    print("\n**Phase 3: C/D PARITY FIXES (Known Pattern)**")
    print("1. Analyze PropertyOnion vs clerk coverage gap")
    print("2. Implement official records supplementary source")
    print("3. Focus on manatee first (best baseline)")
    
    print("\n**Phase 4: B VERIFICATION (Infrastructure)**")
    print("1. Build independent verified outcomes")
    print("2. Connect to clerk/court records")
    print("3. Fleet-wide impact once built")
    
    print("\n📝 **Success Metrics:**")
    print("- **Franklin/Union**: A metric >0 (currently 0)")
    print("- **All counties**: J metric >0 (currently 0)")
    print("- **Manatee priority**: 2/10 → 4+/10")
    print("- **SQL verification**: pencil_dod_evaluate_county proof required")
    print("- **Ship-to-main**: All commits direct to main branch")

if __name__ == "__main__":
    main()