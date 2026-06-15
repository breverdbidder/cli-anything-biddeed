#!/usr/bin/env python3
"""
SHARD-10 CRITERION-PARALLEL ANALYSIS
Analyze failing patterns across sarasota, hernando, pasco, franklin, union
and determine highest-leverage fixes per the CRITERION-PARALLEL PIVOT directive
"""
from datetime import datetime

# SHARD-10 current status from issue briefing (loop run 28)
SHARD10_BRIEFING_DATA = {
    'sarasota': {
        'pass_count': 2,
        'metrics': {
            'A': {'pass': True, 'metric': 3153, 'details': 'fc=3511 td=3153'},
            'B': {'pass': False, 'metric': None, 'details': 'verified=0 closed_sold=1902'},
            'C': {'pass': False, 'metric': 10.6, 'details': 'matched_clean=705 of 6664'},
            'D': {'pass': False, 'metric': 56.8, 'details': 'matched_any=3788 of 6664'},
            'E': {'pass': False, 'metric': 70.5, 'details': 'parcel_linked=4699 of 6664'},
            'F': {'pass': False, 'metric': 11.9, 'details': 'tier1_sold=227 closed_sold=1902'},
            'G': {'pass': False, 'metric': None, 'details': 'density= far= pk1000='},
            'H': {'pass': True, 'metric': 37.7, 'details': 'hours since last_seen (SLA 48h)'},
            'I': {'pass': False, 'metric': None, 'details': 'zoned_complete_parcels=0 field_complete_parcels=761 auctions=6664'},
            'J': {'pass': False, 'metric': 0.0, 'details': 'deal_complete=0 of 6664 (triangle + two-arm CMA + ml_score + max_bid)'}
        }
    },
    'hernando': {
        'pass_count': 1,
        'metrics': {
            'A': {'pass': True, 'metric': 768, 'details': 'fc=768 td=862'},
            'B': {'pass': False, 'metric': None, 'details': 'verified=0 closed_sold=486'},
            'C': {'pass': False, 'metric': 16.9, 'details': 'matched_clean=276 of 1630'},
            'D': {'pass': False, 'metric': 73.6, 'details': 'matched_any=1200 of 1630'},
            'E': {'pass': False, 'metric': 71.5, 'details': 'parcel_linked=1165 of 1630'},
            'F': {'pass': False, 'metric': 0.0, 'details': 'tier1_sold=0 closed_sold=486'},
            'G': {'pass': False, 'metric': None, 'details': 'density= far= pk1000='},
            'H': {'pass': False, 'metric': 598.4, 'details': 'hours since last_seen (SLA 48h)'},
            'I': {'pass': False, 'metric': None, 'details': 'zoned_complete_parcels=0 field_complete_parcels=312 auctions=1630'},
            'J': {'pass': False, 'metric': 0.0, 'details': 'deal_complete=0 of 1630 (triangle + two-arm CMA + ml_score + max_bid)'}
        }
    },
    'pasco': {
        'pass_count': 1,
        'metrics': {
            'A': {'pass': True, 'metric': 3808, 'details': 'fc=9661 td=3808'},
            'B': {'pass': False, 'metric': None, 'details': 'verified=0 closed_sold=5685'},
            'C': {'pass': False, 'metric': 10.8, 'details': 'matched_clean=1458 of 13469'},
            'D': {'pass': False, 'metric': 40.9, 'details': 'matched_any=5512 of 13469'},
            'E': {'pass': False, 'metric': 1.3, 'details': 'parcel_linked=178 of 13469'},
            'F': {'pass': False, 'metric': 0.0, 'details': 'tier1_sold=0 closed_sold=5685'},
            'G': {'pass': False, 'metric': None, 'details': 'density= far= pk1000='},
            'H': {'pass': False, 'metric': 229.4, 'details': 'hours since last_seen (SLA 48h)'},
            'I': {'pass': False, 'metric': None, 'details': 'zoned_complete_parcels=0 field_complete_parcels=23 auctions=13469'},
            'J': {'pass': False, 'metric': 0.0, 'details': 'deal_complete=0 of 13469 (triangle + two-arm CMA + ml_score + max_bid)'}
        }
    },
    'franklin': {
        'pass_count': 0,
        'metrics': {
            'A': {'pass': False, 'metric': 0, 'details': 'fc=0 td=0'},
            'B': {'pass': False, 'metric': None, 'details': 'verified=0 closed_sold=0'},
            'C': {'pass': False, 'metric': None, 'details': 'matched_clean=0 of 0'},
            'D': {'pass': False, 'metric': None, 'details': 'matched_any=0 of 0'},
            'E': {'pass': False, 'metric': None, 'details': 'parcel_linked=0 of 0'},
            'F': {'pass': False, 'metric': None, 'details': 'tier1_sold=0 closed_sold=0'},
            'G': {'pass': False, 'metric': None, 'details': 'density= far= pk1000='},
            'H': {'pass': False, 'metric': None, 'details': 'hours since last_seen (SLA 48h)'},
            'I': {'pass': False, 'metric': None, 'details': 'zoned_complete_parcels=0 field_complete_parcels=0 auctions=0'},
            'J': {'pass': False, 'metric': None, 'details': 'deal_complete=0 of 0 (triangle + two-arm CMA + ml_score + max_bid)'}
        }
    },
    'union': {
        'pass_count': 0,
        'metrics': {
            'A': {'pass': False, 'metric': 0, 'details': 'fc=0 td=0'},
            'B': {'pass': False, 'metric': None, 'details': 'verified=0 closed_sold=0'},
            'C': {'pass': False, 'metric': None, 'details': 'matched_clean=0 of 0'},
            'D': {'pass': False, 'metric': None, 'details': 'matched_any=0 of 0'},
            'E': {'pass': False, 'metric': None, 'details': 'parcel_linked=0 of 0'},
            'F': {'pass': False, 'metric': None, 'details': 'tier1_sold=0 closed_sold=0'},
            'G': {'pass': False, 'metric': None, 'details': 'density= far= pk1000='},
            'H': {'pass': False, 'metric': None, 'details': 'hours since last_seen (SLA 48h)'},
            'I': {'pass': False, 'metric': None, 'details': 'zoned_complete_parcels=0 field_complete_parcels=0 auctions=0'},
            'J': {'pass': False, 'metric': None, 'details': 'deal_complete=0 of 0 (triangle + two-arm CMA + ml_score + max_bid)'}
        }
    }
}

