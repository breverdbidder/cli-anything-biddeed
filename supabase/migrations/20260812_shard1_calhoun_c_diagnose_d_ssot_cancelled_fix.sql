-- Gold Standard ULTRALOOP shard-1, dispatch 7323433f-7f95-4837-b952-1d569ec1acb6
-- county=calhoun, letter=C (D fixed as honest byproduct, C correctly stays FAIL)
--
-- BEFORE (pencil_dod_evaluate_county('calhoun'), live, 2026-08-12):
--   C: pass=false metric=87.5 detail="matched_clean=7"
--   D: pass=false metric=87.5 detail="matched_any=7"
--   auctions_total=8
--
-- ROOT CAUSE (live-verified this session, not carried over from a stale note):
-- Of 8 calhoun auction rows, 7 already carry parity_status in
-- {'matched_clean' w/ tier1 source, 'PARITY_OK'}, satisfying both the C
-- (matched_clean) and D (matched_any) filters in pencil_dod_evaluate_county's
-- prosrc (confirmed via pg_proc.prosrc read this session):
--   matched_clean := (parity_status='matched_clean' AND parity_source LIKE 'tier1%')
--                     OR parity_status IN ('PARITY_OK','CLERK_VERIFIED')
--   matched_any    := (parity_status IN ('matched_clean','matched_divergent') AND parity_source LIKE 'tier1%')
--                     OR parity_status IN ('PARITY_OK','CLERK_VERIFIED','CLERK_SSOT_CANCELLED')
--
-- The 8th row, case_number='546 OF 2024' (tax_deed, auction_status=CANCELLED,
-- data_source='calhoun_clerk_scrape', never propertyonion), carried
-- parity_status='PHANTOM_NOT_ON_CLERK' set by a 2026-08-11 reverify session.
-- That status string matches neither the C nor the D filter, so the row
-- counted against both metrics.
--
-- Live re-verification performed THIS session (2026-08-12), independent of
-- the 08-11 note:
--   1. Fetched https://calhounclerk.com/court-services/property-sales/tax-deed-sales/
--      (HTTP 200) and scanned the embedded case listing for "OF 2023/2024/2026"
--      patterns. Cases present: 171 OF 2023, 227 OF 2024, 268 OF 2023,
--      383 OF 2024, 621 OF 2024 (plus an unrelated 621 OF 2026). 546 OF 2024
--      is genuinely absent from the current listing.
--   2. Fetched https://calhounclerk.com/taxdeeds/546-of-2024/ directly ->
--      HTTP 301 redirecting to the site homepage, confirming the case page
--      was removed from the clerk's CMS (delisted), not merely hidden from
--      the index.
--
-- This is a genuine, confirmed clerk-side cancellation/delisting -- not a
-- scraper bug and not a PropertyOnion artifact. PropertyOnion / po_* fields
-- were NOT used as a source for this decision; data_source on the row
-- remains 'calhoun_clerk_scrape' throughout.
--
-- FIX: relabel the row with the existing CLERK_SSOT_CANCELLED status, which
-- IS already included in the D (matched_any) filter, honestly reflecting a
-- clerk-confirmed cancellation. Do NOT relabel it into the C (matched_clean)
-- set -- there is no live listing to cleanly match against, so C correctly
-- remains 7/8 (87.5%, FAIL). Forcing C to pass would require inventing a
-- live match that does not exist -- banned by this repo's fabrication rules.

UPDATE multi_county_auctions
SET parity_status = 'CLERK_SSOT_CANCELLED',
    parity_source = 'clerk_delisted:calhoun_taxdeeds_20260812_diagnose',
    parity_checked_at = now()
WHERE lower(county) = 'calhoun' AND case_number = '546 OF 2024';

-- AFTER (pencil_dod_evaluate_county('calhoun'), live, 2026-08-12):
--   D: pass=true  metric=100.0 detail="matched_any=8"   [FIXED]
--   C: pass=false metric=87.5  detail="matched_clean=7" [honestly unchanged --
--        no live clerk match exists for 546 OF 2024, so C is not gameable]
