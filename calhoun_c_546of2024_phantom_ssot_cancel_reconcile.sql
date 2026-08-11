-- Gold Standard: Calhoun County, letter C (matched_clean) — parity_status reconciliation
-- Date: 2026-08-11
-- Diagnosis (pre-fix): C metric = 87.5% (7/8), fails >=95 threshold by exactly 1 row.
--   Offending row: case '546 OF 2024', parity_status='PHANTOM_NOT_ON_CLERK',
--   parity_source='tier1:calhoun_clerk_live_20260710', data_source='calhoun_clerk_scrape',
--   tier1_authoritative=false, property_address='10500 SR 73 Frink FL 32430',
--   auction_date=2026-08-13 (marked upcoming), parcel_id='26-1S-10-0000-0004-0100'.
--
-- Investigation (live re-verification, 2026-08-11, ~1 month after original tier1 scrape):
--   Source: Calhoun Clerk of Court WordPress REST API (the same source the
--   calhoun_clerk_harvest.py tier1 scraper uses — calhounclerk.com is a WP site
--   exposing foreclosures/taxdeeds/taxdeedoverbids as custom post types).
--     https://www.calhounclerk.com/wp-json/wp/v2/taxdeeds?per_page=100
--       -> X-WP-Total: 5, X-WP-TotalPages: 1 (no pagination gap)
--       -> live certs: 383 OF 2024, 227 OF 2024, 268 OF 2023, 621 OF 2026(titled "621 OF 2024", cancelled), 171 OF 2023
--     https://www.calhounclerk.com/wp-json/wp/v2/foreclosures?per_page=100
--       -> X-WP-Total: 2, X-WP-TotalPages: 1 -> 26-03DR, 25-56CA
--     https://www.calhounclerk.com/wp-json/wp/v2/taxdeedoverbids?per_page=100
--       -> X-WP-Total: 41, X-WP-TotalPages: 1 (historical surplus/closed-sale feed)
--   Case number "546 OF 2024" does NOT appear in any of the three feeds. Parcel
--   "26-1S-10-0000-0004-0100" also does not appear in any of the three feeds
--   (checked by parcel, ruling out a cert-renumber/re-key scenario). This
--   independently corroborates the original tier1 scraper's PHANTOM_NOT_ON_CLERK
--   finding rather than contradicting it — the row genuinely does not exist on
--   the clerk's live docket, active or historical, a month after our DB first
--   picked it up.
--
-- Resolution applied: reconciled parity_status/auction_status per the existing
--   clerk_ssot/run_parity.py convention for "case in our DB, absent from clerk
--   SSOT" -> auction_status='CANCELLED', parity_status='CLERK_SSOT_CANCELLED'.
--   This corrects the stale "upcoming" auction_status (was advertising a
--   2026-08-13 sale the clerk shows no evidence of) and moves letter D
--   (matched_any, which explicitly includes CLERK_SSOT_CANCELLED in its
--   passing set) from 87.5% -> 100% PASS.
--
-- Letter C is NOT fixed by this and cannot be, by canon design: C's passing
--   set is (parity_status='matched_clean' AND parity_source LIKE 'tier1%') OR
--   parity_status IN ('PARITY_OK','CLERK_VERIFIED') — CLERK_SSOT_CANCELLED is
--   deliberately excluded from C (only D accepts it). auctions_total (the
--   denominator) includes this row regardless of auction_status, since the
--   canon county filter has no auction_status clause. There is no legitimate
--   value this row can be assigned that satisfies C's passing set, because
--   the row is a confirmed-cancelled/never-existed-on-docket case, not a
--   genuine matched auction. Per guardrail #3 (fail-loud, never fabricate a
--   match to force a pass), C for calhoun remains BLOCKED at 87.5% (7/8)
--   pending either (a) the clerk's site retroactively confirming this case
--   under a different identifier, or (b) a future new case entering the
--   denominator that dilutes the 1-row gap below the 5% threshold.
--
-- Verification (public.pencil_dod_evaluate_county('calhoun'), post-fix, live):
--   C: {"pass": false, "detail": "matched_clean=7", "metric": 87.5}   -- unchanged, structurally blocked
--   D: {"pass": true,  "detail": "matched_any=8",    "metric": 100}   -- FIXED (was 87.5)
--   auctions_total: 8

SET statement_timeout = 0;

UPDATE multi_county_auctions
SET auction_status = 'CANCELLED',
    parity_status = 'CLERK_SSOT_CANCELLED',
    parity_source = 'calhoun_clerk_taxdeeds_20260811_reverify'
WHERE lower(county) = 'calhoun'
  AND case_number = '546 OF 2024'
  AND parity_status = 'PHANTOM_NOT_ON_CLERK'
RETURNING id, case_number, county, auction_status, parity_status, parity_source;

-- Result: 1 row updated (id=b92c4842-2222-466a-9332-f32d0130ce75)
