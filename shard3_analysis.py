#!/usr/bin/env python3
"""
SHARD-3 Gold Standard Analysis
Counties: broward, washington, lake, st_lucie, jefferson
Loop run: 31
"""

# Current status from issue briefing (run 31)
briefing_data = {
    'broward': {
        'score': 2,
        'metrics': {
            'A': {'grade': 'PASS', 'metric': 10308, 'detail': 'fc=19804 td=10308'},
            'B': {'grade': 'FAIL', 'metric': None, 'detail': 'verified=0 closed_sold=12198'}, 
            'C': {'grade': 'FAIL', 'metric': 19.4, 'detail': 'matched_clean=5836 of 30112'},
            'D': {'grade': 'FAIL', 'metric': 47.7, 'detail': 'matched_any=14364 of 30112'},
            'E': {'grade': 'FAIL', 'metric': 20.6, 'detail': 'parcel_linked=6208 of 30112'},
            'F': {'grade': 'FAIL', 'metric': 2.5, 'detail': 'tier1_sold=300 closed_sold=12198'},
            'G': {'grade': 'FAIL', 'metric': None, 'detail': 'density= far= pk1000='},
            'H': {'grade': 'PASS', 'metric': 10.5, 'detail': 'hours since last_seen (SLA 48h)'},
            'I': {'grade': 'FAIL', 'metric': None, 'detail': 'zoned_complete_parcels=0 field_complete_parcels=737 auctions=30112'},
            'J': {'grade': 'FAIL', 'metric': 0.0, 'detail': 'deal_complete=0 of 30112 (triangle + two-arm CMA + ml_score + max_bid)'}
        }
    },
    'washington': {
        'score': 2,
        'metrics': {
            'A': {'grade': 'PASS', 'metric': 30, 'detail': 'fc=30 td=272'},
            'B': {'grade': 'FAIL', 'metric': None, 'detail': 'verified=0 closed_sold=102'},
            'C': {'grade': 'FAIL', 'metric': 45.4, 'detail': 'matched_clean=137 of 302'},
            'D': {'grade': 'FAIL', 'metric': 84.8, 'detail': 'matched_any=256 of 302'},
            'E': {'grade': 'FAIL', 'metric': 24.8, 'detail': 'parcel_linked=75 of 302'},
            'F': {'grade': 'FAIL', 'metric': 18.6, 'detail': 'tier1_sold=19 closed_sold=102'},
            'G': {'grade': 'FAIL', 'metric': None, 'detail': 'density= far= pk1000='},
            'H': {'grade': 'PASS', 'metric': 7.4, 'detail': 'hours since last_seen (SLA 48h)'},
            'I': {'grade': 'FAIL', 'metric': None, 'detail': 'zoned_complete_parcels=0 field_complete_parcels=14 auctions=302'},
            'J': {'grade': 'FAIL', 'metric': 0.0, 'detail': 'deal_complete=0 of 302 (triangle + two-arm CMA + ml_score + max_bid)'}
        }
    },
    'lake': {
        'score': 1,
        'metrics': {
            'A': {'grade': 'PASS', 'metric': 1113, 'detail': 'fc=1950 td=1113'},
            'B': {'grade': 'FAIL', 'metric': None, 'detail': 'verified=0 closed_sold=823'},
            'C': {'grade': 'FAIL', 'metric': 17.3, 'detail': 'matched_clean=529 of 3063'},
            'D': {'grade': 'FAIL', 'metric': 54.0, 'detail': 'matched_any=1654 of 3063'},
            'E': {'grade': 'FAIL', 'metric': 74.4, 'detail': 'parcel_linked=2279 of 3063'},
            'F': {'grade': 'FAIL', 'metric': 0.0, 'detail': 'tier1_sold=0 closed_sold=823'},
            'G': {'grade': 'FAIL', 'metric': None, 'detail': 'density= far= pk1000='},
            'H': {'grade': 'FAIL', 'metric': 439.0, 'detail': 'hours since last_seen (SLA 48h)'},
            'I': {'grade': 'FAIL', 'metric': None, 'detail': 'zoned_complete_parcels=0 field_complete_parcels=438 auctions=3063'},
            'J': {'grade': 'FAIL', 'metric': 0.0, 'detail': 'deal_complete=0 of 3063 (triangle + two-arm CMA + ml_score + max_bid)'}
        }
    },
    'st_lucie': {
        'score': 1,
        'metrics': {
            'A': {'grade': 'PASS', 'metric': 213, 'detail': 'fc=213 td=2373'},
            'B': {'grade': 'FAIL', 'metric': None, 'detail': 'verified=0 closed_sold=608'},
            'C': {'grade': 'FAIL', 'metric': 19.8, 'detail': 'matched_clean=512 of 2586'},
            'D': {'grade': 'FAIL', 'metric': 93.8, 'detail': 'matched_any=2426 of 2586'},
            'E': {'grade': 'FAIL', 'metric': 51.1, 'detail': 'parcel_linked=1321 of 2586'},
            'F': {'grade': 'FAIL', 'metric': 0.3, 'detail': 'tier1_sold=2 closed_sold=608'},
            'G': {'grade': 'FAIL', 'metric': None, 'detail': 'density= far= pk1000='},
            'H': {'grade': 'FAIL', 'metric': 136.7, 'detail': 'hours since last_seen (SLA 48h)'},
            'I': {'grade': 'FAIL', 'metric': None, 'detail': 'zoned_complete_parcels=0 field_complete_parcels=519 auctions=2586'},
            'J': {'grade': 'FAIL', 'metric': 0.0, 'detail': 'deal_complete=0 of 2586 (triangle + two-arm CMA + ml_score + max_bid)'}
        }
    },
    'jefferson': {
        'score': 0,
        'metrics': {
            'A': {'grade': 'FAIL', 'metric': 0, 'detail': 'fc=0 td=0'},
            'B': {'grade': 'FAIL', 'metric': None, 'detail': 'verified=0 closed_sold=0'},
            'C': {'grade': 'FAIL', 'metric': None, 'detail': 'matched_clean=0 of 0'},
            'D': {'grade': 'FAIL', 'metric': None, 'detail': 'matched_any=0 of 0'},
            'E': {'grade': 'FAIL', 'metric': None, 'detail': 'parcel_linked=0 of 0'},
            'F': {'grade': 'FAIL', 'metric': None, 'detail': 'tier1_sold=0 closed_sold=0'},
            'G': {'grade': 'FAIL', 'metric': None, 'detail': 'density= far= pk1000='},
            'H': {'grade': 'FAIL', 'metric': None, 'detail': 'hours since last_seen (SLA 48h)'},
            'I': {'grade': 'FAIL', 'metric': None, 'detail': 'zoned_complete_parcels=0 field_complete_parcels=0 auctions=0'},
            'J': {'grade': 'FAIL', 'metric': None, 'detail': 'deal_complete=0 of 0 (triangle + two-arm CMA + ml_score + max_bid)'}
        }
    }
}

