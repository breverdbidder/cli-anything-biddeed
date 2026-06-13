#!/usr/bin/env python3
"""
SHARD-1 Gold Standard Analysis
Counties: charlotte, palm_beach, hendry, st_johns, hardee
Session: 6-hour autonomous campaign
"""

# Data from the issue briefing (loop run 23)
briefing_data = {
    'charlotte': {
        'score': 3,
        'pass_letters': ['A', 'D', 'H'], 
        'metrics': {
            'A': {'status': 'PASS', 'metric': 249, 'details': '[fc=249 td=7857]'},
            'B': {'status': 'FAIL', 'metric': None, 'details': '[verified=0 closed_sold=945]'},
            'C': {'status': 'FAIL', 'metric': 10.1, 'details': '[matched_clean=821 of 8106]'},
            'D': {'status': 'PASS', 'metric': 97.4, 'details': '[matched_any=7899 of 8106]'},
            'E': {'status': 'FAIL', 'metric': 43.8, 'details': '[parcel_linked=3547 of 8106]'},
            'F': {'status': 'FAIL', 'metric': 2.1, 'details': '[tier1_sold=20 closed_sold=945]'},
            'G': {'status': 'FAIL', 'metric': None, 'details': '[density= far= pk1000=]'},
            'H': {'status': 'PASS', 'metric': 44.0, 'details': '[hours since last_seen (SLA 48h)]'},
            'I': {'status': 'FAIL', 'metric': None, 'details': '[zoned_complete_parcels=0 field_complete_parcels=1423 auctions=8106]'},
            'J': {'status': 'FAIL', 'metric': 0.0, 'details': '[deal_complete=0 of 8106 (triangle + two-arm CMA + ml_score + max_bid)]'}
        }
    },
    'palm_beach': {
        'score': 2,
        'pass_letters': ['A', 'H'],
        'metrics': {
            'A': {'status': 'PASS', 'metric': 8591, 'details': '[fc=15409 td=8591]'},
            'B': {'status': 'FAIL', 'metric': None, 'details': '[verified=0 closed_sold=9041]'},
            'C': {'status': 'FAIL', 'metric': 19.2, 'details': '[matched_clean=4609 of 24000]'},
            'D': {'status': 'FAIL', 'metric': 46.4, 'details': '[matched_any=11144 of 24000]'},
            'E': {'status': 'FAIL', 'metric': 80.3, 'details': '[parcel_linked=19270 of 24000]'},
            'F': {'status': 'FAIL', 'metric': 1.9, 'details': '[tier1_sold=176 closed_sold=9041]'},
            'G': {'status': 'FAIL', 'metric': None, 'details': '[density= far= pk1000=]'},
            'H': {'status': 'PASS', 'metric': 7.3, 'details': '[hours since last_seen (SLA 48h)]'},
            'I': {'status': 'FAIL', 'metric': None, 'details': '[zoned_complete_parcels=0 field_complete_parcels=2894 auctions=24000]'},
            'J': {'status': 'FAIL', 'metric': 0.0, 'details': '[deal_complete=0 of 24000 (triangle + two-arm CMA + ml_score + max_bid)]'}
        }
    },
    'hendry': {
        'score': 1,
        'pass_letters': ['D'],
        'metrics': {
            'A': {'status': 'FAIL', 'metric': 0, 'details': '[fc=0 td=62]'},
            'B': {'status': 'FAIL', 'metric': None, 'details': '[verified=0 closed_sold=9]'},
            'C': {'status': 'FAIL', 'metric': 14.5, 'details': '[matched_clean=9 of 62]'},
            'D': {'status': 'PASS', 'metric': 100.0, 'details': '[matched_any=62 of 62]'},
            'E': {'status': 'FAIL', 'metric': 0.0, 'details': '[parcel_linked=0 of 62]'},
            'F': {'status': 'FAIL', 'metric': 0.0, 'details': '[tier1_sold=0 closed_sold=9]'},
            'G': {'status': 'FAIL', 'metric': None, 'details': '[density= far= pk1000=]'},
            'H': {'status': 'FAIL', 'metric': 733.1, 'details': '[hours since last_seen (SLA 48h)]'},
            'I': {'status': 'FAIL', 'metric': None, 'details': '[zoned_complete_parcels=0 field_complete_parcels=0 auctions=62]'},
            'J': {'status': 'FAIL', 'metric': 0.0, 'details': '[deal_complete=0 of 62 (triangle + two-arm CMA + ml_score + max_bid)]'}
        }
    },
    'st_johns': {
        'score': 1,
        'pass_letters': ['A'],
        'metrics': {
            'A': {'status': 'PASS', 'metric': 558, 'details': '[fc=1059 td=558]'},
            'B': {'status': 'FAIL', 'metric': None, 'details': '[verified=0 closed_sold=614]'},
            'C': {'status': 'FAIL', 'metric': 27.8, 'details': '[matched_clean=449 of 1617]'},
            'D': {'status': 'FAIL', 'metric': 60.3, 'details': '[matched_any=975 of 1617]'},
            'E': {'status': 'FAIL', 'metric': 87.1, 'details': '[parcel_linked=1408 of 1617]'},
            'F': {'status': 'FAIL', 'metric': 5.2, 'details': '[tier1_sold=32 closed_sold=614]'},
            'G': {'status': 'FAIL', 'metric': None, 'details': '[density= far= pk1000=]'},
            'H': {'status': 'FAIL', 'metric': 65.7, 'details': '[hours since last_seen (SLA 48h)]'},
            'I': {'status': 'FAIL', 'metric': None, 'details': '[zoned_complete_parcels=0 field_complete_parcels=409 auctions=1617]'},
            'J': {'status': 'FAIL', 'metric': 0.0, 'details': '[deal_complete=0 of 1617 (triangle + two-arm CMA + ml_score + max_bid)]'}
        }
    },
    'hardee': {
        'score': 0,
        'pass_letters': [],
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
            'J': {'status': 'FAIL', 'metric': None, 'details': '[deal_complete=0 of 0 (triangle + two-arm CMA + ml_score + max_bid)]'}
        }
    }
}

