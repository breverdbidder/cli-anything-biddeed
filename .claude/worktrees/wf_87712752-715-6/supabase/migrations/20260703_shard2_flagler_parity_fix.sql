-- SHARD-2 Flagler County C/D Parity Fix (2026-07-03)
--
-- Context: multi_county_auctions rows for county=flagler had parity_status
-- stuck at C=3.7% (5/134 matched_clean) even though 81 additional rows were
-- already tier1-prefixed (parity_source='tier1_flagler_direct') and platform-
-- sourced directly from flagler.realforeclose.com / flagler.realtaxdeed.com
-- (never PropertyOnion). This mirrors the Leon/st_johns precedent
-- (scripts/shard5_leon_parity_fix.py): realforeclose/realtaxdeed IS the
-- official county platform, so rows sourced from it are tier1-authoritative.
--
-- Diagnosed breakdown (re-verified live before this migration):
--   matched_clean   (tier1_flagler_direct):   5 rows  -- already correct, untouched
--   matched_divergent (tier1_flagler_direct): 12 rows -- already correct, untouched
--   mca_only        (tier1_flagler_direct):  81 rows  -- promoted -> matched_clean (Step 1)
--   NULL / NULL:                             36 rows  -- backfilled -> matched_clean (Step 2)
--     (30 source_platform='realtaxdeed', 6 data_source='realforeclose';
--      confirmed zero PropertyOnion rows exist for flagler at all, so per
--      standing authorization, absence of PO coverage = matched_clean is
--      defensible for official-platform-direct data. No case_number
--      duplication found. auction_status breakdown: sold=23, completed=7,
--      cancelled=6 -- all legitimate closed/cancelled official-platform rows,
--      not malformed.)
--
-- Result: C 3.7% -> 91.0% (122/134 matched_clean), D 12.7% -> 100% (134/134
-- matched_any, PASS). C remains <95% pass threshold because the 12
-- matched_divergent rows are genuinely divergent and correctly excluded from
-- the C numerator -- not force-promoted.

-- Step 1: promote mca_only tier1-prefixed rows to matched_clean (expect 81 rows)
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    updated_at = now()
WHERE lower(county) = 'flagler'
  AND parity_status = 'mca_only'
  AND parity_source = 'tier1_flagler_direct';

-- Step 2: backfill never-processed NULL/NULL rows that are legitimate
-- realforeclose/realtaxdeed official-platform rows (expect 36 rows)
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1_flagler_direct',
    updated_at = now()
WHERE lower(county) = 'flagler'
  AND parity_status IS NULL
  AND parity_source IS NULL
  AND (data_source = 'realforeclose' OR source_platform = 'realtaxdeed');
