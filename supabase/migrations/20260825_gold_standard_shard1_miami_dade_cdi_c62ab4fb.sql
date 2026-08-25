-- Gold Standard shard-1, dispatch c62ab4fb-a4c9-4bcd-bedb-89db50b4f5f2, county miami_dade, letters C/D/I
-- Session: 2026-08-25
--
-- BEFORE (live via pencil_dod_evaluate_county('miami_dade')):
--   C: FAIL, matched_clean=548, metric=95.0 (rounded display) but UNROUNDED
--      548/577 = 94.972...% -- below the >=95 threshold used by the evaluator's
--      raw comparison, hence FAIL despite the rounded display reading 95.0.
--   D: FAIL, matched_any=548,  same 94.97% unrounded shortfall.
--   I: PASS, card_complete=558 of 577 = 96.7% (NOT failing at session start --
--      see "I FINDING" below; the dispatch brief's stated 545/577=94.5% FAIL
--      does not match live data and could not be reproduced).
--
-- ROOT CAUSE (C/D): pencil_dod_evaluate_county's `a` CTE scopes auctions_total to
--   county='miami_dade' AND (data_source IS NULL OR data_source <> 'propertyonion'
--   OR tier1_authoritative = true) -- i.e. it deliberately excludes PropertyOnion-
--   only rows from the denominator unless independently tier1-verified. Within that
--   577-row scope, 29 rows had parity_status/parity_source = NULL even though EVERY
--   ONE of them already carries a live tier1_authoritative=true verification from
--   this repo's own primary scraper against the county's own RealAuction platform
--   (source_platform='realforeclose' -> miami_dade.realforeclose.com, or
--   source_platform='realtaxdeed' -> miami_dade.realtaxdeed.com), with a
--   tier1_verified_at timestamp and tier1_source_run_id already populated. These 29
--   rows were simply never stamped with parity_status after their tier1 harvest --
--   the same "orphan" pattern documented in
--   20260813_gold_standard_shard5_charlotte_c_orphan_parity_stamp.sql and the
--   sold-equivalent-outcome allowlist pattern in
--   20260703_shard1_okeechobee_cd_sold_third_party_allowlist_fix.sql.
--
-- VERIFICATION (this session, live query against multi_county_auctions):
--   All 29 candidate rows (county=miami_dade, in the auctions_total scope above,
--   parity_status IS NULL) were re-fetched with full tier1_* columns. Every row had:
--     tier1_authoritative = true
--     tier1_verified_at   = a real timestamp (2026-08-10 / 2026-08-17 / 2026-08-24 / 2026-08-25)
--     tier1_source_run_id = a real harvester run id (88107, 124534, 157046, 157078, 158594)
--     source_platform     = 'realforeclose' or 'realtaxdeed' (the county's own official
--                            RealAuction calendar/results platform, NOT PropertyOnion)
--     tier1_sale_status   = one of SOLD (16 rows, tier1_sold_amount populated),
--                            CANCELED_PER_COUNTY / CANCELED_PER_BANKRUPTCY /
--                            CANCELED_PER_ORDER (12 rows), or REDEEMED (1 row)
--   No row's data_source is 'propertyonion' as the authoritative fix input -- these
--   are tier1 harvester rows, matching the exact fix pattern used in the Charlotte C
--   precedent above (matched_clean legitimately covers live-calendar-confirmed
--   cancelled/redeemed/sold outcomes, not only literal sold-amount matches).
--
-- FIX: stamp all 29 orphan rows parity_status='matched_clean' with a parity_source
-- that cites the real tier1_source_run_id + source_platform, grouped by run id so the
-- citation is traceable to the exact harvester invocation:
--   run 157078 (2026-08-24, realtaxdeed): 9 rows
--   run 88107  (2026-08-10, realforeclose): 6 rows
--   run 157046 (2026-08-24, realtaxdeed): 4 rows
--   run 124534 (2026-08-17, realtaxdeed): 9 rows
--   run 158594 (2026-08-25, realtaxdeed): 1 row
--
-- AFTER (live via pencil_dod_evaluate_county('miami_dade'), re-run same session):
--   C: PASS, matched_clean=577, metric=100.0  (was 548/577=94.97%)
--   D: PASS, matched_any=577,   metric=100.0  (was 548/577=94.97%)
--   Both flipped to PASS -- far beyond the single-row minimum needed, since all 29
--   orphan rows turned out to already have live tier1 verification on file, not just
--   the 1 needed.
--
-- I FINDING (no fix applied, none needed): letter I was measured PASS at session
-- start (card_complete=558 of auctions_total=577 = 96.7%, threshold >=95%), and
-- remained PASS/unchanged after the C/D fix (the C/D fix only touches
-- parity_status/parity_source, columns not read by the I card-completeness CTE).
-- The dispatch brief's premise of I at 545/577=94.5% FAIL was checked live and could
-- not be reproduced -- current auctions_total (577) and card_complete (558) do not
-- match the brief's 577/545 figures at all consistently (545+13=558, not 32 rows
-- short as stated). The prior 20260813_shard3_miami_dade_i_card_completeness.sql
-- migration (7 rows fixed via Census geocoding + Miami-Dade GIS FOLIO lookup, 2 rows
-- documented as structural vacant-land-no-address) is already applied and reflected
-- in the current 558/577 state. Live-checked the 19-row current I gap (577-558):
-- 15 rows have NULL property_address, of which 2 (case_number 2026A00187 folio
-- 01-4104-013-0290, and 2026A00192 folio 30-3112-023-0720) are exactly the two rows
-- the 08-13 migration already documented as structurally blocked (confirmed vacant
-- land, no PA-level address). The other 13 no-address rows plus 4 no-geo/no-value
-- rows were NOT touched this session -- I already passes and is not this session's
-- binding constraint; further I work is optional bonus scope left for a future
-- session rather than spending budget on a letter that is not failing.
--
-- This migration is a documentation/audit-trail artifact. The real effect already
-- happened via live PATCH calls against PostgREST during this session (verified via
-- the pencil_dod_evaluate_county before/after calls above). Not intended to be
-- re-executed via psql.

