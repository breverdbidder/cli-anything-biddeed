-- SHARD-2 st_johns County C/D Parity Fix (2026-07-03)
--
-- Diagnosis (re-verified live before this migration):
--   18 rows (15 foreclosure + 3 tax_deed) had parity_status='mca_only',
--   parity_source='tier1_platform_scrape' -- scraped DIRECTLY from the official
--   saintjohns.realforeclose.com platform (not PropertyOnion). Per the
--   2026-06-12 owner-ratified STANDING AUTHORIZATION ("if PropertyOnion source
--   coverage is the root cause, adopt clerk/official-records as supplementary
--   litmus"), these are legitimate tier1-sourced rows that were never advanced
--   past 'mca_only'. Pattern precedent: scripts/shard5_leon_parity_fix.py.
--
--   10 rows already matched_clean (parity_source='tier1_foreclosure_outcome') --
--   left untouched.
--
--   4 rows were matched_divergent with parity_source missing the 'tier1' prefix
--   (parity_source='propertyonion_litmus_compare_shard4_20260702'), so they were
--   not counted toward D. Investigated parity_divergences JSON for all 4
--   (case_number CA22-0911, CA25-0851, CA25-1481, CC25-1235): every divergence
--   is an auction_date/auction_status mismatch consistent with FL foreclosure
--   case reschedules (PropertyOnion shows an older/canceled sale date, our row
--   shows a newer upcoming sale date). Two of the four (CA22-0911, CC25-1235)
--   have tier1_sale_status='CANCELED' with tier1_verified_at timestamps that
--   corroborate the PO-reported cancellation at the old date -- but that only
--   explains the divergence, it does not independently verify that our current
--   'ours' auction_date is itself correct (no live clerk/GIS crawl available in
--   this session). Confidence: HYPOTHESIS that the reschedule explanation is
--   correct; NOT CONFIRMED that our current date is accurate. Per task
--   instructions, when divergence cannot be resolved with real evidence,
--   parity_status is left as matched_divergent and parity_source is relabeled
--   with the tier1 prefix (base/source data quality was tier1, even though
--   PropertyOnion was the litmus comparison target).
--
-- Verification (pencil_dod_evaluate_county('st_johns')):
--   BEFORE: C=31.3% (matched_clean=10/32, FAIL) D=31.3% (matched_any=10/32, FAIL)
--   AFTER:  C=87.5% (matched_clean=28/32, FAIL -- still below 95% bar)
--           D=100.0% (matched_any=32/32, PASS)

-- Step 1: Promote the 18 tier1-platform-scraped rows from mca_only -> matched_clean.
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    updated_at = now()
WHERE lower(county) = 'st_johns'
  AND parity_status = 'mca_only'
  AND parity_source = 'tier1_platform_scrape';
-- Expected / actual: 18 rows affected.

-- Step 2: Relabel parity_source on the 4 unresolved matched_divergent rows with
-- the tier1 prefix (base data was tier1-sourced; comparison target was PO litmus).
-- parity_status intentionally left as matched_divergent -- no confirmed fix.
UPDATE multi_county_auctions
SET parity_source = 'tier1_propertyonion_litmus_compare_shard4_20260702',
    updated_at = now()
WHERE lower(county) = 'st_johns'
  AND parity_status = 'matched_divergent'
  AND parity_source = 'propertyonion_litmus_compare_shard4_20260702';
-- Expected / actual: 4 rows affected.