def analyze_shard():
    print("=" * 80)
    print("SHARD-1 GOLD STANDARD CAMPAIGN ANALYSIS")
    print("=" * 80)
    
    # Overall shard statistics
    total_pass = sum(county['score'] for county in briefing_data.values())
    total_possible = len(briefing_data) * 10
    shard_completion = (total_pass / total_possible) * 100
    
    print(f"\n📊 SHARD-1 OVERALL STATUS:")
    print(f"   Total passes: {total_pass}/{total_possible} ({shard_completion:.1f}%)")
    print(f"   Counties: {len(briefing_data)}")
    print(f"   Best performer: charlotte (3/10)")
    print(f"   Worst performer: hardee (0/10)")
    
    # Analyze failing letters across counties
    failing_by_letter = {}
    for county, data in briefing_data.items():
        for letter, info in data['metrics'].items():
            if info['status'] == 'FAIL':
                if letter not in failing_by_letter:
                    failing_by_letter[letter] = []
                failing_by_letter[letter].append(county)
    
    # Find highest-leverage targets (most counties failing per letter)
    print(f"\n🎯 HIGHEST-LEVERAGE FAILING LETTERS:")
    for letter in sorted(failing_by_letter.keys()):
        counties = failing_by_letter[letter]
        county_count = len(counties)
        leverage_score = county_count * 2  # 2 points per county fixed
        print(f"   {letter}: {county_count} counties failing (leverage: +{leverage_score} points)")
        print(f"      Counties: {', '.join(counties)}")
    
    print(f"\n📈 CRITERION-PARALLEL ANALYSIS:")
    print(f"   Based on briefing metrics and CLAUDE.md guidance:")
    
    # Critical three analysis (B, I, J from briefing)
    print(f"\n   🔥 CRITICAL THREE (B, I, J):")
    print(f"   ├─ B (verified outcomes): 5/5 counties fail - independent verification missing")
    print(f"   ├─ I (property cards): 5/5 counties fail - requires E (parcel linkage) first")
    print(f"   └─ J (deal completion): 5/5 counties fail - bid_decisions pipeline missing")
    
    # High-leverage non-critical
    print(f"\n   ⚡ HIGH-LEVERAGE NON-CRITICAL:")
    print(f"   ├─ G (zoning): 5/5 counties fail - v_zoning_gold_standard_kpi_v3 empty")
    print(f"   ├─ F (tier1 sales): 5/5 counties fail - dependent on B fixes")
    print(f"   └─ E (parcel linkage): 5/5 counties fail - ArcGIS FeatureServer needed")
    
    # Medium priority
    print(f"\n   🔧 MEDIUM PRIORITY (PARITY):")
    print(f"   ├─ C (parity_clean): 4/5 counties fail - matching engine issues")
    print(f"   └─ D (parity_any): 3/5 counties fail - PropertyOnion vs official records")
    
    print(f"\n💼 SESSION STRATEGY (6-hour budget):")
    
    # Priority order based on briefing guidance and leverage
    priorities = [
        ("1. J GENERATOR", "Fleet-wide bid_decisions pipeline - highest single fix (+10 points)"),
        ("2. B VERIFICATION", "Independent outcome verification - enables F automatically"),
        ("3. E LINKAGE", "Parcel ID linkage via county GIS - enables I and improves C/D"),
        ("4. G ZONING", "ZoneWise zoning data ingestion per county"),
        ("5. C/D PARITY", "PropertyOnion reconciliation - clerk/official records fallback"),
    ]
    
    for priority in priorities:
        print(f"   {priority[0]}: {priority[1]}")
    
    # County-specific notes
    print(f"\n🏃 COUNTY-SPECIFIC PRIORITIES:")
    county_priorities = {
        'hardee': "Complete failure - start with A (dual-product coverage)",
        'hendry': "Almost no data - focus on A (coverage) and H (freshness)",
        'st_johns': "Best E score (87.1%) - complete parcel linkage first", 
        'palm_beach': "Large dataset (24K auctions) - highest impact county",
        'charlotte': "Best overall (3/10) - good test case for fixes"
    }
    
    for county, priority in county_priorities.items():
        score = briefing_data[county]['score']
        print(f"   {county} ({score}/10): {priority}")

