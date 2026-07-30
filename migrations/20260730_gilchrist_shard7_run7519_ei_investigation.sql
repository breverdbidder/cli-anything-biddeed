-- GOLD STANDARD SHARD-7 run-7519 — gilchrist — E/I investigation + ULTRALOOP audit
-- dispatch_id: 61f11933-122d-4474-acf3-65e71d7a707c
-- session: architect-20260730T160000
--
-- ENTRY STATE (from brief, consistent with 2026-07-25 verified):
--   E: FAIL metric=57.1 [parcel_linked=8 of 14]
--   I: FAIL metric=42.9 [card_complete=6 of 14]
--
-- ANALYSIS (from reading 4 prior session reports + gilchrist-specific migrations):
--
-- The 8/14 parcel_linked and 6/14 card_complete gaps break down as follows:
--
-- E GAP (6 rows with no parcel_id):
--   212025CA000064CAAXMX  (09/14/2026 auction)
--   212026CA000004CAAXMX  (09/14/2026 auction)
--   212025CA000042CAAXMX  (09/14/2026 auction)
--   212025CA000033CAAXMX  (09/28/2026 auction)
--   212025CA000070CAAXMX  (09/28/2026 auction)
--   212025CA000043CAAXMX  (10/12/2026 auction)
--   (Note: 26-0036-CAAXMX / 10/26/2026 case also potentially unlinked — varies by session)
--
--   ROOT CAUSE (VERIFIED across 2 independent sessions, 27+ research agents combined):
--   gilchrist.realforeclose.com AJAX listings expose a generic qpublic.schneidercorp.com
--   search page link (Q=548715190, identical href across all cases on the same auction
--   date), not a per-parcel deep link. qpublic.net is Cloudflare-blocked (403) to
--   automated requests. The platform genuinely does NOT publish parcel data for these
--   foreclosure listings before the auction date itself.
--
-- I GAP (additional 2 rows beyond the 6 E failures):
--   26-0005-TD: parcel_id="171015" (malformed/truncated — does not resolve in GIS)
--     Strong candidate from floridaparcels.com: "171015005100000180"
--     "1202 SW FOURTH AVE, TRENTON, FL 32693", owner "JS REAL PROPERTIES LLC TRUSTEE"
--     INFERRED — not confirmed against gilchristclerk.com (403-blocked) or GIS
--     (requires GIS network access). Cannot write without confirmation.
--
--   212025CA000069CAAXMX: parcel_id=11-10-16-0552-0010-0060 (WRONG)
--     GIS lookup of that STRAP returns: use_dscr=VACANT, tax_val=$1,300, Newberry FL
--     But DB row has property_address="7439 SE 78 PL, TRENTON", assessed_value=$183,373
--     Material inconsistency — existing parcel_id was likely mismatched in an earlier
--     session. Cannot write a corrected parcel without GIS address search.
--
-- THIS SESSION'S ACTIONS:
-- 1. No DB writes can be made from this sandbox (Python execution blocked,
--    SUPABASE_KEY not available in this runner context).
-- 2. The fix script scripts/gilchrist_shard7_run7519_ei_fix.py was written and
--    committed. It implements:
--    A) RealAuction AJAX re-harvest for all 6 unlinked foreclosure cases
--       (parcel data may now be published closer to auction dates: 09/14 is
--       ~6 weeks away at time of writing 2026-07-30)
--    B) GIS address search for 26-0005-TD ("1202 SW FOURTH AVE" or "1202 SW 4TH")
--    C) GIS address search for 212025CA000069CAAXMX ("7439 SE 78 PL")
--    D) Fail-loud: does not write placeholders; reports unresolved rows explicitly
--
-- NEXT SESSION MUST-DO:
-- 1. Run scripts/gilchrist_shard7_run7519_ei_fix.py with SUPABASE_KEY set
--    AND network access to gis1.hcpao.org (TLS cert may need --insecure or OS CA update)
-- 2. The 09/14/2026 auction is 45 days away — RealAuction may now list parcel data
-- 3. If GIS is unreachable again, try gilchristclerk.com/tax-deeds/ for 26-0005-TD
--    (was 403 in prior sessions — rotating UA or Firecrawl may work if credits restored)

SET statement_timeout = 0;

-- ULTRALOOP audit entries for this session
-- These document the dead-end investigation (survived=false = no fix claimed)
-- Required by the certification gate: all letters need audit rows within 7 days
INSERT INTO gold_standard_ultraloop_audit (
    dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived
)
VALUES
(
    '61f11933-122d-4474-acf3-65e71d7a707c', 'fallback', 'gilchrist', 'E',
    'Shard-7 run-7519 (2026-07-30): E FAIL at 57.1% (8/14 parcel_linked). Six unlinked rows are foreclosure cases whose RealAuction platform listings do not expose per-parcel data (generic qpublic link Q=548715190, same across all cases on the same auction date). This finding is confirmed by 2 prior independent sessions (dispatch 28bd9542 run 6288 with 18 agents + dispatch 5269ffd2 run 6354 with 9 agents). This session could not execute the fix script (Python blocked in runner, SUPABASE_KEY not available). The script scripts/gilchrist_shard7_run7519_ei_fix.py was written and committed for the next session with proper credentials. Approaching auction dates (09/14, 09/28/2026) may now carry parcel data — re-harvest recommended as first action next session.',
    '{"tag":"VERIFIED","evidence":"prior_sessions_28bd9542_and_5269ffd2_both_confirmed_platform_gap","sessions_count":2,"agents_used":27,"no_write_made":true,"script_committed":"scripts/gilchrist_shard7_run7519_ei_fix.py","blocker":"runner_missing_supabase_key"}',
    false
),
(
    '61f11933-122d-4474-acf3-65e71d7a707c', 'fallback', 'gilchrist', 'I',
    'Shard-7 run-7519 (2026-07-30): I FAIL at 42.9% (6/14 card_complete). Blocked by E (parcel_id required for card completeness) plus 2 specific bad rows: (1) 26-0005-TD has malformed parcel_id "171015" — does not resolve in GIS; strong candidate 171015005100000180 found on floridaparcels.com but not confirmed against clerk records (gilchristclerk.com 403-blocked in prior sessions). (2) 212025CA000069CAAXMX has wrong parcel_id 11-10-16-0552-0010-0060 — GIS resolves this STRAP to a $1,300 vacant lot in Newberry FL, inconsistent with the DB row showing $183,373 SFH at "7439 SE 78 PL, TRENTON". Neither bad row can be safely written without GIS network access for address re-derivation. No write made this session.',
    '{"tag":"VERIFIED","evidence":"prior_sessions_28bd9542_verified_parcel_mismatch_212025CA000069CAAXMX_and_bad_26_0005_TD","no_write_made":true,"specific_blockers":{"26-0005-TD":"malformed_parcel_171015","212025CA000069CAAXMX":"wrong_parcel_vacant_lot_mismatch"},"script_committed":"scripts/gilchrist_shard7_run7519_ei_fix.py"}',
    false
)
ON CONFLICT DO NOTHING;

-- Verification: confirm ULTRALOOP audit rows were inserted
-- SELECT county_slug, letter, survived, created_at
-- FROM gold_standard_ultraloop_audit
-- WHERE dispatch_id = '61f11933-122d-4474-acf3-65e71d7a707c'
-- ORDER BY letter;
--
-- Expected: 2 rows (E and I, both survived=false — honest dead-end documentation)
