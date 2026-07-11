-- Gold Standard shard-3 (levy/suwannee/wakulla, dispatch b80c4c55-8ad7-41fb-86de-a1b33ecc95d5):
-- suwannee FC fabrication RE-PURGE + cron quarantine.
--
-- ROOT CAUSE (VERIFIED live 2026-07-11): scripts/shard1_run3534_suwannee_fc_fabrication_revert.py
-- (run3534, 2026-07-10) had already identified and purged 2 fictitious foreclosure auctions
-- (case_number SUWANNEE-FC-2026-001/002, parcel_id SUW-FC-BOOT-001/002) hardcoded by
-- scripts/shard5_run1524_suwannee_bootstrap.py, whose own docstring self-labels this data
-- "INFERRED ... B outcomes = INFERRED (past-due marked sold for bootstrap, not clerk-verified)".
-- That bootstrap script was, and still is, wired to run EVERY DAY at 05:00Z via
-- .github/workflows/shard5-run1524-daily.yml (job "suwannee-bootstrap"), so the run3534 revert
-- was silently undone the very next morning and every morning since. This session found the
-- 2 rows back in multi_county_auctions with created_at=2026-07-11T05:51:30Z (today's 05:00Z
-- cron), sold_amount_source='INFERRED:suwannee_bootstrap:run1524', data_source=NULL (every
-- other real suwannee row has a populated data_source), and mirrored into bid_decisions
-- (ids 139222/139231, pipeline_version=run338_shard28_v4, created_at=2026-07-11T08:42:10Z —
-- the J-generator picking up the re-fabricated rows a few hours later).
--
-- This is the same fabrication-recurrence failure class as R5 (envelope-conquest.yml
-- self-retriggering) flagged elsewhere in this campaign: a purge without killing the
-- generator is not a fix, it is a 24-hour snooze.
--
-- ADDITIONAL FINDING: 2 of suwannee's 9 real tax-deed parcels (10591001000 / case 4666,
-- 11016001003 / case 4667) still carried a zone_code from the SAME fabrication script
-- (parcel_zones.source='shard5_bootstrap_run1524', zone_code='AG', self-documented as
-- "INFERRED (standard FL zone types, not ordinance-verified)") even though 7 of 9 parcels
-- had already been correctly re-sourced via a real DOR-use-code crosswalk earlier today
-- (source='shard_gold_run3645_suwannee_zoning_real:2026-07-11:dor_usecode_to_district_map:...',
-- scripts/gold_standard_shard11_suwannee_a_i_fix.py). This was a partial ghost-success
-- inside a currently-PASSing G. Fixed live this session using the exact same live source and
-- methodology as the other 7 parcels: queried suwannee-search.gsacorp.io (the Suwannee
-- Property Appraiser's real livesearch API) for both addresses ("16112 164th" ->
-- 1104S12E10591001000, "20947 76th" -> 1402S11E11016001003), confirmed real assessed values
-- already matched DB ($63,581 / $39,666), and real DOR Use Code = "0200: MOBILE HOME" for
-- both -- which the existing crosswalk (USE_CODE_TO_DISTRICT in
-- scripts/gold_standard_shard11_suwannee_a_i_fix.py) maps to R1 (Single-Family Residential),
-- matching 5 of the other 7 already-fixed parcels that share the same use code.
--
-- ACTIONS TAKEN LIVE (via PostgREST, this file documents for replay):
--   1. UPDATE parcel_zones SET zone_code='R1', zone_name='Single-Family Residential',
--      source='shard_gold_run3645_suwannee_zoning_real:2026-07-11:dor_usecode_to_district_map:
--      use_code=0200: MOBILE HOME' WHERE id IN (821671, 821674).
--   2. DELETE FROM multi_county_auctions WHERE county='suwannee' AND case_number IN
--      ('SUWANNEE-FC-2026-001','SUWANNEE-FC-2026-002').
--   3. DELETE FROM bid_decisions WHERE case_number IN
--      ('SUWANNEE-FC-2026-001','SUWANNEE-FC-2026-002') (ids 139222, 139231).
--   4. QUARANTINED the recurrence source: removed the "suwannee-bootstrap" job from
--      .github/workflows/shard5-run1524-daily.yml entirely (h-freshness and the independent
--      osceola-cd-fix job, which is out of this shard's scope and was not touched, remain).
--      The script file itself (scripts/shard5_run1524_suwannee_bootstrap.py) is left in place,
--      unwired, as audit-trail precedent (same pattern as
--      scripts/shard1_run3534_suwannee_fc_fabrication_revert.py) -- do not re-wire it without
--      first rewriting it to scrape a real source.
--
-- pencil_dod_evaluate_county('suwannee') before -> after this session, both re-verified live:
--   A: PASS (fc=2, fake)      -> FAIL (fc=0, honest -- suwannee.realforeclose.com genuinely
--      has 0 live listings right now, confirmed separately this same day by
--      scripts/gold_standard_shard11_suwannee_a_i_fix.py's AJAX calendar probe)
--   B: FAIL (verified=0/2=0.0%, fake denominator) -> FAIL (verified=0/0=null, honest --
--      no real closed foreclosure sale exists for suwannee yet)
--   C: PASS 100.0 (11/11, 2 fake) -> PASS 100.0 (9/9, all real)
--   D: PASS 100.0 (11/11, 2 fake) -> PASS 100.0 (9/9, all real)
--   E: PASS 100.0 (11/11, 2 fake) -> PASS 100.0 (9/9, all real) -- unchanged
--   F: PASS (tier1_sold=2/2=100%, fake) -> FAIL (tier1_sold=0/0=null, honest)
--   G: PASS 100.0 (9/9 real parcels, but 2 zone_codes were fabricated) -> PASS 100.0
--      (9/9 real parcels, ALL zone_codes now real)
--   H: PASS (unchanged)
--   I: FAIL (card_complete=9 of 11, 81.8%) -> PASS (card_complete=9 of 9, 100.0%) -- the 2
--      rows that were pulling I below threshold were exactly the 2 fabricated FC rows
--      (no real parcel_id -> never zone-linked -> never card-complete); removing them
--      resolves I honestly rather than needing any new field backfill.
--   auctions_total: 11 -> 9 (correct honest denominator)
--   Net: 8/10 -> 7/10 raw count. This is an HONEST regression, matching the exact precedent
--   already established for levy (migrations/20260710_gold_standard_shard3_levy_fabrication_
--   purge.sql): the prior 8/10 rested on 2 fabricated letters (A, F) plus a partially-fake G;
--   the current 7/10 (C,D,E,G,H,I,J) is fully real, and I is a genuine new PASS gained by
--   removing the fabrication rather than backfilling data.
--
-- Per HARD GUARDRAILS ("PropertyOnion = litmus ONLY... fail-loud invariant... NEVER
-- fabricate") this purge-and-quarantine is mandatory, not discretionary.
-- ============================================================================

BEGIN;

UPDATE parcel_zones
SET zone_code = 'R1',
    zone_name = 'Single-Family Residential',
    source = 'shard_gold_run3645_suwannee_zoning_real:2026-07-11:dor_usecode_to_district_map:use_code=0200: MOBILE HOME'
WHERE id IN (821671, 821674)
  AND parcel_id IN ('11016001003', '10591001000');

DELETE FROM bid_decisions
WHERE case_number IN ('SUWANNEE-FC-2026-001', 'SUWANNEE-FC-2026-002');

DELETE FROM multi_county_auctions
WHERE lower(county) = 'suwannee'
  AND case_number IN ('SUWANNEE-FC-2026-001', 'SUWANNEE-FC-2026-002');

COMMIT;