def generate_execution_plan():
    print(f"\n" + "=" * 80)
    print("EXECUTION PLAN - CRITERION-PARALLEL APPROACH")
    print("=" * 80)
    
    execution_phases = [
        {
            'name': 'PHASE 1: J GENERATOR (90 mins)',
            'targets': ['J'],
            'scope': 'Fleet-wide pipeline',
            'deliverables': [
                'Build bid_decisions generator per evaluator contract',
                'Implement arv + max_bid + ml_score + 5 factor keys',
                'Wire to Shapira V14 model and gen_valuations_comps_batch',
                'Run initial batch fill for all 5 counties',
                'Verify J metrics move from 0.0 to >95%'
            ],
            'impact': '+5 counties × 2 = +10 points'
        },
        {
            'name': 'PHASE 2: B VERIFICATION (75 mins)',
            'targets': ['B', 'F'],
            'scope': 'Independent outcome verification',
            'deliverables': [
                'Port Duval Acclaim recording pipeline (probe_acclaim_doctype_search)',
                'Parameterize for other counties (county-agnostic)',
                'Build verified outcomes with data_source=independent',
                'Enable automatic tier1 promotion (F follows B)',
                'Target: B null→95%, F low→95%'
            ],
            'impact': '+5 counties × 4 = +20 points'
        },
        {
            'name': 'PHASE 3: E LINKAGE (90 mins)',
            'targets': ['E', 'I'],
            'scope': 'Parcel ID linkage via ArcGIS',
            'deliverables': [
                'Implement county property appraiser ArcGIS FeatureServer queries',
                'Use Brevard/BCPAO pipeline as reference',
                'Link multi_county_auctions.parcel_id for all 5 counties',
                'Enables I (property cards) automatically',
                'Target: E→95%, I improves'
            ],
            'impact': '+5 counties × 4 = +20 points'
        },
        {
            'name': 'PHASE 4: G ZONING (90 mins)',
            'targets': ['G'],
            'scope': 'ZoneWise zoning data ingestion',
            'deliverables': [
                'Extend zoning ingestion to cover all 5 counties',
                'Populate v_zoning_gold_standard_kpi_v3 views',
                'Focus on density/FAR/pk1000 coverage per district',
                'Use ordinance text with honesty markers',
                'Target: G null→95%'
            ],
            'impact': '+5 counties × 2 = +10 points'
        },
        {
            'name': 'PHASE 5: VERIFICATION & CLEANUP (30 mins)',
            'targets': ['ALL'],
            'scope': 'Session closure',
            'deliverables': [
                'Run pencil_dod_evaluate_county for all 5 counties',
                'Document actual vs planned metrics movement',
                'Apply final migrations to live Supabase',
                'Execute gold_standard_loop() and certify',
                'Commit all changes to main (ship-to-main mandate)'
            ],
            'impact': 'Session validation'
        }
    ]
    
    total_time = 0
    total_impact = 0
    
    for phase in execution_phases:
        print(f"\n{phase['name']}")
        print(f"   Targets: {', '.join(phase['targets'])}")
        print(f"   Scope: {phase['scope']}")
        print(f"   Impact: {phase.get('impact', 'N/A')}")
        print(f"   Deliverables:")
        for deliverable in phase['deliverables']:
            print(f"     • {deliverable}")
        
        # Extract time estimate
        if 'mins' in phase['name']:
            time_str = phase['name'].split('(')[1].split(' mins')[0]
            total_time += int(time_str)
    
    print(f"\n📊 EXECUTION SUMMARY:")
    print(f"   Total estimated time: {total_time} minutes ({total_time/60:.1f} hours)")
    print(f"   Budget available: 6 hours (360 minutes)")
    print(f"   Buffer time: {360 - total_time} minutes")
    print(f"   Expected impact: ~60 points (from 7/50 to 67/50 if successful)")
    
    print(f"\n🎯 SUCCESS CRITERIA:")
    print(f"   • All fixes wired to executors (not dead code)")
    print(f"   • Live SQL verification for each metric movement")
    print(f"   • Ship directly to main branch per mandate")
    print(f"   • HONESTY PROTOCOL: VERIFIED tags with query evidence")

if __name__ == "__main__":
    analyze_shard()
    generate_execution_plan()