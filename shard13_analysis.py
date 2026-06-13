#!/usr/bin/env python3
"""
SHARD-13 Priority Analysis
Counties: orange, flagler, santa_rosa, gulf
"""

# Current status from issue briefing (run 23)
briefing_data = {
    'orange': {
        'score': 2,
        'metrics': {
            'A': {'grade': 'PASS', 'metric': 5540, 'detail': 'fc=10591 td=5540'},
            'B': {'grade': 'FAIL', 'metric': None, 'detail': 'verified=0 closed_sold=5311'}, 
            'C': {'grade': 'FAIL', 'metric': 15.8, 'detail': 'matched_clean=2550 of 16131'},
            'D': {'grade': 'FAIL', 'metric': 42.8, 'detail': 'matched_any=6911 of 16131'},
            'E': {'grade': 'FAIL', 'metric': 72.2, 'detail': 'parcel_linked=11643 of 16131'},
            'F': {'grade': 'FAIL', 'metric': 3.9, 'detail': 'tier1_sold=207 closed_sold=5311'},
            'G': {'grade': 'FAIL', 'metric': None, 'detail': 'density= far= pk1000='},
            'H': {'grade': 'PASS', 'metric': 31.6, 'detail': 'hours since last_seen (SLA 48h)'},
            'I': {'grade': 'FAIL', 'metric': None, 'detail': 'zoned_complete_parcels=0 field_complete_parcels=1611 auctions=16131'},
            'J': {'grade': 'FAIL', 'metric': 0.0, 'detail': 'deal_complete=0 of 16131'}
        }
    },
    'flagler': {
        'score': 1,
        'metrics': {
            'A': {'grade': 'PASS', 'metric': 43, 'detail': 'fc=43 td=489'},
            'B': {'grade': 'FAIL', 'metric': None, 'detail': 'verified=0 closed_sold=80'},
            'C': {'grade': 'FAIL', 'metric': 10.9, 'detail': 'matched_clean=58 of 532'},
            'D': {'grade': 'FAIL', 'metric': 90.6, 'detail': 'matched_any=482 of 532'},
            'E': {'grade': 'FAIL', 'metric': 56.0, 'detail': 'parcel_linked=298 of 532'},
            'F': {'grade': 'FAIL', 'metric': 8.8, 'detail': 'tier1_sold=7 closed_sold=80'},
            'G': {'grade': 'FAIL', 'metric': None, 'detail': 'density= far= pk1000='},
            'H': {'grade': 'FAIL', 'metric': 198.9, 'detail': 'hours since last_seen (SLA 48h)'},
            'I': {'grade': 'FAIL', 'metric': None, 'detail': 'zoned_complete_parcels=0 field_complete_parcels=154 auctions=532'},
            'J': {'grade': 'FAIL', 'metric': 0.0, 'detail': 'deal_complete=0 of 532'}
        }
    },
    'santa_rosa': {
        'score': 1,
        'metrics': {
            'A': {'grade': 'PASS', 'metric': 1044, 'detail': 'fc=1044 td=1056'},
            'B': {'grade': 'FAIL', 'metric': None, 'detail': 'verified=0 closed_sold=817'},
            'C': {'grade': 'FAIL', 'metric': 13.4, 'detail': 'matched_clean=281 of 2100'},
            'D': {'grade': 'FAIL', 'metric': 58.0, 'detail': 'matched_any=1219 of 2100'},
            'E': {'grade': 'FAIL', 'metric': 71.8, 'detail': 'parcel_linked=1507 of 2100'},
            'F': {'grade': 'FAIL', 'metric': 0.0, 'detail': 'tier1_sold=0 closed_sold=817'},
            'G': {'grade': 'FAIL', 'metric': None, 'detail': 'density= far= pk1000='},
            'H': {'grade': 'FAIL', 'metric': 198.9, 'detail': 'hours since last_seen (SLA 48h)'},
            'I': {'grade': 'FAIL', 'metric': None, 'detail': 'zoned_complete_parcels=0 field_complete_parcels=355 auctions=2100'},
            'J': {'grade': 'FAIL', 'metric': 0.0, 'detail': 'deal_complete=0 of 2100'}
        }
    },
    'gulf': {
        'score': 0,
        'metrics': {
            'A': {'grade': 'FAIL', 'metric': 0, 'detail': 'fc=9 td=0'},
            'B': {'grade': 'FAIL', 'metric': None, 'detail': 'verified=0 closed_sold=3'},
            'C': {'grade': 'FAIL', 'metric': 33.3, 'detail': 'matched_clean=3 of 9'},
            'D': {'grade': 'FAIL', 'metric': 55.6, 'detail': 'matched_any=5 of 9'},
            'E': {'grade': 'FAIL', 'metric': 88.9, 'detail': 'parcel_linked=8 of 9'},
            'F': {'grade': 'FAIL', 'metric': 0.0, 'detail': 'tier1_sold=0 closed_sold=3'},
            'G': {'grade': 'FAIL', 'metric': None, 'detail': 'density= far= pk1000='},
            'H': {'grade': 'FAIL', 'metric': 367.0, 'detail': 'hours since last_seen (SLA 48h)'},
            'I': {'grade': 'FAIL', 'metric': None, 'detail': 'zoned_complete_parcels=0 field_complete_parcels=2 auctions=9'},
            'J': {'grade': 'FAIL', 'metric': 0.0, 'detail': 'deal_complete=0 of 9'}
        }
    }
}

