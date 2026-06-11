#!/usr/bin/env python3
"""
SHARD-8 ANALYSIS: Priority determination based on current metrics
From GitHub Issue #7533 - Gold Standard Campaign
"""

# Current metrics from issue description (loop run 11)
COUNTY_STATUS = {
    'indian_river': {
        'scores': '2/10',
        'letters': {
            'A': {'status': 'PASS', 'metric': 588, 'detail': 'fc=864 td=588'},
            'B': {'status': 'FAIL', 'metric': 'null', 'detail': 'verified=0 closed_sold=608'},
            'C': {'status': 'FAIL', 'metric': 14.7, 'detail': 'matched_clean=214 of 1452'},
            'D': {'status': 'FAIL', 'metric': 52.2, 'detail': 'matched_any=758 of 1452'}, 
            'E': {'status': 'FAIL', 'metric': 81.0, 'detail': 'parcel_linked=1176 of 1452'},
            'F': {'status': 'FAIL', 'metric': 5.1, 'detail': 'tier1_sold=31 closed_sold=608'},
            'G': {'status': 'FAIL', 'metric': 'null', 'detail': 'density= far= pk1000='},
            'H': {'status': 'PASS', 'metric': 40.7, 'detail': 'hours since last_seen (SLA 48h)'},
            'I': {'status': 'FAIL', 'metric': 'null', 'detail': 'zoned_complete_parcels=0 field_complete_parcels=251 auctions=1452'},
            'J': {'status': 'FAIL', 'metric': 0.0, 'detail': 'deal_complete=0 of 1452'}
        }
    },
    'volusia': {
        'scores': '2/10', 
        'letters': {
            'A': {'status': 'PASS', 'metric': 6611, 'detail': 'fc=8966 td=6611'},
            'B': {'status': 'FAIL', 'metric': 'null', 'detail': 'verified=0 closed_sold=5481'},
            'C': {'status': 'FAIL', 'metric': 10.0, 'detail': 'matched_clean=1551 of 15577'},
            'D': {'status': 'FAIL', 'metric': 47.8, 'detail': 'matched_any=7453 of 15577'},
            'E': {'status': 'FAIL', 'metric': 65.8, 'detail': 'parcel_linked=10256 of 15577'},
            'F': {'status': 'FAIL', 'metric': 7.3, 'detail': 'tier1_sold=402 closed_sold=5481'},
            'G': {'status': 'FAIL', 'metric': 'null', 'detail': 'density= far= pk1000='},
            'H': {'status': 'PASS', 'metric': 7.7, 'detail': 'hours since last_seen (SLA 48h)'},
            'I': {'status': 'FAIL', 'metric': 'null', 'detail': 'zoned_complete_parcels=0 field_complete_parcels=1356 auctions=15577'},
            'J': {'status': 'FAIL', 'metric': 0.0, 'detail': 'deal_complete=0 of 15577'}
        }
    },
    'lee': {
        'scores': '1/10',
        'letters': {
            'A': {'status': 'PASS', 'metric': 8353, 'detail': 'fc=8353 td=9348'},
            'B': {'status': 'FAIL', 'metric': 'null', 'detail': 'verified=0 closed_sold=5862'},
            'C': {'status': 'FAIL', 'metric': 11.4, 'detail': 'matched_clean=2010 of 17701'},
            'D': {'status': 'FAIL', 'metric': 58.2, 'detail': 'matched_any=10298 of 17701'},
            'E': {'status': 'FAIL', 'metric': 80.4, 'detail': 'parcel_linked=14229 of 17701'},
            'F': {'status': 'FAIL', 'metric': 0.0, 'detail': 'tier1_sold=0 closed_sold=5862'},
            'G': {'status': 'FAIL', 'metric': 'null', 'detail': 'density= far= pk1000='},
            'H': {'status': 'FAIL', 'metric': 151.9, 'detail': 'hours since last_seen (SLA 48h)'},
            'I': {'status': 'FAIL', 'metric': 'null', 'detail': 'zoned_complete_parcels=0 field_complete_parcels=3167 auctions=17701'},
            'J': {'status': 'FAIL', 'metric': 0.0, 'detail': 'deal_complete=0 of 17701'}
        }
    },
    'desoto': {
        'scores': '0/10',
        'letters': {
            'A': {'status': 'FAIL', 'metric': 0, 'detail': 'fc=0 td=0'},
            'B': {'status': 'FAIL', 'metric': 'null', 'detail': 'verified=0 closed_sold=0'},
            'C': {'status': 'FAIL', 'metric': 'null', 'detail': 'matched_clean=0 of 0'},
            'D': {'status': 'FAIL', 'metric': 'null', 'detail': 'matched_any=0 of 0'},
            'E': {'status': 'FAIL', 'metric': 'null', 'detail': 'parcel_linked=0 of 0'},
            'F': {'status': 'FAIL', 'metric': 'null', 'detail': 'tier1_sold=0 closed_sold=0'},
            'G': {'status': 'FAIL', 'metric': 'null', 'detail': 'density= far= pk1000='},
            'H': {'status': 'FAIL', 'metric': 'null', 'detail': 'hours since last_seen (SLA 48h)'},
            'I': {'status': 'FAIL', 'metric': 'null', 'detail': 'zoned_complete_parcels=0 field_complete_parcels=0 auctions=0'},
            'J': {'status': 'FAIL', 'metric': 'null', 'detail': 'deal_complete=0 of 0'}
        }
    },
    'monroe': {
        'scores': '0/10',
        'letters': {
            'A': {'status': 'FAIL', 'metric': 0, 'detail': 'fc=0 td=0'},
            'B': {'status': 'FAIL', 'metric': 'null', 'detail': 'verified=0 closed_sold=0'},
            'C': {'status': 'FAIL', 'metric': 'null', 'detail': 'matched_clean=0 of 0'},
            'D': {'status': 'FAIL', 'metric': 'null', 'detail': 'matched_any=0 of 0'},
            'E': {'status': 'FAIL', 'metric': 'null', 'detail': 'parcel_linked=0 of 0'},
            'F': {'status': 'FAIL', 'metric': 'null', 'detail': 'tier1_sold=0 closed_sold=0'},
            'G': {'status': 'FAIL', 'metric': 'null', 'detail': 'density= far= pk1000='},
            'H': {'status': 'FAIL', 'metric': 'null', 'detail': 'hours since last_seen (SLA 48h)'},
            'I': {'status': 'FAIL', 'metric': 'null', 'detail': 'zoned_complete_parcels=0 field_complete_parcels=0 auctions=0'},
            'J': {'status': 'FAIL', 'metric': 'null', 'detail': 'deal_complete=0 of 0'}
        }
    }
}