def analyze_criterion_patterns():
    """Analyze patterns across failing letters to identify highest-leverage fixes"""
    
    print("=" * 80)
    print("SHARD-10 CRITERION-PARALLEL ANALYSIS")
    print("=" * 80)
    print(f"Analysis Time: {datetime.now().isoformat()}")
    print(f"Counties: sarasota, hernando, pasco, franklin, union")
    print()
    
    # Count failures by letter across shard
    letter_failures = {}
    for county, data in SHARD10_BRIEFING_DATA.items():
        for letter, metrics in data['metrics'].items():
            if not metrics['pass']:
                if letter not in letter_failures:
                    letter_failures[letter] = []
                letter_failures[letter].append(county)
    
    print("📊 FAILING LETTERS ACROSS SHARD-10:")
    print("-" * 50)
    for letter in sorted(letter_failures.keys()):
        counties = letter_failures[letter]
        print(f"{letter}: {len(counties)}/5 counties - {', '.join(counties)}")
    
    print()
    print("🎯 CRITERION-PARALLEL PIVOT ANALYSIS:")
    print("-" * 50)
    
    # Priority 1: Universal failures (affects all or most counties)
    print("\n1. UNIVERSAL BLOCKERS (5/5 counties failing):")
    universal_blockers = [letter for letter, counties in letter_failures.items() if len(counties) == 5]
    for letter in universal_blockers:
        if letter == 'J':
            print(f"   {letter}: bid_decisions pipeline missing - 0.0% across all counties")
            print("      ROOT CAUSE: Generator not built (fleet-wide architectural gap)")
            print("      IMPACT: 5 counties × 1 letter = 5 points")
        elif letter == 'B':
            print(f"   {letter}: Verified outcomes missing - verified=0 across all counties")
            print("      ROOT CAUSE: Independent clerk source verification not built")  
            print("      IMPACT: 5 counties × 1 letter = 5 points")
        elif letter == 'G':
            print(f"   {letter}: Zoning KPI missing - null metrics across all counties")
            print("      ROOT CAUSE: v_zoning_gold_standard_kpi_v3 empty for these counties")
            print("      IMPACT: 5 counties × 1 letter = 5 points")
        elif letter == 'I':
            print(f"   {letter}: Property cards incomplete - zoned_complete=0 across all counties")
            print("      ROOT CAUSE: Dependent on G (zoning substrate)")
            print("      IMPACT: 5 counties × 1 letter = 5 points")
        else:
            print(f"   {letter}: {len(letter_failures[letter])}/5 counties")
    
    # Priority 2: High-impact patterns
    print("\n2. HIGH-IMPACT PATTERNS:")
    
    # E linkage analysis  
    e_counties = letter_failures.get('E', [])
    if e_counties:
        print(f"   E (Parcel Linkage): {len(e_counties)}/5 counties - {', '.join(e_counties)}")
        print("      sarasota: 70.5% (4699/6664) - close to pass threshold")
        print("      hernando: 71.5% (1165/1630) - close to pass threshold") 
        print("      pasco: 1.3% (178/13469) - CRITICAL gap")
        print("      LEVERAGE: Fixing pasco E unblocks 13,469 auctions for I/J/F")
    
    # H freshness analysis
    h_counties = letter_failures.get('H', [])
    if h_counties:
        print(f"   H (Freshness): {len(h_counties)}/5 counties - {', '.join(h_counties)}")
        print("      hernando: 598.4h (25 days) - scraper stalled")
        print("      pasco: 229.4h (9.6 days) - scraper stalled")
        print("      LEVERAGE: Scraper fixes for 2 counties = 2 points")
    
    # Priority 3: Optimize-able counties (already have some passes)
    print("\n3. OPTIMIZATION TARGETS (counties with >0 passes):")
    optimizable = [(county, data['pass_count']) for county, data in SHARD10_BRIEFING_DATA.items() if data['pass_count'] > 0]
    optimizable.sort(key=lambda x: x[1], reverse=True)
    
    for county, passes in optimizable:
        failing = [l for l, m in SHARD10_BRIEFING_DATA[county]['metrics'].items() if not m['pass']]
        print(f"   {county}: {passes}/10 PASS - {8 + (2-passes)} potential points from {', '.join(failing)}")
        
        # Specific optimization notes
        if county == 'sarasota':
            print("      Near-passes: C 10.6% (need 95%), D 56.8%, E 70.5%")
        elif county == 'hernando':
            print("      Near-passes: C 16.9%, D 73.6%, E 71.5%") 
        elif county == 'pasco':
            print("      Critical: E 1.3% blocks everything downstream")
    
    # Priority 4: Bootstrap targets
    print("\n4. BOOTSTRAP TARGETS (0/10 pass counties):")
    bootstrap = [county for county, data in SHARD10_BRIEFING_DATA.items() if data['pass_count'] == 0]
    for county in bootstrap:
        print(f"   {county}: Full pipeline bootstrap needed - all metrics null/0")
    
    return generate_work_order()

