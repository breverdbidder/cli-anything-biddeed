#!/usr/bin/env python3
"""
Gold Standard shard-3 SESSION CLOSE-OUT — dispatch_id 697ee013-cc20-4655-bdf7-14e820c464b2
Counties: sumter, suwannee, wakulla
Date: 2026-08-26

WHAT THIS SCRIPT DOCUMENTS (already executed live via PostgREST this session,
this file is a record, not something meant to be re-run to "do" the work):

1. Ran pencil_dod_evaluate_county live for sumter, suwannee, wakulla as the
   final authoritative after-state for the session. See county_final_states
   in the structured session output for exact JSON.

2. Cross-checked prior-session diagnose/fix claims against the adversarial
   verify results supplied in the dispatch brief:
     - sumter_C (NO_CHANGE): no fix attempted, no audit row required (only
       FIXED/PARTIAL claims require an audit row per the brief).
     - suwannee_CD (PARTIAL, verdict SURVIVED): D flipped FAIL 82.9%
       (matched_any=29) -> PASS 100.0% (matched_any=35). C held FAIL at
       82.9% (matched_clean=29), unchanged, correctly not counted as a
       clean match. Both letters written to gold_standard_ultraloop_audit
       with survived=true.
     - wakulla_CEIJ (NO_CHANGE): no fix attempted, no audit row required.
   No REFUTED claims were present in this session's adversarial verify
   batch, so no survived=false rows were needed.

3. WROTE 2 rows to gold_standard_ultraloop_audit (POST via PostgREST,
   HTTP 201, ids 18247 and 18248):
     - dispatch_id=697ee013-cc20-4655-bdf7-14e820c464b2, ultraloop_mode=native,
       county_slug=suwannee, letter=C, survived=true
     - dispatch_id=697ee013-cc20-4655-bdf7-14e820c464b2, ultraloop_mode=native,
       county_slug=suwannee, letter=D, survived=true

4. PATCHED gold_standard_campaign row id=5060 (matched via
   dispatch_id=eq.697ee013-cc20-4655-bdf7-14e820c464b2, target_counties=
   ["sumter","suwannee","wakulla"], the correct/unambiguous row for this
   shard's dispatch — confirmed via GET before writing, HTTP 200 on PATCH):
     criteria_passed (per-county A-J booleans from step-1 live re-check):
       sumter:   {A:T,B:T,C:F,D:T,E:T,F:T,G:T,H:T,I:T,J:T}
       suwannee: {A:T,B:T,C:F,D:T,E:T,F:T,G:T,H:T,I:T,J:T}
       wakulla:  {A:T,B:T,C:F,D:T,E:F,F:T,G:T,H:T,I:F,J:F}
     criteria_total: 10
     exit_reason: 'timeout'  (session budget close-out, not full certification)
     session_end_at: 2026-08-26T08:14:58.000Z

NO other writes were made. No gold_standard_loop() or gold_standard_certify()
calls were made (fleet coordination rule respected — other shards may be
mid-flight). No PropertyOnion data was ingested or referenced as an origin
data_source anywhere in this session.

HONESTY TAG: VERIFIED — every number above was read directly from live
PostgREST HTTP responses captured in this session (RPC 200s, POST 201,
PATCH 200), pasted without alteration into this record.
"""

FINAL_STATE_SUMTER = {
    "A": {"pass": True, "detail": "fc=10 td=14", "metric": 10},
    "B": {"pass": True, "detail": "verified=4 closed_sold=4", "metric": 100.0},
    "C": {"pass": False, "detail": "matched_clean=21", "metric": 87.5},
    "D": {"pass": True, "detail": "matched_any=24", "metric": 100.0},
    "E": {"pass": True, "detail": "parcel_linked=24", "metric": 100.0},
    "F": {"pass": True, "detail": "tier1_sold=4 closed_sold=4", "metric": 100.0},
    "G": {"pass": True, "detail": "density=100.0 far=100.0 pk1000=100.0", "metric": 100.0},
    "H": {"pass": True, "detail": "hours since last_seen (SLA 48h)", "metric": 0.8},
    "I": {"pass": True, "detail": "card_complete=24 of 24", "metric": 100.0},
    "J": {"pass": True, "detail": "deal_complete=24 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 100.0},
    "auctions_total": 24,
}

FINAL_STATE_SUWANNEE = {
    "A": {"pass": True, "detail": "fc=4 td=31", "metric": 4},
    "B": {"pass": True, "detail": "verified=4 closed_sold=4", "metric": 100.0},
    "C": {"pass": False, "detail": "matched_clean=29", "metric": 82.9},
    "D": {"pass": True, "detail": "matched_any=35", "metric": 100.0},
    "E": {"pass": True, "detail": "parcel_linked=35", "metric": 100.0},
    "F": {"pass": True, "detail": "tier1_sold=4 closed_sold=4", "metric": 100.0},
    "G": {"pass": True, "detail": "density=100.0 far=100.0 pk1000=100.0", "metric": 100.0},
    "H": {"pass": True, "detail": "hours since last_seen (SLA 48h)", "metric": 0.1},
    "I": {"pass": True, "detail": "card_complete=35 of 35", "metric": 100.0},
    "J": {"pass": True, "detail": "deal_complete=35 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 100.0},
    "auctions_total": 35,
}

FINAL_STATE_WAKULLA = {
    "A": {"pass": True, "detail": "fc=8 td=36", "metric": 8},
    "B": {"pass": True, "detail": "verified=20 closed_sold=20", "metric": 100.0},
    "C": {"pass": False, "detail": "matched_clean=37", "metric": 84.1},
    "D": {"pass": True, "detail": "matched_any=44", "metric": 100.0},
    "E": {"pass": False, "detail": "parcel_linked=38", "metric": 86.4},
    "F": {"pass": True, "detail": "tier1_sold=20 closed_sold=20", "metric": 100.0},
    "G": {"pass": True, "detail": "density=97.1 far= pk1000=", "metric": 97.1},
    "H": {"pass": True, "detail": "hours since last_seen (SLA 48h)", "metric": 2.5},
    "I": {"pass": False, "detail": "card_complete=38 of 44", "metric": 86.4},
    "J": {"pass": False, "detail": "deal_complete=38 (triangle + two-arm CMA + ml_score + max_bid)", "metric": 86.4},
    "auctions_total": 44,
}

if __name__ == "__main__":
    import json
    print(json.dumps({"sumter": FINAL_STATE_SUMTER, "suwannee": FINAL_STATE_SUWANNEE, "wakulla": FINAL_STATE_WAKULLA}, indent=2))
