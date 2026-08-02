-- GOLD STANDARD shard-1 (brevard/jefferson/holmes), dispatch a42bf937-8d85-46f9-8158-554d3d6ffd21
-- Brevard letter I (property card completeness): real, sourced backfill.
--
-- Diagnosis (live-verified 2026-08-02): I was failing at card_complete=6044/7238 (83.5%).
-- Root cause of the ~1194-row gap, decomposed:
--   - 1124 rows missing property_address. Direct live check against Brevard's own authoritative
--     GIS (gis.brevardfl.gov Base_Map/Parcel_New_WKID2881 MapServer/5, field STREET_NAME) on all
--     1058 numeric-format parcel_ids in this set: only 21 have a real, non-'UNKNOWN' street name.
--     ~98% are genuinely no-situs-address parcels (mostly vacant tax-deed land) per the county's
--     own record, not a scraper gap. One of the 21 ('CONFIDENTIAL' street name -- FL address
--     confidentiality program) was deliberately excluded, not written.
--   - Remaining ~70 rows had an address but were missing geo/value/zoning. 68 of 70 were missing
--     a parcel_zones row. Root cause: Brevard's county-level Zoning GIS layer
--     (Planning_Development/Zoning_WKID2881) covers unincorporated county only -- most of these
--     parcels sit inside one of Brevard's ~13 municipalities, which maintain separate zoning GIS
--     systems not yet integrated. One parcel (unincorporated) was resolved via a live
--     point-in-polygon query against that layer. Eleven more already had a real zone_code sitting
--     in sample_properties (from the pre-existing zoning_assignments_sync / gis_conquest pipelines)
--     but had never been copied into parcel_zones.
--
-- Net effect applied live this session (see session report for full before/after evaluator output):
--   card_complete 6044 -> 6077 of 7238 (83.5% -> 84.0%). Still FAILing (<95%) -- this is a
--   confirmed, evidence-backed data-availability ceiling, not a scraper/matcher bug. Structural
--   ceiling for future sessions: municipal (per-jurisdiction) zoning GIS integration for the
--   remaining ~56 zoneless parcels, and no further address recovery is possible without a
--   non-GIS source for genuinely no-situs vacant parcels.
--
-- This file documents the writes for audit history. The writes themselves were applied live via
-- the Supabase Management API during the session (see /tmp/brevard_i_backfill.py logic, not
-- committed -- ephemeral one-off script). Statements below are idempotent re-statements of the
-- same writes for reproducibility; safe to re-run.