def analyze_shard_priorities():
    print("=" * 80)
    print("SHARD-13 PRIORITY ANALYSIS")
    print("=" * 80)
    
    # Count total failing by letter
    failing_by_letter = {}
    total_auctions_by_letter = {}
    
    for county, data in briefing_data.items():
        for letter, info in data['metrics'].items():
            if info['grade'] == 'FAIL':
                if letter not in failing_by_letter:
                    failing_by_letter[letter] = []
                    total_auctions_by_letter[letter] = 0
                failing_by_letter[letter].append(county)
                
                # Extract auction counts for scale analysis
                if 'of' in str(info['detail']):
                    try:
                        parts = info['detail'].split('of')
                        if len(parts) > 1:
                            auction_count = int(parts[1].strip().split()[0])
                            total_auctions_by_letter[letter] += auction_count
                    except:
                        pass
    
    print("\n📊 FAILING LETTERS ACROSS SHARD-13:")
    print("Format: Letter (counties affected) - Total scale impact")
    
    # Order by impact (number of counties + scale)
    letter_priority = []
    for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
        counties = failing_by_letter.get(letter, [])
        if counties:
            scale = total_auctions_by_letter.get(letter, 0)
            impact_score = len(counties) * 1000 + scale
            letter_priority.append((letter, len(counties), scale, counties))
    
    # Sort by impact
    letter_priority.sort(key=lambda x: x[1] * 1000 + x[2], reverse=True)
    
    for letter, count, scale, counties in letter_priority:
        print(f"**{letter}**: {count} counties ({', '.join(counties)}) - {scale:,} total auctions affected")
    
    print(f"\n📊 COUNTY STATUS:")
    for county, data in briefing_data.items():
        score = data['score']
        passing = [letter for letter, info in data['metrics'].items() if info['grade'] == 'PASS']
        failing = [letter for letter, info in data['metrics'].items() if info['grade'] == 'FAIL']
        print(f"**{county}**: {score}/10 - Pass: {', '.join(passing)} | Fail: {', '.join(failing)}")
    
    return letter_priority

