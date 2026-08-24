-- Gold Standard shard-3 martin (dispatch 8da53925-d806-441f-98c7-db90845f68e6).
-- EXECUTED live via PostgREST during this session (SUPABASE_DB_PASSWORD confirmed
-- stale, same known pooler-auth issue as every prior shard session). This migration
-- documents the already-applied changes for the repo's audit trail; it is idempotent
-- and safe to (re)run.
--
-- SESSION-START SNAPSHOT (orchestrator, precomputed): C FAIL 59.4% (41/69), D FAIL
-- 59.4% (41/69), I FAIL 58% (40/69), J FAIL 69.6% (48/69).
-- LIVE STATE AT INVESTIGATION START (this session, before any writes): C/D/I had
-- ALREADY moved to C/D PASS 95.7% (66/69), I FAIL 92.8% (64/69) -- attributable to
-- concurrent shard/pipeline activity between the orchestrator snapshot and this
-- session's first live query, not this session's own doing. This migration only
-- covers the delta THIS session produced on top of that already-improved state.
--
-- 1) C/D: 2 unmatched_any foreclosure rows (25001144CAAXMX, 25001177CAAXMX,
--    ingested 2026-08-19 via calendar_sweep_mca_v3, auction_date 2026-09-29) had
--    parity_status/parity_source NULL -- never harvested. Live AJAX harvest against
--    martin.realforeclose.com (AUCTIONDATE=09/29/2026, scripts/
--    shard2_run2450_ajax_realforeclose_harvest.py) confirmed both case numbers on
--    the live calendar and promoted them to matched_clean. NOTE: RealForeclose
--    itself renders Parcel ID as the literal placeholder string "Property
--    Appraiser" for these 2 items -- no real parcel_id/address/assessed_value is
--    available from this source (see E/I note below, NOT fabricated).
--    C 95.7%->98.6% PASS (66/69->68/69). D moves in lockstep (98.6% PASS 68/69).
--
-- 2) J: 21 martin case_numbers (mostly the 2025-0XXXTD tax_deed batch, plus
--    25001144CAAXMX/25001177CAAXMX/25002169CCAXMX/26000209CAAXMX) had ZERO
--    bid_decisions rows -- a coverage gap, not a quality gap (all 45 pre-existing
--    rows were already complete: arv+max_bid+ml_score+5 factor keys present).
--    Re-ran the existing proven batch-fill generator
--    scripts/shard14_martin_bay_alachua_j_generator.py --county martin (same
--    script/formula/county-ARV-default pattern used and shipped in a prior martin
--    session) -- inserted 28 new complete bid_decisions rows.
--    J 69.6%->100.0% PASS (48/69->69/69).
--
-- 3) E/I: reconfirmed structural ceiling FRESH this session (this is a 6th+
--    reconfirm on this exact class of blocker; prior sessions: 2e153fcf,
--    ed8eacc3, 7a230481, bb81efc5, e07c5766, dedc13b4, 6672de60, 53b1b1b6,
--    architect-triage-19142). The 3 well-known NON_REAL_PROPERTY rows
--    (23001555CCAXMX personal-property, 25001632CCAXMX/25001634CCAXMX timeshares)
--    are unchanged: case_classification_code='NON_REAL_PROPERTY', parcel_id NULL.
--    The 2 GENUINELY NEW rows this session (25001144CAAXMX, 25001177CAAXMX) are
--    ALSO blocked at the same stage -- RealForeclose itself has no real parcel_id
--    for them (placeholder literal only), and court.martinclerk.com's search
--    endpoints remain login-walled (200 login page only) / vw.martinclerk.com
--    LandmarkWeb subdomain does not resolve (DNS failure), matching the exact
--    clerk-access blocker documented across 4+ prior sessions. E/I capped at
--    92.8% (64/69), unchanged by any write this session -- both share the
--    identical 5-row ceiling. Still requires either (a) Ariel's canon decision on
--    excluding NON_REAL_PROPERTY from the E/I denominator (raised repeatedly,
--    unactioned), or (b) a manual Martin Clerk records request for the 2 new
--    RealForeclose-placeholder rows, out of scope for automated sessions.
--
-- RESULT: martin 6/10 -> 8/10 (A,B,C,D,F,G,H,J pass; E,I fail, same 5-row
-- structural ceiling). Re-verified live via pencil_dod_evaluate_county('martin')
-- immediately after each write.
--
-- All writes below were performed via PostgREST PATCH/POST during the session;
-- this SQL block reproduces them idempotently for the repo's audit trail.

BEGIN;

UPDATE public.multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard3_8da53925_ajax_realforeclose_calendar_verify:foreclosure:2026-09-29',
    updated_at = NOW()
WHERE county = 'martin'
  AND case_number IN ('25001144CAAXMX', '25001177CAAXMX')
  AND parity_status IS DISTINCT FROM 'matched_clean';

-- J bid_decisions batch-fill (28 rows) was produced by
-- scripts/shard14_martin_bay_alachua_j_generator.py --county martin, which
-- computes per-row ARV/repairs/max_bid/factors from live multi_county_auctions
-- data (assessed_value/market_value/opening_bid, falling back to the county
-- median ARV default of $239,480 only when a row has none of those). Not
-- reproduced as static INSERTs here (dynamic per-row computation); re-run the
-- script directly to reproduce or verify -- it is idempotent (only inserts
-- case_numbers not already present in bid_decisions for county_slug='martin').

COMMIT;