-- 20 property_address backfills, sourced from gis.brevardfl.gov Parcel_New MapServer/5 STREET_* fields
-- (full list re-selected live post-apply from multi_county_auctions to guarantee accuracy)
UPDATE multi_county_auctions SET property_address = '3474 MASEK AVE, MIMS, FL 32754', assessed_value_source = COALESCE(assessed_value_source, 'gis_brevardfl_gov_parcel_layer') WHERE parcel_id = '2102407' AND lower(county) = 'brevard' AND property_address IS NULL;
UPDATE multi_county_auctions SET property_address = '2971 CARVER ST, MIMS, FL 32754', assessed_value_source = COALESCE(assessed_value_source, 'gis_brevardfl_gov_parcel_layer') WHERE parcel_id = '2103818' AND lower(county) = 'brevard' AND property_address IS NULL;
UPDATE multi_county_auctions SET property_address = '5225 VOLUSIA AVE, TITUSVILLE, FL 32780', assessed_value_source = COALESCE(assessed_value_source, 'gis_brevardfl_gov_parcel_layer') WHERE parcel_id = '2215828' AND lower(county) = 'brevard' AND property_address IS NULL;
UPDATE multi_county_auctions SET property_address = '205 PALMETTO AVE, MERRITT ISLAND, FL 32953', assessed_value_source = COALESCE(assessed_value_source, 'gis_brevardfl_gov_parcel_layer') WHERE parcel_id = '2426593' AND lower(county) = 'brevard' AND property_address IS NULL;
UPDATE multi_county_auctions SET property_address = '107 TERRY ST, INDIAN HARBOUR BEACH, FL 32937', assessed_value_source = COALESCE(assessed_value_source, 'gis_brevardfl_gov_parcel_layer') WHERE parcel_id = '2715004' AND lower(county) = 'brevard' AND property_address IS NULL;
UPDATE multi_county_auctions SET property_address = '1008 BROTHERS AVE, MELBOURNE, FL 32901', assessed_value_source = COALESCE(assessed_value_source, 'gis_brevardfl_gov_parcel_layer') WHERE parcel_id = '2817145' AND lower(county) = 'brevard' AND property_address IS NULL;
UPDATE multi_county_auctions SET property_address = '480 TRUMAN ST, PALM BAY, FL 32908', assessed_value_source = COALESCE(assessed_value_source, 'gis_brevardfl_gov_parcel_layer') WHERE parcel_id = '2900995' AND lower(county) = 'brevard' AND property_address IS NULL;
UPDATE multi_county_auctions SET property_address = '654 HARPER BLVD, PALM BAY, FL 32908', assessed_value_source = COALESCE(assessed_value_source, 'gis_brevardfl_gov_parcel_layer') WHERE parcel_id = '2904779' AND lower(county) = 'brevard' AND property_address IS NULL;
UPDATE multi_county_auctions SET property_address = '699 DE GROODT RD, PALM BAY, FL 32908', assessed_value_source = COALESCE(assessed_value_source, 'gis_brevardfl_gov_parcel_layer') WHERE parcel_id = '2906015' AND lower(county) = 'brevard' AND property_address IS NULL;
UPDATE multi_county_auctions SET property_address = '2074 MIDWEST AVE, PALM BAY, FL 32908', assessed_value_source = COALESCE(assessed_value_source, 'gis_brevardfl_gov_parcel_layer') WHERE parcel_id = '2909284' AND lower(county) = 'brevard' AND property_address IS NULL;
UPDATE multi_county_auctions SET property_address = '2035 MORI CT, PALM BAY, FL 32908', assessed_value_source = COALESCE(assessed_value_source, 'gis_brevardfl_gov_parcel_layer') WHERE parcel_id = '2910997' AND lower(county) = 'brevard' AND property_address IS NULL;
UPDATE multi_county_auctions SET property_address = '2315 WOODSTOCK DR, PALM BAY, FL 32908', assessed_value_source = COALESCE(assessed_value_source, 'gis_brevardfl_gov_parcel_layer') WHERE parcel_id = '2916119' AND lower(county) = 'brevard' AND property_address IS NULL;
UPDATE multi_county_auctions SET property_address = '2738 MAHAFFEY AVE, PALM BAY, FL 32908', assessed_value_source = COALESCE(assessed_value_source, 'gis_brevardfl_gov_parcel_layer') WHERE parcel_id = '2916615' AND lower(county) = 'brevard' AND property_address IS NULL;
UPDATE multi_county_auctions SET property_address = '2541 BLARNY AVE, PALM BAY, FL 32908', assessed_value_source = COALESCE(assessed_value_source, 'gis_brevardfl_gov_parcel_layer') WHERE parcel_id = '2917301' AND lower(county) = 'brevard' AND property_address IS NULL;
UPDATE multi_county_auctions SET property_address = '2567 LEGION AVE, PALM BAY, FL 32908', assessed_value_source = COALESCE(assessed_value_source, 'gis_brevardfl_gov_parcel_layer') WHERE parcel_id = '2917703' AND lower(county) = 'brevard' AND property_address IS NULL;
UPDATE multi_county_auctions SET property_address = '1001 PONDER ST, PALM BAY, FL 32908', assessed_value_source = COALESCE(assessed_value_source, 'gis_brevardfl_gov_parcel_layer') WHERE parcel_id = '2919784' AND lower(county) = 'brevard' AND property_address IS NULL;
UPDATE multi_county_auctions SET property_address = '664 AIROSO RD, PALM BAY, FL 32909', assessed_value_source = COALESCE(assessed_value_source, 'gis_brevardfl_gov_parcel_layer') WHERE parcel_id = '2929260' AND lower(county) = 'brevard' AND property_address IS NULL;
UPDATE multi_county_auctions SET property_address = '7468 BABCOCK ST, PALM BAY, FL 32909', assessed_value_source = COALESCE(assessed_value_source, 'gis_brevardfl_gov_parcel_layer') WHERE parcel_id = '2934586' AND lower(county) = 'brevard' AND property_address IS NULL;
UPDATE multi_county_auctions SET property_address = '1031 RAY RD, PALM BAY, FL 32909', assessed_value_source = COALESCE(assessed_value_source, 'gis_brevardfl_gov_parcel_layer') WHERE parcel_id = '2939087' AND lower(county) = 'brevard' AND property_address IS NULL;
UPDATE multi_county_auctions SET property_address = '1420 SANDUSKY ST, PALM BAY, FL 32909', assessed_value_source = COALESCE(assessed_value_source, 'gis_brevardfl_gov_parcel_layer') WHERE parcel_id = '2940183' AND lower(county) = 'brevard' AND property_address IS NULL;