def generate_work_order():
    """Generate prioritized work order per CRITERION-PARALLEL PIVOT"""
    
    print("\n" + "=" * 80)
    print("WORK ORDER (CRITERION-PARALLEL PRIORITY)")
    print("=" * 80)
    
    work_order = []
    
    # Phase 1: Universal Infrastructure (highest leverage)
    print("\n🚀 PHASE 1: UNIVERSAL INFRASTRUCTURE")
    print("-" * 40)
    
    print("1. J GENERATOR (5 counties, 0.0% → 95%)")
    print("   BUILD: bid_decisions pipeline with Shapira Formula")
    print("   FILES: scripts/j_generator_shard10.py")
    print("   IMPACT: 5 letters × 1 point = 5 certification points")
    work_order.append({
        'phase': 1,
        'letter': 'J', 
        'impact': '5 counties',
        'action': 'Build bid_decisions generator',
        'files': ['scripts/j_generator_shard10.py']
    })
    
    print("\n2. B VERIFIED OUTCOMES (5 counties, null → 95%)")
    print("   BUILD: Independent clerk source verification")  
    print("   FILES: scripts/b_verified_outcomes_shard10.py")
    print("   IMPACT: 5 letters × 1 point = 5 certification points")
    work_order.append({
        'phase': 1,
        'letter': 'B',
        'impact': '5 counties', 
        'action': 'Build verified outcomes scraper',
        'files': ['scripts/b_verified_outcomes_shard10.py']
    })
    
    # Phase 2: Parcel Infrastructure (unblocks I/F)
    print("\n🔧 PHASE 2: PARCEL INFRASTRUCTURE") 
    print("-" * 40)
    
    print("3. E PARCEL LINKAGE (pasco critical)")
    print("   FIX: pasco 1.3% → 95% (unblocks 13,469 auctions)")
    print("   OPTIMIZE: sarasota 70.5% → 95%, hernando 71.5% → 95%")
    print("   FILES: scripts/e_parcel_linkage_shard10.py")
    print("   IMPACT: 3 letters × 1 point = 3 points + unblocks I/J/F")
    work_order.append({
        'phase': 2,
        'letter': 'E',
        'impact': '3 counties critical',
        'action': 'Fix parcel linking (pasco priority)',
        'files': ['scripts/e_parcel_linkage_shard10.py'] 
    })
    
    print("\n4. H FRESHNESS (hernando, pasco stalled scrapers)")
    print("   FIX: Resume stalled scrapers")
    print("   hernando: 598.4h → <48h")
    print("   pasco: 229.4h → <48h") 
    print("   FILES: scripts/h_scraper_resume_shard10.py")
    print("   IMPACT: 2 letters × 1 point = 2 points")
    work_order.append({
        'phase': 2,
        'letter': 'H', 
        'impact': '2 counties',
        'action': 'Resume stalled scrapers',
        'files': ['scripts/h_scraper_resume_shard10.py']
    })
    
    # Phase 3: Parity Optimization
    print("\n📊 PHASE 3: PARITY OPTIMIZATION")
    print("-" * 40)
    
    print("5. C/D PARITY IMPROVEMENTS")
    print("   sarasota: C 10.6% → 95%, D 56.8% → 95%")
    print("   hernando: C 16.9% → 95%, D 73.6% → 95%") 
    print("   pasco: C 10.8% → 95%, D 40.9% → 95%")
    print("   FILES: scripts/cd_parity_shard10.py")
    print("   IMPACT: 6 letters × 1 point = 6 points")
    work_order.append({
        'phase': 3,
        'letter': 'C/D',
        'impact': '3 counties',
        'action': 'Improve parity matching',
        'files': ['scripts/cd_parity_shard10.py']
    })
    
    # Phase 4: Bootstrap (if time permits)
    print("\n🏗️ PHASE 4: BOOTSTRAP (if time permits)")
    print("-" * 40)
    
    print("6. A BOOTSTRAP (franklin, union)")
    print("   Both counties: 0 auctions → baseline ingestion")
    print("   FILES: scripts/a_bootstrap_shard10.py") 
    print("   IMPACT: 2 letters × 1 point = 2 points")
    work_order.append({
        'phase': 4,
        'letter': 'A',
        'impact': '2 counties',
        'action': 'Bootstrap franklin/union data ingestion', 
        'files': ['scripts/a_bootstrap_shard10.py']
    })
    
    print("\n📋 TOTAL POTENTIAL IMPACT:")
    print("   Phase 1: 10 points (J + B universal)")
    print("   Phase 2: 5 points (E + H targeted)")
    print("   Phase 3: 6 points (C/D optimization)")
    print("   Phase 4: 2 points (A bootstrap)")
    print("   TOTAL: 23 points possible")
    
    print("\n✅ CERTIFICATION PATH:")
    print("   Current: sarasota 2/10, hernando 1/10, pasco 1/10")
    print("   After Phases 1-3: sarasota 8/10, hernando 7/10, pasco 8/10")
    print("   Remaining gaps: G/I (zoning substrate), F (depends on tier1 promotion)")
    
    return work_order

if __name__ == "__main__":
    work_order = analyze_criterion_patterns()
    print(f"\n🎯 SHARD-10 WORK ORDER GENERATED: {len(work_order)} phases")
    print("Ready for autonomous execution per CRITERION-PARALLEL PIVOT")