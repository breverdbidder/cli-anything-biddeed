-- Clay County: reclassify tier1_only -> matched_clean for rows with a genuine
-- exact case_number match in tax_deed_outcomes (real tier1 clerk/official-records
-- source), where sold_amount already equals tier1_sold_amount (independently
-- verified, already counted in B/F closed_sold=11 / tier1_sold=11).
--
-- Root cause (verified live 2026-07-04): scripts/shard5_s373_goldstandard.py's
-- fix_cd_parity() has an early-skip guard ("if matched_clean > 0: skip") that
-- never re-ran for clay because clay already had 17 matched_clean rows from an
-- earlier, unrelated cosmetic patch (scripts/shard5_run651_daily_patch.py).
-- As a result, 3 rows that DO have an exact case_number match in
-- tax_deed_outcomes (tier1) were left at parity_status='tier1_only' instead of
-- being promoted to 'matched_clean'. This is NOT a PropertyOnion relabel and
-- NOT a fabricated match -- verified live:
--   tax_deed_outcomes rows: 2025-0077TD ($375,650), 2025-0092TD ($14,650),
--   2025-0110TD ($4,350) -- exact case_number match, exact sold_amount match
--   against multi_county_auctions.tier1_sold_amount / sold_amount.
--
-- Explicitly OUT OF SCOPE (left as tier1_only, not touched): the other 5
-- tier1_only rows (2025-0090TD, 2025-0071TD, 2025-0098TD, 2025-0089TD,
-- 2025-0085TD) have NO exact-match row in tax_deed_outcomes at all (they are
-- redeemed pre-sale, never sold, so no clerk sale record exists) -- promoting
-- those would be an unverified guess and is forbidden.
--
-- Explicitly OUT OF SCOPE: the 49 mca_only/tier1_clerk_supp_shard5_run651 rows
-- and the 1 mca_only/null row (50 total) are pre-sale auctions (auction_status
-- ='upcoming', auction_date mostly 2026-04-08 through 2026-09-02) with zero
-- corresponding tier1 outcome records (foreclosure_outcomes has 0 clay rows,
-- tax_deed_outcomes has exactly 11 clay rows = the count of already-closed
-- sales). No tier1 data exists for these 50 case_numbers yet -- a tax-deed/
-- foreclosure outcome cannot exist for a property that hasn't sold. Verified
-- live: 0/50 join to tax_deed_outcomes under exact or punctuation-normalized
-- case_number match. This is a structural ceiling requiring net-new clerk
-- scraping infrastructure for Clay/jacksonclerk.com, not a same-session SQL
-- fix. Left unfixed -- see session report.
--
-- Expected impact: C (matched_clean) 17 -> 20 of 108 (15.7% -> 18.5%),
-- D (matched_any) 17 -> 20 of 108 (15.7% -> 18.5%). Both remain well below
-- the 95% pass threshold -- this does NOT flip C/D to pass. It is a small,
-- real, verifiable correction, not a threshold-crossing fix.

BEGIN;

UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_scope = 'clerk_outcomes_litmus_reclass_shard_clay_run20260704'
WHERE county = 'clay'
  AND parity_status = 'tier1_only'
  AND parity_source LIKE 'tier1%'
  AND case_number IN ('2025-0077TD', '2025-0092TD', '2025-0110TD')
  AND sold_amount IS NOT NULL
  AND tier1_sold_amount IS NOT NULL
  AND sold_amount = tier1_sold_amount;

COMMIT;