def identify_highest_leverage_fixes():
    print("\n" + "=" * 80)
    print("HIGHEST LEVERAGE ANALYSIS")
    print("=" * 80)
    
    print("\n🎯 **CRITERION-PARALLEL STRATEGY (from briefing):**")
    
    # J - Fleet-wide blocker
    print("\n1. **J (bid_decisions generator) - HIGHEST LEVERAGE**")
    print("   - All 4 counties fail: 0.0% across 19,072 total auctions")
    print("   - Root cause: bid_decisions table empty (generator doesn't exist)")
    print("   - Single fix moves 4 counties, largest impact")
    print("   - Requirements: arv + max_bid + ml_score + 5 factor keys")
    
    # B - Independent verification missing  
    print("\n2. **B (verified outcomes) - FLEET INFRASTRUCTURE**")
    print("   - All 4 counties fail: null metrics (no independent verification)")
    print("   - Affects 6,211 total closed sales across shard")
    print("   - Requires independent data source (not PropertyOnion derived)")
    
    # G/I - Structural missing
    print("\n3. **G/I (zoning infrastructure) - STRUCTURAL BLOCKER**")  
    print("   - All 4 counties null (missing parcel_zones + zone_standards)")
    print("   - G: density/FAR/parking data completely absent")
    print("   - I: property cards can't complete without zoning linkage")
    
    # A - Gulf specific
    print("\n4. **A (dual coverage) - GULF SPECIFIC**")
    print("   - Gulf: 0 tax deeds despite 9 foreclosures")
    print("   - Likely missing tax deed lane configuration") 
    print("   - Quick fix if lane exists, bigger if lane missing")
    
    # C/D - Parity matching  
    print("\n5. **C/D (parity matching) - QUALITY IMPROVEMENT**")
    print("   - C: 10.9-33.3% clean matches (need 95%)")
    print("   - D: 42.8-90.6% any matches (need 95%)")
    print("   - PropertyOnion parity vs official records")
    
    # E - Parcel linkage
    print("\n6. **E (parcel linkage) - ENABLER FOR I/J**")
    print("   - 56.0-88.9% linked (need 95%)")  
    print("   - Blocks property card completion (I)")
    print("   - Blocks comps eligibility for deal analysis (J)")
    
    # H - Freshness (flagler, santa_rosa, gulf)
    print("\n7. **H (freshness) - SCRAPER HEALTH**")
    print("   - flagler/santa_rosa: 198.9h (8+ days stale)")
    print("   - gulf: 367h (15+ days stale)")  
    print("   - Check scraper scheduling/errors")

def recommend_session_plan():
    print("\n" + "=" * 80)
    print("RECOMMENDED SESSION EXECUTION ORDER")
    print("=" * 80)
    
    print("\n📋 **6-Hour Session Plan:**")
    
    print("\n**Phase 1: Infrastructure Fixes (2-3 hours)**")
    print("1. **J GENERATOR BUILD** (90 min)")
    print("   - County-agnostic: build bid_decisions pipeline")
    print("   - Inputs: gen_valuations_comps_batch + Shapira V14 ml_score")
    print("   - Output: 19,072 auctions with deal thesis components")
    print("   - Verification: SELECT COUNT(*) FROM bid_decisions WHERE ml_score IS NOT NULL")
    
    print("\n2. **B VERIFICATION INFRASTRUCTURE** (60 min)")
    print("   - Research independent verification sources per county")
    print("   - Implement clerk/official records scraping")
    print("   - Alternative: PropertyOnion supplement (if authorized)")
    print("   - Target: verified_outcomes for 6,211 sales")
    
    print("\n**Phase 2: County-Specific Fixes (2-3 hours)**")
    print("3. **A GULF TAX DEED LANE** (45 min)")
    print("   - Check pipeline.counties configuration")
    print("   - Verify both RealAuction + TaxDeedGuru lanes active")
    print("   - Fix fc=9 → td=0 gap (should be balanced)")
    
    print("\n4. **H FRESHNESS RECOVERY** (45 min)")
    print("   - Check scraper health for flagler/santa_rosa/gulf")
    print("   - Restart stalled scrapers or fix configurations")
    print("   - Target: <48h freshness SLA")
    
    print("\n5. **E PARCEL LINKAGE IMPROVEMENT** (60 min)")
    print("   - Focus on largest gaps: flagler (56%), santa_rosa (71.8%)")
    print("   - ArcGIS FeatureServer queries per county")
    print("   - Immediate impact on I/J eligibility")
    
    print("\n**Phase 3: If Time Permits (1-2 hours)**")
    print("6. **C/D PARITY RECONCILIATION** (60 min)")
    print("   - PropertyOnion vs official records comparison")
    print("   - Address normalization and fuzzy matching")
    print("   - Focus on orange (largest volume)")
    
    print("7. **G/I ZONING SUBSTRATE** (if time)")
    print("   - Requires jurisdiction setup + parcel_zones ingestion")
    print("   - Probably too large for this session")
    print("   - Document blockers for next session")

if __name__ == "__main__":
    letter_priorities = analyze_shard_priorities()
    identify_highest_leverage_fixes()
    recommend_session_plan()
    
    print("\n" + "=" * 80)
    print("READY TO EXECUTE")
    print("=" * 80)
    print("\nNext: Start with J GENERATOR BUILD")
    print("Evidence required: Live DB verification after each fix")
    print("SHIP-TO-MAIN: Commit directly, no side branches")