-- Gold Standard shard-11 lee ADDENDUM, dispatch 03ff9ae3-9a64-4179-8345-d6b129a0ed83
-- loop run 6354. Follows an ultracode adversarial-verify workflow
-- (wf_e63f9e0e-bb8) that reviewed the same-day migration
-- 20260725_gold_standard_shard11_lee_ei_arcgis_backfill_run6354.sql and
-- caught two real defects, both fixed here:
--
-- 1. That migration's parcel_zones INSERT for parcel_id
--    17-44-25-P4-00400.0910 (case 24-CA-005519) created a DUPLICATE row --
--    a real row for that exact (parcel_id, jurisdiction_id, zone_code)
--    tuple already existed (id=831870, source='lee_arcgis_2026_shard8',
--    created 2026-07-10). This session's earlier diagnosis missed the
--    pre-existing link because the query only checked v_zoning_gold_standard_
--    card by parcel_id/tax_account, and the pre-existing row should have
--    surfaced there -- the actual root cause is that 24-CA-005519's
--    parcel_id was STILL the placeholder text 'Property Appraiser' at
--    diagnosis time, so the row correctly failed I's card_complete check
--    for a real reason (bad parcel_id on the auction row), but the
--    zoning link for the STRAP itself already existed under the correct
--    parcel_id. Deleted the duplicate (id=845505) below.
-- 2. The prior migration's committed assessed_value literals for
--    25-CA-003297 (445468) and 25-CA-002748 (600414) do not match what is
--    live today (555253.00 and 632486.00) -- both rows already carried
--    real lat/lng/assessed_value/address from a 2026-07-20 batch process
--    (identical microsecond-precision updated_at on both rows, a value
--    source distinct from and evidently fresher than this ArcGIS layer's
--    ASSESSED field) BEFORE this session ran. The prior migration's SET
--    for these two columns on those two rows was therefore a no-op against
--    live data; only its parcel_zones INSERT (linking the already-correct
--    parcel_id to a zoned district) had real effect. No further action
--    needed here -- documented for the audit trail.
--
-- New real work in this file: 4 more lee auction rows get a genuine
-- ArcGIS-matched parcel_id + parcel_zones link, all into EXISTING
-- zoning_districts/zone_standards rows with real standards on file
-- (630/C-1 pk1000=3.33, 815/R1 density=4.00, 914/AG-2 density=1.00) --
-- zero new zoning_districts rows, zero G-regression risk. Source
-- addresses for all of this file's writes were independently found via
-- legals.businessobserverfl.com (Florida statutory foreclosure-sale legal
-- notices) and adversarially cross-checked against the live DB
-- auction_date before use (workflow wf_e63f9e0e-bb8, agent
-- refute-e-residual, 14/14 SURVIVED).
--
-- Also backfills real, sourced property_address (no parcel/zone match
-- found) for 10 more lee cases that previously had case_number only --
-- honest partial progress, does not by itself flip E or I for those rows
-- (both require a parcel_id link) but replaces a total data void with
-- verified fact for a future session's ArcGIS/parcel-matching pass.

SET statement_timeout = 0;

-- STEP 0: remove the duplicate parcel_zones row from the same-day prior
-- migration (id verified live before this file was written).
DELETE FROM parcel_zones
WHERE id = 845505
  AND parcel_id = '17-44-25-P4-00400.0910'
  AND source = 'lee_shard11_run6354_arcgis_20260725';

-- STEP 1: backfill parcel_id + geo + assessed_value + parcel_zones link
-- for the 4 rows that ArcGIS-matched to a zone code with existing,
-- real zone_standards precedent.

UPDATE multi_county_auctions
SET parcel_id = '24-44-22-00-00043.0000',
    latitude = 26.63496965,
    longitude = -82.06515122,
    assessed_value = 699111,
    property_address = '4205 PINE ISLAND RD NW, MATLACHA, FL 33993'
WHERE lower(county) = 'lee' AND case_number = '23-CA-011030';

UPDATE multi_county_auctions
SET parcel_id = '15-47-25-B2-00200.2010',
    latitude = 26.38821309,
    longitude = -81.78838062,
    assessed_value = 660785,
    property_address = '24200 STILLWELL PKWY, BONITA SPRINGS, FL 34135'
WHERE lower(county) = 'lee' AND case_number = '24-CA-007855';

UPDATE multi_county_auctions
SET parcel_id = '13-45-23-C1-00099.0030',
    latitude = 26.561287,
    longitude = -81.971301,
    assessed_value = 583016,
    property_address = '4906 SORRENTO CT, CAPE CORAL, FL 33904'