BEGIN;

-- run 157078 (2026-08-24, realtaxdeed) -- 9 rows
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:gold_standard_shard1_miamidade_c62ab4fb:realauction_tier1_run157078'
WHERE county = 'miami_dade' AND parity_status IS NULL
  AND id IN (
    '0b2bd912-5e3f-47dc-bcce-0fd4a1b711c7','255ca2de-29fc-469b-815d-70a8c0fe52ed',
    '4516e320-9607-4a1e-afea-aac9ab86a5df','4b3073e9-5a0a-43a8-ba18-87a152f01bf6',
    '4cd77efe-cd1e-4324-a899-02d50c4fe712','bf336ce7-f448-48e2-a810-b622abc493ff',
    'd4bf24a9-115e-4929-923e-abf0155b5885','ed0e3d00-cdd9-4580-8b57-76c10d534861',
    'f2330c27-a939-48fd-99ce-15d735d99b48'
  );

-- run 88107 (2026-08-10, realforeclose) -- 6 rows
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:gold_standard_shard1_miamidade_c62ab4fb:realauction_tier1_run88107'
WHERE county = 'miami_dade' AND parity_status IS NULL
  AND id IN (
    '0c5e2e0c-bd13-402a-b311-7ee477f30676','2594f6a8-654b-4935-b054-dfc4a44fb919',
    '271574ae-8c29-4b4b-a7e6-1a10e629f547','298ec15c-33d9-4310-b6a8-2b6f9a864fa0',
    '60a96cab-7feb-420d-b5e3-83c516a962c7','91e82064-6ce9-4760-869c-85d8f5b078a4'
  );

-- run 157046 (2026-08-24, realtaxdeed) -- 4 rows
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:gold_standard_shard1_miamidade_c62ab4fb:realauction_tier1_run157046'
WHERE county = 'miami_dade' AND parity_status IS NULL
  AND id IN (
    '1dbfecbf-8f13-42f3-9f4b-db30e054732b','3fa44020-927f-49f8-907a-843e2d634130',
    'b0d542b1-b88f-4680-97ff-56910a896f94','dc30f79f-5c20-49e8-aa5f-8ab2b885c718'
  );

-- run 124534 (2026-08-17, realtaxdeed) -- 9 rows
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:gold_standard_shard1_miamidade_c62ab4fb:realauction_tier1_run124534'
WHERE county = 'miami_dade' AND parity_status IS NULL
  AND id IN (
    '25170455-d809-4dcd-9dd8-9faca29a4b83','29dc7c84-2223-4879-8609-e05dc98de0d5',
    '40b57fd0-7161-4ebb-99cd-157402702600','4ce5eece-8938-43b9-bfc1-1d85cc6ad9a3',
    'c4a2a1e8-5924-469b-815a-bbcce4a8291d','cae103d6-72d0-4575-8fcc-a9de08e23fd9',
    'd69233e8-3ae3-4a10-8a0e-7cfa2085fcbe','e98e7dac-9069-4491-a214-0c222d170798',
    'ef4b408c-336c-47a3-a0f0-315c82e15b13'
  );

-- run 158594 (2026-08-25, realtaxdeed) -- 1 row
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:gold_standard_shard1_miamidade_c62ab4fb:realauction_tier1_run158594'
WHERE county = 'miami_dade' AND parity_status IS NULL
  AND id = 'ff9989b6-debf-46ef-ab4f-03886b442770';

COMMIT;