# Canon A-J definitions from issue
CANON_DEFINITIONS = {
    'A': 'dual-product coverage',
    'B': 'verified INDEPENDENT outcomes >=95% of closed', 
    'C': 'parity_clean >=95%',
    'D': 'parity_any >=95%',
    'E': 'parcel linkage >=95%', 
    'F': 'tier1 sold-amount >=95% of closed',
    'G': 'zoning min(density,FAR,pk1000) >=95%',
    'H': 'freshness <=48h',
    'I': 'property card complete >=95% (address+geo+value+zoned parcel)',
    'J': 'Shapira deal thesis >=95% (bid_decisions: arv+max_bid+ml_score+triangle factors+two-arm CMA)'
}

# Critical three from issue
CRITICAL_LETTERS = ['B', 'I', 'J']

def analyze_priority():
    """Analyze current status and determine priority work"""
    
    print("=" * 80)
    print("SHARD-8 PRIORITY ANALYSIS")
    print("=" * 80)
    
    # Overall county rankings by current progress
    county_scores = []
    for county, data in COUNTY_STATUS.items():
        pass_count = sum(1 for letter_data in data['letters'].values() if letter_data['status'] == 'PASS')
        county_scores.append((county, pass_count, data['scores']))
    
    county_scores.sort(key=lambda x: x[1], reverse=True)
    
    print(f"\nCOUNTY RANKINGS (by current pass count):")
    for i, (county, passes, score_str) in enumerate(county_scores, 1):
        print(f"{i}. {county.upper()}: {passes}/10 letters passing ({score_str})")
    
    # Analysis by letter across counties
    print(f"\nLETTER ANALYSIS ACROSS COUNTIES:")
    
    all_letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']
    
    for letter in all_letters:
        is_critical = letter in CRITICAL_LETTERS
        critical_marker = "🔥 CRITICAL" if is_critical else ""
        
        print(f"\nLetter {letter}: {CANON_DEFINITIONS[letter]} {critical_marker}")
        
        passing_counties = []
        failing_counties = []
        
        for county, data in COUNTY_STATUS.items():
            letter_data = data['letters'][letter]
            if letter_data['status'] == 'PASS':
                passing_counties.append(county)
            else:
                failing_counties.append((county, letter_data['metric'], letter_data['detail']))
        
        print(f"  ✅ PASSING: {len(passing_counties)}/5 counties: {', '.join(passing_counties) if passing_counties else 'NONE'}")
        print(f"  ❌ FAILING: {len(failing_counties)}/5 counties")
        
        if failing_counties:
            for county, metric, detail in failing_counties:
                print(f"    - {county}: {metric} ({detail})")
    
    # Determine highest leverage work
    print(f"\n" + "=" * 80)
    print("HIGHEST LEVERAGE OPPORTUNITIES")
    print("=" * 80)
    
    # Priority 1: Counties with data but close to thresholds
    print(f"\n🎯 PRIORITY 1: Counties with existing data near thresholds")
    
    high_leverage = []
    
    # Check each county for near-miss opportunities
    for county, data in COUNTY_STATUS.items():
        opportunities = []
        
        # Check letter E (parcel linkage) - need >=95%
        e_data = data['letters']['E']
        if e_data['status'] == 'FAIL' and isinstance(e_data['metric'], (int, float)) and e_data['metric'] > 60:
            gap_to_95 = 95 - e_data['metric']
            opportunities.append(f"Letter E: {e_data['metric']:.1f}% -> need +{gap_to_95:.1f}% for pass")
        
        # Check letter D (parity_any) - need >=95%  
        d_data = data['letters']['D']
        if d_data['status'] == 'FAIL' and isinstance(d_data['metric'], (int, float)) and d_data['metric'] > 40:
            gap_to_95 = 95 - d_data['metric']
            opportunities.append(f"Letter D: {d_data['metric']:.1f}% -> need +{gap_to_95:.1f}% for pass")
            
        # Check letter C (parity_clean) - need >=95%
        c_data = data['letters']['C'] 
        if c_data['status'] == 'FAIL' and isinstance(c_data['metric'], (int, float)) and c_data['metric'] > 10:
            gap_to_95 = 95 - c_data['metric']
            opportunities.append(f"Letter C: {c_data['metric']:.1f}% -> need +{gap_to_95:.1f}% for pass")
        
        if opportunities:
            high_leverage.append((county, opportunities))
    
    for county, opportunities in high_leverage:
        print(f"\n{county.upper()}:")
        for opp in opportunities:
            print(f"  - {opp}")
    
    # Priority 2: Zero-state counties needing bootstrap
    print(f"\n🔧 PRIORITY 2: Zero-state counties needing full bootstrap")
    
    zero_counties = []
    for county, data in COUNTY_STATUS.items():
        # Check if county has zero auctions (needs full pipeline setup)
        a_data = data['letters']['A']
        if a_data['metric'] == 0:
            zero_counties.append(county)
    
    for county in zero_counties:
        print(f"  - {county.upper()}: No auctions found - needs full scraper setup (Letter A)")
    
    # Priority 3: Critical letters B, I, J analysis
    print(f"\n🔥 PRIORITY 3: Critical letters (B, I, J) - required for gold certification")
    
    for letter in CRITICAL_LETTERS:
        print(f"\nLetter {letter}: {CANON_DEFINITIONS[letter]}")
        
        failing_count = 0
        for county, data in COUNTY_STATUS.items():
            if data['letters'][letter]['status'] == 'FAIL':
                failing_count += 1
        
        print(f"  Status: {5-failing_count}/5 counties passing, {failing_count}/5 failing")
        
        if letter == 'B':
            print(f"  🎯 Root cause: All counties show verified=0 - need INDEPENDENT outcome sources")
            print(f"  📋 Action: Build/extend clerk recording pipelines (AcclaimWeb, court records)")
        elif letter == 'I':
            print(f"  🎯 Root cause: zoned_complete_parcels=0 across counties")
            print(f"  📋 Action: Extend ZoneWise zoning ingestion to target counties")  
        elif letter == 'J':
            print(f"  🎯 Root cause: deal_complete=0 across counties")
            print(f"  📋 Action: Populate bid_decisions via Shapira Formula pipeline")
    
    # Final recommendations
    print(f"\n" + "=" * 80)
    print("SESSION WORK PLAN (6-hour budget)")
    print("=" * 80)
    
    print(f"\n📋 RECOMMENDED EXECUTION ORDER:")
    print(f"1. Bootstrap desoto + monroe (Letter A): Setup RealAuction scraping")
    print(f"2. Extend parcel linkage for volusia + lee (Letter E): Property appraiser APIs")
    print(f"3. Improve parity matching for indian_river (Letters C/D): Case number cleanup") 
    print(f"4. Address freshness issue in lee (Letter H): Update scraper schedules")
    print(f"5. Start verified outcomes pipeline (Letter B): Court records integration")
    print(f"6. Time permitting: Begin zoning work (Letters G/I)")
    
    print(f"\n⏰ ESTIMATED TIMELINE:")
    print(f"- Counties bootstrap (desoto/monroe): 90 min")
    print(f"- Parcel linkage improvements: 120 min") 
    print(f"- Parity matching fixes: 60 min")
    print(f"- Verified outcomes setup: 90 min")
    print(f"- Testing & verification: 30 min")
    print(f"- TOTAL: 390 min (6.5 hours)")
    
    return {
        'county_rankings': county_scores,
        'high_leverage_counties': high_leverage,
        'zero_state_counties': zero_counties,
        'critical_letter_status': {letter: failing_count for letter in CRITICAL_LETTERS}
    }

if __name__ == "__main__":
    analysis = analyze_priority()