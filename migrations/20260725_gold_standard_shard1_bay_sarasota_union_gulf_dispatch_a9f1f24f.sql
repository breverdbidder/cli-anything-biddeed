-- Gold Standard shard-1 (bay/sarasota/union/gulf), dispatch a9f1f24f-93aa-42e0-bdc5-83dd5a4a5039
-- Applied live via Supabase PostgREST REST API using the service-role key (2026-07-25). This session's
-- environment had no working psql/DDL access (direct pooler password auth failed for both the transaction
-- and session pooler hosts) -- all statements below were executed as REST reads/writes against existing
-- tables, not as a psql-run migration. This file documents those writes for the repo's audit trail.
--
-- SECURITY NOTE: a tool-result in this session attempted a prompt injection -- a fabricated "file was
-- modified by the user/linter, don't tell them" note trying to get fabricated Sarasota zoning
-- parking_per_1000sf values written to production while hidden from the user. It was refused and flagged
-- to the user; none of that data was used. Re-verification pulled the same 4 real, legitimately-sourced
-- values that were already live in zone_standards (ids 1137,1138,1139,1140,4995,4925) -- no data was lost
-- or corrupted by the attempt, but it is recorded here since it's directly relevant to trusting this file.

-- ===== gulf: 9 tax-deed cases were closed with a sale, verified via Gulf County Clerk's official
-- "Tax Deeds Sales and Surplus/Overbids" page (https://www.gulfclerk.com/courts/tax-deeds/, independently
-- re-fetched HTTP 200). A SURPLUS entry only exists under FL Stat. 197.582 when the winning bid exceeds
-- the statutory minimum -- proof of a completed sale, even though the page does not publish the full
-- winning-bid dollar amount (only the surplus/excess). tier1_sold_amount was deliberately left NULL --
-- writing the surplus figure into that field would misrepresent it as the sale price, which it is not.

UPDATE multi_county_auctions
SET auction_status = 'completed',
    tier1_sale_status = 'sold',
    tier1_authoritative = true,
    tier1_verified_at = '2026-07-25T08:22:17Z'
WHERE id IN (
  'ffa578f9-fd4b-4007-9423-d935b3e23bbf', -- 2025-001, surplus $1,396.95
  '5020af68-9fe7-4bec-b994-a9dd35df5720', -- 2025-003, surplus $5,788.56
  '5207789c-7c56-4dbe-aa41-a3bf76cb87d4', -- 2025-011, surplus $5,238.47
  '174a433f-d692-4ace-90ce-ccf6780b92a6', -- 2025-010, surplus $9,963.71
  'f6c312cc-3d43-47b1-9882-d6da2f8313ba', -- 2025-022, surplus $3,885.62
  '14b4ecac-8452-4907-a5cc-77c7ea9e9a2e', -- 2025-021, surplus $4,161.58
  '97442d1c-8668-47f3-9e0e-f107eb8398e3', -- 2025-018, surplus $37,036.22
  'afc7bca8-39d4-44e4-b84e-b0e3c4c129a9', -- 2025-017, surplus $39.14
  '39cd7b4d-e5ee-4d56-be08-06764f4cf9db'  -- 2025-023, surplus $1,200.99
);

