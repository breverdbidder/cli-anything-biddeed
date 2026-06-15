#!/usr/bin/env python3
"""
SHARD-10 Analysis based on briefing data
Counties: palm_beach, escambia, okeechobee, franklin, union
"""

def analyze_shard10_priorities():
    """Analyze SHARD-10 priorities based on briefing data"""
    
    # Current status from issue briefing
    briefing_data = {
        'palm_beach': {
            'score': 2,
            'metrics': {
                'A': {'grade': 'PASS', 'metric': 8591, 'details': 'fc=15414 td=8591'},
                'B': {'grade': 'FAIL', 'metric': None, 'details': 'verified=0 closed_sold=9041'},
                'C': {'grade': 'FAIL', 'metric': 19.2, 'details': 'matched_clean=4609 of 24005'},
                'D': {'grade': 'FAIL', 'metric': 46.4, 'details': 'matched_any=11144 of 24005'},
                'E': {'grade': 'FAIL', 'metric': 80.3, 'details': 'parcel_linked=19275 of 24005'},
                'F': {'grade': 'FAIL', 'metric': 1.9, 'details': 'tier1_sold=176 closed_sold=9041'},
                'G': {'grade': 'FAIL', 'metric': None, 'details': 'density= far= pk1000='},
                'H': {'grade': 'PASS', 'metric': 0.4, 'details': 'hours since last_seen (SLA 48h)'},
                'I': {'grade': 'FAIL', 'metric': None, 'details': 'zoned_complete_parcels=0 field_complete_parcels=2894 auctions=24005'},
                'J': {'grade': 'FAIL', 'metric': 0.0, 'details': 'deal_complete=0 of 24005 (triangle + two-arm CMA + ml_score + max_bid)'}
            }
        },
        'escambia': {
            'score': 1,
            'metrics': {
                'A': {'grade': 'PASS', 'metric': 3195, 'details': 'fc=3195 td=3362'},
                'B': {'grade': 'FAIL', 'metric': None, 'details': 'verified=0 closed_sold=2102'},
                'C': {'grade': 'FAIL', 'metric': 20.5, 'details': 'matched_clean=1343 of 6557'},
                'D': {'grade': 'FAIL', 'metric': 59.0, 'details': 'matched_any=3869 of 6557'},
                'E': {'grade': 'FAIL', 'metric': 87.1, 'details': 'parcel_linked=5714 of 6557'},
                'F': {'grade': 'FAIL', 'metric': 0.1, 'details': 'tier1_sold=2 closed_sold=2102'},
                'G': {'grade': 'FAIL', 'metric': None, 'details': 'density= far= pk1000='},
                'H': {'grade': 'FAIL', 'metric': 82.2, 'details': 'hours since last_seen (SLA 48h)'},
                'I': {'grade': 'FAIL', 'metric': None, 'details': 'zoned_complete_parcels=0 field_complete_parcels=1709 auctions=6557'},
                'J': {'grade': 'FAIL', 'metric': 0.0, 'details': 'deal_complete=0 of 6557 (triangle + two-arm CMA + ml_score + max_bid)'}
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
                'H': {'grade': 'FAIL', 'metric': 439.0, 'details': 'hours since last_seen (SLA 48h)'},
                'I': {'grade': 'FAIL', 'metric': None, 'details': 'zoned_complete_parcels=0 field_complete_parcels=136 auctions=450'},
                'J': {'grade': 'FAIL', 'metric': 0.0, 'details': 'deal_complete=0 of 450 (triangle + two-arm CMA + ml_score + max_bid)'}
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
                'J': {'grade': 'FAIL', 'metric': None, 'details': 'deal_complete=0 of 0 (triangle + two-arm CMA + ml_score + max_bid)'}
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
                'J': {'grade': 'FAIL', 'metric': None, 'details': 'deal_complete=0 of 0 (triangle + two-arm CMA + ml_score + max_bid)'}
            }
        }
    }
    
    print("=" * 80)
    print("SHARD-10 GOLD STANDARD ANALYSIS")
    print("=" * 80)
    
    print("\n📊 COUNTY SCORES SUMMARY:")
    total_passing_letters = 0
    for county, data in briefing_data.items():
        score = data['score']
        total_passing_letters += score
        failing = [letter for letter, info in data['metrics'].items() if info['grade'] == 'FAIL']
        print(f"  {county}: {score}/10 - Failing: {', '.join(failing)}")
    
    print(f"\nTOTAL SHARD: {total_passing_letters}/50 passing letters")
    
    print("\n🎯 LEVERAGE ANALYSIS:")
    
    # Count failing by letter across shard
    failing_by_letter = {}
    for county, data in briefing_data.items():
        for letter, info in data['metrics'].items():
            if info['grade'] == 'FAIL':
                if letter not in failing_by_letter:
                    failing_by_letter[letter] = []
                failing_by_letter[letter].append(county)
    
    # High-leverage fixes (affect most counties)
    high_leverage = [(letter, counties) for letter, counties in failing_by_letter.items() 
                     if len(counties) >= 4]  # 4+ counties
    high_leverage.sort(key=lambda x: len(x[1]), reverse=True)
    
    print("HIGH-LEVERAGE FIXES (4+ counties):")
    for letter, counties in high_leverage:
        print(f"  {letter}: {len(counties)} counties ({', '.join(counties)})")
    
    print("\n📈 COUNTY PRIORITIZATION:")
    
    # Prioritize by impact potential 
    county_priorities = []
    for county, data in briefing_data.items():
        score = data['score']
        auction_count = 0
        
        # Extract auction counts from A metric details
        a_details = data['metrics']['A']['details']
        if 'fc=' in a_details and 'td=' in a_details:
            # Parse fc (foreclosure) + td (tax deed) counts
            fc = int(a_details.split('fc=')[1].split()[0])
            td = int(a_details.split('td=')[1].split()[0]) if 'td=' in a_details else 0
            auction_count = fc + td
        
        # Calculate impact potential (low score + high auction volume = high impact)
        if auction_count > 0:
            impact = auction_count * (10 - score)  # More impact for lower scores
        else:
            impact = 0
            
        county_priorities.append({
            'county': county,
            'score': score,
            'auction_count': auction_count,
            'impact_potential': impact
        })
    
    county_priorities.sort(key=lambda x: x['impact_potential'], reverse=True)
    
    for i, county_data in enumerate(county_priorities, 1):
        county = county_data['county']
        score = county_data['score']
        auctions = county_data['auction_count']
        impact = county_data['impact_potential']
        
        if score == 0 and auctions == 0:
            priority = "🔴 CRITICAL (No data)"
        elif score < 2 and auctions > 1000:
            priority = "🔴 CRITICAL (High volume, low score)"
        elif score < 3:
            priority = "🟡 HIGH"
        else:
            priority = "🟢 MEDIUM"
        
        print(f"  {i}. {county}: {score}/10, {auctions} auctions, {priority}")
    
    print("\n🚀 RECOMMENDED SESSION PLAN (6-hour budget):")
    
    # Strategy based on briefing analysis and criterion-parallel pivot
    print("""
1. **FRANKLIN & UNION (A-lane setup)** [30 min]
   - Zero auctions = need lane configuration first
   - Run scripts/shard6_configure_lanes.py for both counties
   - Verify pipeline.counties setup and test scrapers
   
2. **PALM_BEACH B-reconciliation** [45 min]  
   - 9041 closed sales but 0 verified outcomes (highest volume)
   - Build verified outcome scraper for Palm Beach clerk records
   - Likely biggest single metric gain in shard
   
3. **FLEET-WIDE J GENERATOR** [90 min]
   - All 5 counties J=0.0% (bid_decisions table empty)
   - County-agnostic fix benefits all shards
   - Build Shapira V14 ML pipeline per briefing specs
   
4. **OKEECHOBEE H-freshness** [20 min]
   - 439 hours since last_seen (SLA violation by 9x)
   - Quick scraper fix, high impact for small county
   
5. **ESCAMBIA H-freshness** [15 min] 
   - 82.2 hours since last_seen (SLA violation)
   - Similar quick fix
   
6. **C/D PARITY FIXES** [120 min]
   - All counties have low clean matching (17-20%)
   - Implement clerk/official-records supplementary litmus
   - Pre-authorized per briefing: "invoke now, document evidence"
   
7. **VERIFICATION & COMMIT** [30 min]
   - Run pencil_dod_evaluate_county for all 5
   - Commit to main with SQL verification blocks
   - Update progress tracking
   
ESTIMATED TOTAL: 5.5 hours (within 6h budget)
EXPECTED GAIN: +15-20 passing letters across shard
    """)
    
    return briefing_data

def identify_critical_paths():
    """Identify critical dependency paths for maximum efficiency"""
    print("\n🔗 CRITICAL DEPENDENCY ANALYSIS:")
    print("""
DEPENDENCY CHAIN (sequence matters):
1. A (lanes) → All other metrics (data source required)
2. E (parcel linkage) → I (property cards) 
3. B (verified outcomes) → F (tier1 promotion) [existing automation]
4. G (zoning) → I (property cards) [structural requirement]

PARALLEL-SAFE (can work simultaneously):
- J generator (county-agnostic)
- H freshness (per-county scrapers)
- C/D parity (per-county matching)
- B verified outcomes (per-county clerks)

BLOCKING PATHS:
- Franklin/Union: A=FAIL blocks everything else
- All counties: G=null blocks I completely  
- All counties: J pipeline absent (fleet-wide gap)
    """)

if __name__ == "__main__":
    briefing_data = analyze_shard10_priorities()
    identify_critical_paths()
    
    print("\n" + "=" * 80)
    print("READY TO EXECUTE - Proceeding with session plan...")
    print("=" * 80)