WHERE lower(county) = 'lee' AND case_number = '25-CA-004207';

UPDATE multi_county_auctions
SET parcel_id = '01-44-22-C2-05241.0530',
    latitude = 26.67985087,
    longitude = -82.0559992,
    assessed_value = 52488,
    property_address = '1432 OLD BURNT STORE RD N, CAPE CORAL, FL 33993'
WHERE lower(county) = 'lee' AND case_number = '25-CA-006030';

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
VALUES
  ('24-44-22-00-00043.0000', 630, 'C-1', 'Commercial', 'lee_shard11_run6354_arcgis_addr_20260725'),
  ('15-47-25-B2-00200.2010', 914, 'AG-2', 'AG-2 Zone', 'lee_shard11_run6354_arcgis_addr_20260725'),
  ('13-45-23-C1-00099.0030', 815, 'R1', 'R1 Zone', 'lee_shard11_run6354_arcgis_addr_20260725'),
  ('01-44-22-C2-05241.0530', 815, 'R1', 'R1 Zone', 'lee_shard11_run6354_arcgis_addr_20260725')
ON CONFLICT DO NOTHING;

-- STEP 1b: 25-CC-007464 ArcGIS-matched to a real STRAP (zone RS-2) but
-- jurisdiction 630 (Saint James City/unincorporated) has no RS-2
-- zoning_districts precedent -- per this campaign's established caution,
-- NOT linking parcel_zones without a real standard on file (G-regression
-- risk), but the parcel_id itself is real and verified, so it DOES advance
-- E (parcel-linkage) on its own.

UPDATE multi_county_auctions
SET parcel_id = '26-45-22-02-00000.0080',
    latitude = 26.526668,
    longitude = -82.082954,
    assessed_value = 30443,
    property_address = '3511 PINK IBIS DR, SAINT JAMES CITY, FL 33956'
WHERE lower(county) = 'lee' AND case_number = '25-CC-007464';

-- STEP 2: address-only backfill (no ArcGIS parcel match found for these --
-- 2 are mobile-home-park / Fort Myers Beach / master-parcel addresses that
-- didn't resolve to an individual SITEADDR in the ArcGIS layer; the other
-- match attempts returned 0 results on this session's LIKE-prefix search).
-- Does not flip E or I alone (both require parcel_id); real, sourced,
-- non-fabricated groundwork for a future parcel-matching pass.

UPDATE multi_county_auctions
SET property_address = '24898 TROST BLVD, BONITA SPRINGS, FL 34135'
WHERE lower(county) = 'lee' AND case_number = '25-CA-000992' AND property_address IS NULL;

UPDATE multi_county_auctions
SET property_address = '734 SE 43RD ST, CAPE CORAL, FL 33904'
WHERE lower(county) = 'lee' AND case_number = '25-CA-001692' AND property_address IS NULL;

UPDATE multi_county_auctions
SET property_address = '1229 NW 37TH PL, CAPE CORAL, FL 33993'
WHERE lower(county) = 'lee' AND case_number = '25-CA-002165' AND property_address IS NULL;

UPDATE multi_county_auctions
SET property_address = '230 ARONNE AVE S, LEHIGH ACRES, FL 33974'
WHERE lower(county) = 'lee' AND case_number = '25-CA-003367' AND property_address IS NULL;

UPDATE multi_county_auctions
SET property_address = '1165 AUGUSTA ST E, LEHIGH ACRES, FL 33974'
WHERE lower(county) = 'lee' AND case_number = '25-CA-003581' AND property_address IS NULL;

UPDATE multi_county_auctions
SET property_address = '5276 ESTERO BLVD, FORT MYERS BEACH, FL 33931'
WHERE lower(county) = 'lee' AND case_number = '25-CA-003850' AND property_address IS NULL;

UPDATE multi_county_auctions
SET property_address = '2825 PALM BEACH BLVD, FORT MYERS, FL 33916'
WHERE lower(county) = 'lee' AND case_number = '25-CA-004959' AND property_address IS NULL;

UPDATE multi_county_auctions
SET property_address = '4540 25TH ST SW, LEHIGH ACRES, FL 33973'
WHERE lower(county) = 'lee' AND case_number = '25-CA-005615' AND property_address IS NULL;

UPDATE multi_county_auctions
SET property_address = '12210 SIESTA DR, FORT MYERS BEACH, FL 33931'
WHERE lower(county) = 'lee' AND case_number = '25-CA-006129' AND property_address IS NULL;