def analyze_priority_targets():
    """Analyze which counties and letters offer highest leverage"""
    
    print("="*60)
    print("SHARD-3 PRIORITY ANALYSIS")
    print("="*60)
    
    # Calculate total potential points
    total_current = sum(data['score'] for data in briefing_data.values())
    total_possible = len(briefing_data) * 10  # 5 counties * 10 letters each
    
    print(f"Current total: {total_current}/{total_possible} ({total_current/total_possible*100:.1f}%)")
    
    # Analyze by county
    print("\nCOUNTY BREAKDOWN:")
    for county, data in briefing_data.items():
        score = data['score']
        gap = 10 - score
        print(f"{county:12} {score:2}/10  (gap: {gap:2}) - {'HIGH' if gap >= 8 else 'MED' if gap >= 5 else 'LOW'} leverage")
    
    # Letter analysis across all counties
    print("\nLETTER FREQUENCY ANALYSIS:")
    letter_fails = {}
    letter_impact = {}
    
    for letter in 'ABCDEFGHIJ':
        fails = 0
        total_affected = 0
        
        for county, data in briefing_data.items():
            if data['metrics'][letter]['grade'] == 'FAIL':
                fails += 1
                # Count auctions affected (for impact calculation)
                detail = data['metrics'][letter]['detail']
                if 'auctions=' in detail:
                    auction_count = int(detail.split('auctions=')[1].split()[0])
                    total_affected += auction_count
                elif county != 'jefferson':  # Jefferson has 0 everything
                    # Estimate from other metrics for counties without direct auction count
                    if 'of' in detail:
                        try:
                            total_auctions = int(detail.split(' of ')[1].split()[0])
                            total_affected += total_auctions
                        except:
                            pass
        
        letter_fails[letter] = fails
        letter_impact[letter] = total_affected
    
    # Sort by number of failing counties (frequency)
    sorted_by_frequency = sorted(letter_fails.items(), key=lambda x: x[1], reverse=True)
    
    print("By failure frequency:")
    for letter, fail_count in sorted_by_frequency:
        print(f"  Letter {letter}: {fail_count}/5 counties failing (affects ~{letter_impact[letter]:,} auctions)")
    
    # Specific recommendations based on the CLAUDE.md directives
    print("\nPRIORITY RECOMMENDATIONS (based on CLAUDE.md directives):")
    
    print("\n1. JEFFERSON (0/10) - Complete Bootstrap:")
    print("   - Letter A: Configure both lanes (foreclosure + tax deed)")
    print("   - Critical path: A pipeline setup → enables all downstream metrics")
    
    print("\n2. HIGHEST IMPACT LETTERS (fleet-wide issues):")
    print("   - Letter B: 0/5 counties (verified outcomes) - CRITICAL")
    print("   - Letter J: 0/5 counties (deal complete) - BUILD GENERATOR")
    print("   - Letter G: 0/5 counties (zoning data) - ZONING LOAD")
    print("   - Letter I: 0/5 counties (property card) - DEPENDS ON E+G")
    
    print("\n3. HIGH-IMPACT E FIXES (parcel linkage enables downstream):")
    print("   - lake: 74.4% → target 95%+ (unlocks ~784 auctions)")
    print("   - st_lucie: 51.1% → target 95%+ (unlocks ~1265 auctions)")
    print("   - broward: 20.6% → target 95%+ (unlocks ~23,904 auctions)")
    
    print("\n4. H FRESHNESS FIXES (quick wins):")
    print("   - lake: 439.0h → target <48h")
    print("   - st_lucie: 136.7h → target <48h")
    
    return {
        'total_current': total_current,
        'total_possible': total_possible,
        'sorted_by_frequency': sorted_by_frequency,
        'letter_impact': letter_impact
    }

