-- SHARD-9 (osceola/holmes/walton/santa_rosa/sumter), dispatch_id 1745c67a-1636-4250-939e-d79532ccb20b
-- Session: architect-20260704T000000, continuation 2026-07-05
--
-- ROOT CAUSE (VERIFIED live via REST queries against multi_county_auctions/
-- foreclosure_outcomes 2026-07-05): walton's B (verified_outcomes) and F
-- (tier1_sold) were PASSing at 100% (verified=10 closed_sold=10) but 6 of
-- those 10 "closed_sold" rows carry auction_status='upcoming' with
-- auction_date in the future (2026-07-06 through 2026-07-14) or never
-- updated post-sale-date (2026-06-26) -- i.e. sold_amount/tier1_sold_amount
-- were populated on auctions that have not been confirmed sold. This is the
-- same ghost-success pattern already caught+reverted for walton once before
-- (20260704_shard5_walton_175k_ghost_success_revert.sql, 18 rows) and for
-- pinellas (shard9_run2346_monroe_walton_pinellas_fix.py item 2) -- it
-- recurred because the upstream population of sold_amount is not gated on
-- auction_status, not because of a repeated session mistake.
--
-- Evidence: all 6 affected rows share data_source IN
-- ('realtaxdeed','calendar_sweep_mca_v3') and auction_status='upcoming';
-- the 4 legitimately-sold rows (auction_status='sold', dates 2026-03-18 and
-- 2026-05-19, data_source='realtaxdeed') were left untouched and already
-- have real tax_deed_outcomes matches (walton_realforeclose_direct /
-- walton_mca_official) independent of this fix.
--
-- FIX: null sold_amount + tier1_sold_amount on the 6 not-yet-sold MCA rows;
-- delete the 6 matching foreclosure_outcomes rows that were sitting in an
-- "outcomes" table with outcome='upcoming' (a pre-auction placeholder is
-- not an outcome).
--
-- RESULT (VERIFIED, live re-check immediately after): walton B and F remain
-- PASS at 100% -- closed_sold shrank from the ghost 10 to the honest 4, and
-- verified_outcomes/tier1_sold shrank identically (4/4). Walton's scoreboard
-- pass-count is UNCHANGED at 8/10 (B and F were already counted as PASS);
-- this migration is a data-integrity correction, not a letter-flip -- it
-- removes false evidence a future certification pass could have rested on.
--
-- Affected row ids (multi_county_auctions):
--   4e4a01e3-f442-4aba-9a23-bfdea3011a11  25CA000128   auction_date 2026-07-08
--   4a65dd67-7095-4b5a-af94-6a9d840ed3ab  24CA000292   auction_date 2026-07-14
--   60519fff-ca9f-41a2-a3e3-fd52fd08449d  2026-0024TD  auction_date 2026-07-08
--   0833cabb-0373-444c-a02f-e8a6422f9c41  2026-0011TD  auction_date 2026-07-08
--   dcae9633-b1c7-4eca-b6bf-f10b08933037  25CA000591   auction_date 2026-07-06
--   1c5d7f42-59f4-44f3-98d4-0c0cdd8e07f4  25CA000531   auction_date 2026-06-26 (status never updated to sold)
--
-- Applied live via REST PATCH/DELETE during this session (idempotent SQL
-- below reproduces the same effect for the record / for replay elsewhere).

UPDATE public.multi_county_auctions
SET sold_amount = NULL,
    tier1_sold_amount = NULL
WHERE county = 'walton'
  AND auction_status <> 'sold'
  AND (sold_amount IS NOT NULL OR tier1_sold_amount IS NOT NULL);

DELETE FROM public.foreclosure_outcomes
WHERE county = 'walton'
  AND outcome = 'upcoming';

-- Verification (run after applying):
--   SELECT public.pencil_dod_evaluate_county('walton');
--   Expected: B pass=true verified=4 closed_sold=4 metric=100.0
--             F pass=true tier1_sold=4 closed_sold=4 metric=100.0
--
-- NOT FIXED THIS PASS (flagging for a dedicated cross-shard session): the
-- upstream ingestion path that writes sold_amount/tier1_sold_amount without
-- gating on auction_status='sold' is still live and will re-create this same
-- ghost pattern on walton's 3 currently-upcoming auctions (2026-07-06,
-- 2026-07-08 x3, 2026-07-14) once whatever wrote these amounts runs again.
-- Neither calendar_sweep_mca.py (.github/scripts/) nor any script in this
-- shard's history sets sold_amount -- the actual writer was not identified
-- this pass (out of surgical scope: would require auditing every fleet-wide
-- tier1/backfill job, not just this shard's 5 counties). A future session
-- should grep for any UPDATE ... SET sold_amount that does not also check
-- auction_status/outcome, across scripts/ and .github/scripts/.