-- Zoning link backfill: 1 row via live spatial point-in-polygon query
INSERT INTO parcel_zones (jurisdiction_id, parcel_id, tax_account, zone_code, source)
VALUES (13, '2103356', '2103356', 'RU-1-7', 'gis_brevardfl_gov_spatial_point_query')
ON CONFLICT DO NOTHING;

-- Zoning link backfill: 11 rows copied from pre-existing real sample_properties.zone_code values
INSERT INTO parcel_zones (jurisdiction_id, parcel_id, tax_account, zone_code, source) VALUES
  (5, '2424532', '2424532', 'SFR',      'sample_properties_sync:zoning_assignments_sync'),
  (5, '2424530', '2424530', 'MFR',      'sample_properties_sync:zoning_assignments_sync'),
  (5, '2425263', '2425263', 'C-G',      'sample_properties_sync:gis_conquest'),
  (5, '2421508', '2421508', 'RU-2-15',  'sample_properties_sync:gis_conquest'),
  (5, '2424555', '2424555', 'SFR',      'sample_properties_sync:zoning_assignments_sync'),
  (5, '2424531', '2424531', 'VAC-RES',  'sample_properties_sync:zoning_assignments_sync'),
  (5, '2421542', '2421542', 'RU-2-15',  'sample_properties_sync:gis_conquest'),
  (5, '2415891', '2415891', 'RU-1-7',   'sample_properties_sync:gis_conquest'),
  (5, '2424554', '2424554', 'MH',       'sample_properties_sync:zoning_assignments_sync'),
  (5, '2441121', '2441121', 'RU-2-15',  'sample_properties_sync:gis_conquest'),
  (5, '2421521', '2421521', 'RU-2-15',  'sample_properties_sync:gis_conquest')
ON CONFLICT DO NOTHING;

-- GHOST-SUCCESS PURGE (found by the ULTRALOOP refuter pass, not caused by this session): 49 rows
-- in multi_county_auctions.property_address held the literal placeholder strings '0 UNKNOWN'
-- (47 rows) and '0 CONFIDENTIAL NO TPP' (2 rows) -- a naive "STREET_NUMBER STREET_NAME"
-- concatenation from an unrelated prior session (2026-07-31 / 2026-08-01) that never filtered out
-- non-address GIS field values. Because they are NOT NULL, these rows were falsely counted as
-- card_complete under the letter-I evaluator. Purging them is a correction, not a regression: it
-- drops the reported card_complete count but makes it honest. See session report for the full
-- before/after reconciliation.
UPDATE multi_county_auctions SET property_address = NULL
WHERE lower(county) = 'brevard' AND property_address IN ('0 UNKNOWN', '0 CONFIDENTIAL NO TPP');