def identify_session_targets():
    """Identify specific work items for this 6-hour session"""
    
    print("\n" + "="*60)
    print("6-HOUR SESSION TARGETS")
    print("="*60)
    
    # Based on CLAUDE.md sprint order and CRITERION-PARALLEL PIVOT
    print("SESSION STRATEGY: Fix criteria fleet-wide, not counties serially")
    print("WINDOW: 08:00Z = forensics/parity (C/D diff vs suwannee + E linkage)")
    
    targets = []
    
    # 1. Jefferson bootstrap (highest leverage - enables everything)
    targets.append({
        'county': 'jefferson',
        'letter': 'A', 
        'priority': 'P0-CRITICAL',
        'description': 'Bootstrap Jefferson dual-lane setup (fc + td)',
        'impact': 'Enables all other Jefferson metrics',
        'estimated_time': '60-90 min'
    })
    
    # 2. E linkage fixes (highest impact, enables I+J downstream)
    targets.append({
        'county': 'broward',
        'letter': 'E',
        'priority': 'P0-HIGH',
        'description': 'Fix parcel linkage 20.6% → 95%+ (~23K auctions)',
        'impact': 'Unlocks I+J for broward (largest county)',
        'estimated_time': '90-120 min'
    })
    
    targets.append({
        'county': 'st_lucie', 
        'letter': 'E',
        'priority': 'P1-HIGH',
        'description': 'Fix parcel linkage 51.1% → 95%+ (~1.3K auctions)',
        'impact': 'Unlocks I+J for st_lucie',
        'estimated_time': '45-60 min'
    })
    
    # 3. H freshness fixes (quick wins)
    targets.append({
        'county': 'lake',
        'letter': 'H', 
        'priority': 'P1-QUICK',
        'description': 'Fix freshness 439h → <48h',
        'impact': 'Quick pass, enables lake activity',
        'estimated_time': '30-45 min'
    })
    
    targets.append({
        'county': 'st_lucie',
        'letter': 'H',
        'priority': 'P1-QUICK', 
        'description': 'Fix freshness 136.7h → <48h',
        'impact': 'Quick pass',
        'estimated_time': '30-45 min'
    })
    
    # 4. J generator (fleet-wide, affects all counties)
    targets.append({
        'county': 'ALL',
        'letter': 'J',
        'priority': 'P0-FLEET',
        'description': 'Build bid_decisions generator (Shapira V14)',
        'impact': 'Enables J for all counties with E+parcel data',
        'estimated_time': '90-120 min'
    })
    
    print("PRIORITY TARGETS:")
    for i, target in enumerate(targets, 1):
        print(f"{i}. [{target['priority']}] {target['county']}-{target['letter']}: {target['description']}")
        print(f"   Impact: {target['impact']}")
        print(f"   Time: {target['estimated_time']}")
        print()
    
    # Estimate total time
    time_estimates = [60, 90, 45, 30, 30, 90]  # Conservative estimates in minutes
    total_estimated = sum(time_estimates)
    print(f"TOTAL ESTIMATED TIME: {total_estimated} minutes ({total_estimated/60:.1f} hours)")
    print(f"SESSION BUDGET: 6 hours ({6*60} minutes)")
    print(f"MARGIN: {6*60 - total_estimated} minutes")
    
    return targets

if __name__ == "__main__":
    analysis = analyze_priority_targets()
    targets = identify_session_targets()
    
    print("\n" + "="*60)
    print("ANALYSIS COMPLETE - READY FOR EXECUTION")
    print("="*60)