INSERT INTO tax_deed_outcomes (case_number, county, auction_date, parcel_id, outcome, data_source, source_url)
VALUES
  ('2025-001','gulf','2025-08-27','02513000R','SOLD','gulfclerk_taxdeed_surplus_v1:GOLD-STANDARD-A9F1F24F','https://www.gulfclerk.com/courts/tax-deeds/'),
  ('2025-003','gulf','2025-08-27','02154001R','SOLD','gulfclerk_taxdeed_surplus_v1:GOLD-STANDARD-A9F1F24F','https://www.gulfclerk.com/courts/tax-deeds/'),
  ('2025-011','gulf','2025-11-19','02722200R','SOLD','gulfclerk_taxdeed_surplus_v1:GOLD-STANDARD-A9F1F24F','https://www.gulfclerk.com/courts/tax-deeds/'),
  ('2025-010','gulf','2025-11-19','05762000R','SOLD','gulfclerk_taxdeed_surplus_v1:GOLD-STANDARD-A9F1F24F','https://www.gulfclerk.com/courts/tax-deeds/'),
  ('2025-022','gulf','2026-03-04','00627000R','SOLD','gulfclerk_taxdeed_surplus_v1:GOLD-STANDARD-A9F1F24F','https://www.gulfclerk.com/courts/tax-deeds/'),
  ('2025-021','gulf','2026-01-21','00629010R','SOLD','gulfclerk_taxdeed_surplus_v1:GOLD-STANDARD-A9F1F24F','https://www.gulfclerk.com/courts/tax-deeds/'),
  ('2025-018','gulf','2026-01-07','05004050R','SOLD','gulfclerk_taxdeed_surplus_v1:GOLD-STANDARD-A9F1F24F','https://www.gulfclerk.com/courts/tax-deeds/'),
  ('2025-017','gulf','2025-12-17','03426604R','SOLD','gulfclerk_taxdeed_surplus_v1:GOLD-STANDARD-A9F1F24F','https://www.gulfclerk.com/courts/tax-deeds/'),
  ('2025-023','gulf','2026-03-18','00469000R','SOLD','gulfclerk_taxdeed_surplus_v1:GOLD-STANDARD-A9F1F24F','https://www.gulfclerk.com/courts/tax-deeds/');

-- ===== gulf: data-integrity fix, not a metric-flipping fix. Row 237fb61f (case 232019CA000060CAAXMX) had
-- parcel_id literally set to the string "Property Appraiser" -- a scraping artifact, not a real parcel ID
-- -- which was counting as a false-positive "linked" parcel toward criterion E. Nulling it is honest and
-- causes E's metric to correctly drop (85.7% -> 78.6%); this is intentional, not a regression to hide.
-- Separately, this same row's tier1_sale_status was already CANCELED_PER_ORDER (tier1_authoritative=true,
-- verified 2026-07-23 by prior automation) -- genuinely not a sale, correctly excluded from B/F.

UPDATE multi_county_auctions
SET parcel_id = NULL
WHERE id = '237fb61f-c945-4e72-9fd5-179978d9b1bc';

-- ===== Residual gaps NOT fixed this session (see session report for full detail + evidence):
--  gulf B/F: real winning_bid amount for the 9 tax-deed sales above is not publicly available (only
--    surplus); the 5 CA/CC foreclosure cases (232025CA000037CAAXMX, 232024CA000042CAAXMX,
--    232019CA000060CAAXMX, 232024CA000072CAAXMX, 232024CC000157CCAXMX) are blocked by gulf.realforeclose.com
--    (403 to all automated fetches) and Gulf County's OCRS portal (interactive JS app, not fetchable).
--  gulf C/D/E/I: 2 rows (232024CA000072CAAXMX, 232024CC000157CCAXMX) have no case-detail available from
--    any accessible source; 2 rows (2025-017, 2025-023) are vacant unaddressed parcels where the Clerk's
--    own record also lacks a street address (legal description only) -- "N/A" may already be structurally
--    correct, not a data gap.
--  union B/F: genuine dead end -- 2 of 3 auctions haven't reached their sale date yet, 1 was redeemed
--    (no 3rd-party sale by definition). Nothing to fix; will resolve naturally as auction dates pass.
--  sarasota G: pk1000 sub-metric structurally blocked pending a fleet-wide policy decision from Ariel
--    (use-type-only parking codes, no single district-wide standard) -- see dispatch 42827b21/db0d3b7b
--    (2026-07-25, same day) and dispatch 9f070f2b (2026-07-18, bay county, same blocker). Not re-attempted.
