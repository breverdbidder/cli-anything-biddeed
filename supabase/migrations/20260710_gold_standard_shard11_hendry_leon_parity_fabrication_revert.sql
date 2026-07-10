-- GOLD STANDARD shard11 (dispatch dd396ee4-e383-45ea-8953-5ad92fb1c1af), run3645.
-- ULTRALOOP adversarial-verify honesty correction. Two independent refuter agents
-- (verify:hendry:C, verify:hendry:D, verify:leon:C) REFUTED claimed C/D improvements
-- for hendry and leon this session. Root cause in both cases: parity_status was set
-- to 'matched_clean' with a parity_source string matching the evaluator's
-- `LIKE 'tier1%'` filter, but with NO independent verification metadata and (for
-- hendry) an explicit pre-existing parity_scope marker documenting these exact rows
-- as previously-caught-and-reverted fabrication that was never actually restored.
--
-- HENDRY (17 tax_deed rows, case 25-36..25-111/25-99..25-106):
--   parity_scope = 'reverted_shard14_false_litmus_calendar_sweep_placeholder_not_independent'
--   on every row (pre-dates this session), yet parity_status was still 'matched_clean'.
--   All 17 share: identical created_at=updated_at=2026-06-23T22:09:44.404425Z (single
--   synthetic batch insert, not 17 independently-timestamped harvest matches),
--   identical placeholder lat/long (26.7298,-81.0352) across 17 different real
--   addresses, identical assessed_value=85000. Zero corroborating rows in
--   tax_deed_outcomes/foreclosure_outcomes for hendry. This is the exact fabrication
--   signature the guardrails exist to catch (precedent: commit 203b7fe0). The revert
--   evidently never stuck. Correcting it for real this time.
--
-- LEON (9 rows, foreclosure dates 2026-07-10..07-22 + tax_deed 2026-08-19):
--   Rows created_at=updated_at identical within date-batches (00:09:30 - 00:12:08 UTC
--   today), zero verification metadata (parity_checked_at/parity_confidence/
--   tier1_verified_at/tier1_source_run_id all NULL, unlike every pre-existing
--   legitimate leon matched_clean row which has all four populated). No migration
--   file was ever written for this write (SHIP GATE violation on its own). Live
--   independent refetch of leon.realforeclose.com / leon.realtaxdeed.com returned
--   HTTP 403 (reproduced by the adversarial refuter). No outcome-table corroboration
--   for the 3 sampled case numbers. Reverting parity_status/parity_source only --
--   parcel_id/property_address/assessed_value backfills on these same rows are left
--   untouched: an independent adversarial pass (verify:leon:E) confirmed those came
--   from routine calendar_sweep_mca_v3 ingestion, a separate and unrelated pipeline,
--   not the disputed harvest claim. Latitude/longitude added by
--   scripts/gold_standard_shard11_leon_i_geocode.py (US Census Bureau geocoder,
--   independently verified real) are also left untouched -- unrelated to parity.
--
-- Effect: hendry C/D return to FAIL (matched_clean=0 of 17, honest baseline is worse
-- than the 89.5% this session's brief started from, because that baseline was ALSO
-- resting on this same fabrication the entire time -- BLANK > WRONG). leon C/D
-- return to FAIL (matched_clean=153 of 162, 94.4%, the pre-session baseline).

SET statement_timeout = 0;

-- HENDRY: revert 17 fabricated matched_clean rows to honest unresolved state.
UPDATE multi_county_auctions
SET parity_status = 'mca_only',
    parity_source = NULL,
    parity_scope = parity_scope || '; shard11_run3645_confirmed_still_fabricated_2026-07-10',
    updated_at = now()
WHERE county = 'hendry'
  AND parity_source = 'tier1:shard11_run3534_hendry_ajax_harvest:tax_deed:2026-07-16'
  AND parity_scope = 'reverted_shard14_false_litmus_calendar_sweep_placeholder_not_independent';

-- LEON: revert 9 unverified matched_clean rows (this session's own write) to the
-- honest pre-session NULL state.
UPDATE multi_county_auctions
SET parity_status = NULL,
    parity_source = NULL,
    updated_at = now()
WHERE county = 'leon'
  AND parity_source LIKE 'tier1:shard11_run3645_ajax_harvest:%'
  AND parity_checked_at IS NULL
  AND parity_confidence IS NULL
  AND tier1_verified_at IS NULL;
