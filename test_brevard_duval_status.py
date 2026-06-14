#!/usr/bin/env python3
"""
Test current status for brevard and duval counties for Gold Standard session
"""
import os
import json

def analyze_briefing_data():
    """Analyze the briefing data for brevard and duval"""
    print("=== GOLD STANDARD SESSION 24 - BREVARD & DUVAL STATUS ===")
    
    # Data from the briefing
    brevard_data = {
        'score': 2,
        'metrics': {
            'A': {'status': 'PASS', 'metric': 5627, 'threshold': None, 'note': 'fc=14079 td=5627'},
            'B': {'status': 'FAIL', 'metric': 134.1, 'threshold': 95, 'note': 'ANOMALY>105 — reconcile denominator/double-count'},
            'C': {'status': 'FAIL', 'metric': 20.8, 'threshold': 95, 'note': 'matched_clean=4092 of 19706'},
            'D': {'status': 'FAIL', 'metric': 33.2, 'threshold': 95, 'note': 'matched_any=6548 of 19706'},
            'E': {'status': 'FAIL', 'metric': 78.6, 'threshold': 95, 'note': 'parcel_linked=15486 of 19706'},
            'F': {'status': 'FAIL', 'metric': 51.1, 'threshold': 95, 'note': 'tier1_sold=3256 closed_sold=6373'},
            'G': {'status': 'FAIL', 'metric': 48.9, 'threshold': 95, 'note': 'density=57.3 far=48.9 pk1000=67.5 (FAR binding)'},
            'H': {'status': 'PASS', 'metric': 8.0, 'threshold': 48, 'note': 'hours since last_seen (SLA 48h)'},
            'I': {'status': 'FAIL', 'metric': 18.6, 'threshold': 95, 'note': 'zoned_complete_parcels=3666 field_complete_parcels=4008'},
            'J': {'status': 'FAIL', 'metric': 0.0, 'threshold': 95, 'note': 'deal_complete=0 of 19706'}
        }
    }
    
    duval_data = {
        'score': 2,
        'metrics': {
            'A': {'status': 'PASS', 'metric': 8436, 'threshold': None, 'note': 'fc=11586 td=8436'},
            'B': {'status': 'FAIL', 'metric': 110.2, 'threshold': 95, 'note': 'ANOMALY>105 — reconcile denominator/double-count'},
            'C': {'status': 'FAIL', 'metric': 16.1, 'threshold': 95, 'note': 'matched_clean=3217 of 20022'},
            'D': {'status': 'FAIL', 'metric': 52.9, 'threshold': 95, 'note': 'matched_any=10590 of 20022'},
            'E': {'status': 'FAIL', 'metric': 83.4, 'threshold': 95, 'note': 'parcel_linked=16700 of 20022'},
            'F': {'status': 'FAIL', 'metric': 63.3, 'threshold': 95, 'note': 'tier1_sold=3995 closed_sold=6307'},
            'G': {'status': 'FAIL', 'metric': None, 'threshold': 95, 'note': 'density= far= pk1000='},
            'H': {'status': 'PASS', 'metric': 13.8, 'threshold': 48, 'note': 'hours since last_seen (SLA 48h)'},
            'I': {'status': 'FAIL', 'metric': None, 'threshold': 95, 'note': 'zoned_complete_parcels=0 field_complete_parcels=3068'},
            'J': {'status': 'FAIL', 'metric': 0.0, 'threshold': 95, 'note': 'deal_complete=0 of 20022'}
        }
    }
    
    print("\n📊 BREVARD STATUS:")
    print(f"   Score: {brevard_data['score']}/10 (A,H pass)")
    for letter, data in brevard_data['metrics'].items():
        status_emoji = "✅" if data['status'] == 'PASS' else "❌"
        metric_str = f"{data['metric']}" if data['metric'] is not None else "NULL"
        print(f"   {letter}: {status_emoji} {metric_str} - {data['note']}")
    
    print("\n📊 DUVAL STATUS:")
    print(f"   Score: {duval_data['score']}/10 (A,H pass)")
    for letter, data in duval_data['metrics'].items():
        status_emoji = "✅" if data['status'] == 'PASS' else "❌"
        metric_str = f"{data['metric']}" if data['metric'] is not None else "NULL"
        print(f"   {letter}: {status_emoji} {metric_str} - {data['note']}")
    
    print("\n🎯 SPRINT ORDER ANALYSIS:")
    
    print("\n**BREVARD SPRINT ORDER (Jun12 velocity-derived):**")
    print("1. C/D ROOT CAUSE (CRITICAL) - numerators frozen while denominator grew 33%")
    print("   → INVOKE pre-authorized clerk/official-records supplementary litmus")
    print("   → C=20.9, D=34.0 vs threshold 95%")
    print("2. J GENERATOR - bid_decisions pipeline (0→95 biggest point block)")
    print("   → Build to evaluator contract: arv+max_bid+ml_score+5 factor keys")
    print("3. G HIT LIST - zone_standards NULL backfill (~15 verified districts)")
    print("   → R-1AAA Melbourne 53.4K parcels, FAR gaps (binding at 48.9%)")
    print("4. B RECONCILIATION - 134.1% anomaly (verified=8547 > closed_sold=6373)")
    
    print("\n**DUVAL SPRINT ORDER:**")
    print("1. G+I SUBSTRATE BUILD - duval-unique blocker")
    print("   → parcel_zones=0 and zoning_districts unpopulated")
    print("   → Jacksonville Ch. 656 covers majority of parcels")
    print("2. C/D ROOT CAUSE - same clerk/official-records litmus as brevard")
    print("   → C=16.1 worse than brevard")
    print("3. J GENERATOR - county-agnostic (check if brevard shard built it first)")
    print("4. B RECONCILIATION - 110.2% anomaly")
    
    print("\n🔧 ULTRALOOP PROTOCOL:")
    print("1. Fan-out subagents per failing letter per county")
    print("2. Adversarial refuter for every claim (survival vote)")
    print("3. Claims ship ONLY if they survive refutation")
    print("4. Log all in gold_standard_ultraloop_audit table")
    
    print("\n📝 SESSION NEXT STEPS:")
    print("1. Verify database connection with live pencil_dod_evaluate_county calls")
    print("2. Start with brevard C/D root cause (highest velocity)")
    print("3. Build J generator (county-agnostic, highest leverage)")
    print("4. Implement duval G+I substrate")
    print("5. Loop verification with live metrics")

if __name__ == "__main__":
    analyze_briefing_data()
    print("\n✅ Analysis complete. Ready to proceed with implementation.")