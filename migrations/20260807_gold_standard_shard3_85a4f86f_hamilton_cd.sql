-- GOLD STANDARD shard-3 (dispatch 85a4f86f-993f-40c0-9095-47ac8d01a6e5) — hamilton C/D
-- 8 of 21 hamilton rows failed tier1 parity (3 NULL, 5 mca_only). Live re-verification
-- against hamiltonclerk.com/tax-deeds/ and hamiltonclerk.com/foreclosures/ (the county's
-- own tier1 source already cited in these rows' data_source field) confirmed 4 of the 8
-- genuinely match current clerk listings (parcel_id/owner/plaintiff all matched exactly).
-- Promoted those 4. The other 4 foreclosure cases (2021-CA-46, 2023-CA-41, 2024-CA-19,
-- 2025-CA-37) are NOT present on the clerk's current static foreclosure page (confirmed,
-- no pagination/archive exists) and were deliberately left untouched — Civitek OCRS
-- (civitekflorida.com/ocrs/county/24/) is the likely next lever but requires authenticated
-- browser navigation unavailable to WebFetch this session.
--
-- Result (adversarially verified, gold_standard_ultraloop_audit): C/D 61.9% -> 81.0%,
-- still FAIL (<95% threshold). Genuine partial improvement, not a full close.

SET statement_timeout = 0;

UPDATE multi_county_auctions
SET
    parity_status     = 'matched_clean',
    parity_source     = 'tier1:hamilton_gold_standard_session_20260807_live_reharvest:tax_deed:2026-08-07',
    parity_confidence = 0.9,
    parity_checked_at = NOW(),
    updated_at        = NOW()
WHERE county = 'hamilton'
  AND case_number IN ('HAM-TD-CERT-379','HAM-TD-CERT-597','HAM-TD-CERT-599')
  AND parity_status IS NULL;

UPDATE multi_county_auctions
SET
    parity_status     = 'matched_clean',
    parity_source     = 'tier1:hamilton_gold_standard_session_20260807_live_reharvest:foreclosure:2026-08-07',
    parity_confidence = 0.9,
    parity_checked_at = NOW(),
    updated_at        = NOW()
WHERE county = 'hamilton'
  AND case_number = '2025-CA-66'
  AND parity_status = 'mca_only';

-- Deliberately NOT touched (no live match found on hamiltonclerk.com/foreclosures/ as of 2026-08-07):
--   2021-CA-46, 2023-CA-41, 2024-CA-19, 2025-CA-37
