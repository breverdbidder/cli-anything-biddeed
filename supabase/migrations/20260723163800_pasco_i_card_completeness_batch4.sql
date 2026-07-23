-- Gold Standard: pasco criterion I follow-up (batch 4)
-- 91.8% (236/257) -> target >=95%
--
-- Root cause: same pattern as batch1/batch2/batch3 -- multi_county_auctions rows
-- either (a) already have a valid parcel_id but are missing latitude/longitude/
-- assessed_value AND have no parcel_zones row for pasco jurisdiction 1258, or
-- (b) have parcel_id IS NULL but carry a real, non-placeholder street address
-- that resolves to exactly one fl_parcels row via a local ILIKE prefix match.
--
-- IMPORTANT DISCOVERY THIS SESSION: the FL GIO Statewide Cadastral FeatureServer
-- org id used by batch1/2/3 (services9.arcgis.com/Gh9awoUAlNaqxRUn/...) is STALE
-- -- it now returns HTTP 400 "Invalid URL" for every request, including the bare
-- service-info endpoint (confirmed via curl -v; not a query-parameter issue).
-- Re-resolved the live item via https://www.arcgis.com/sharing/rest/search --
-- the "Florida_Statewide_Cadastral" Feature Service (item
-- 64a6281f835c4b09a8abcc4e309230de, owner FDEPMapDirect) now lives at org id
-- Gh9awoU677aKree0. Confirmed working with a live query (PARCEL_ID exact match,
-- JV returned matches fl_parcels.jv for every parcel below). Future pasco/other-
-- county sessions should use services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/
-- services/Florida_Statewide_Cadastral/FeatureServer/0/query going forward.
--
-- (a) 11 rows: parcel_id present, missing lat/lon/assessed_value, no parcel_zones
--     row. Backfilled via FL GIO polygon centroid (avg of outer-ring vertices)
--     + JV, cross-checked against fl_parcels.jv (co_no=61) -- exact match on all
--     11. DOR_UC crosswalk reused unchanged from batch1/2/3 (001->R-2, 002->MH,
--     004->RMF), no new zone_code labels needed.
--
-- (b) 3 rows: parcel_id IS NULL, but a real (non-placeholder) address matched
--     EXACTLY ONE fl_parcels row via a local ILIKE prefix search on phy_addr1
--     (house number + first street word(s), since fl_parcels stores abbreviated
--     street names). All 3 are also among the "IDENTICAL placeholder-looking"
--     rows flagged this session (latitude=28.308, longitude=-82.4396,
--     assessed_value=150000.0 -- a legacy ghost-fill that did NOT previously
--     count as card_complete because parcel_id was NULL, so no false PASS was
--     ever produced by it). Per this session's data-quality-flag guidance, the
--     fake lat/lon/assessed_value on these 3 rows is OVERWRITTEN with the real
--     FL GIO-sourced values in the same UPDATE, since we now have a resolved
--     parcel_id for them. All 3 are DOR_UC 001 -> R-2, same crosswalk as (a).
--
-- Deferred (parcel_id IS NULL, no confident single-row match, or already
-- deferred in a prior batch -- no new information found this session, not
-- re-attempted beyond a documented local-match check):
--   51-2025-CA-000763-CAAX-WS   : addr "6824 BEACH BLVD, HUDSON" -- zero
--                                 fl_parcels rows (co_no=61) match phy_addr1
--                                 ILIKE '6824 BEACH%'. Still carries the fake
--                                 placeholder lat/lon/assessed_value untouched
--                                 (cannot overwrite without a real parcel match).
--   51-2025-CA-002914-CAAX-WS   : addr "4371 TAHITIAN GARDENS CIR, HOLIDAY" --
--                                 zero fl_parcels rows match phy_addr1 ILIKE
--                                 '4371 TAHITIAN%'. Fake placeholder untouched.
--   51-2025-CA-002535-CAAX-ES   : addr "36733 THOMAS JEFFERSON ROAD, DADE CITY"
--                                 -- zero fl_parcels rows match phy_addr1 ILIKE
--                                 '36733 THOMAS%'. (This row does NOT carry the
--                                 fake placeholder -- lat/lon/assessed_value are
--                                 genuinely NULL.)
--   51-2025-CC-004020-CCAX-ES   : addr "6609 RIDGE ROAD #2 A/K/A #4, PORT
--                                 RICHEY" -- phy_addr1 ILIKE '6609 RIDGE%'
--                                 returns 4 distinct fl_parcels rows (a small
--                                 commercial/retail complex subdivided into unit
--                                 parcels). No confident single match -- unit-
--                                 level guess risk too high per guardrails.
--                                 Fake placeholder untouched.
--   51-2026-CC-000910-CCAX-WS   : addr "5722 BISCAYNE COURT UNIT # 302, NEW
--                                 PORT RICHEY" -- phy_addr1 ILIKE '5722
--                                 BISCAYNE%' returns ~30 condo-unit parcels,
--                                 same condo ambiguity already documented and
--                                 deferred in batch3. Not re-attempted.
--   51-2025-CC-004715-CCAX-ES   : parcel_id NULL, no address, no legal_desc/
--                                 owner_name -- unchanged from batch3, still
--                                 blocked (re-confirmed this session).
--   51-2025-CC-008556-CCAX-WS   : parcel_id NULL, no address -- unchanged from
--                                 batch3, still blocked (re-confirmed this
--                                 session). NOTE: this row's latitude/longitude/
--                                 assessed_value have changed since batch3's
--                                 comment (batch3 said "already has lat/lon/
--                                 assessed_value from realforeclose source";
--                                 this session observed lat=28.24, lon=-82.72,
--                                 assessed_value=25581.21, not the fake-
--                                 placeholder triple and not what batch3
--                                 described either -- an upstream scraper must
--                                 have updated it between batches). Left
--                                 untouched here: no address/parcel_id to
--                                 independently verify a real geocode against,
--                                 and altering values we can't verify is out of
--                                 scope per the (c) guardrail (only overwrite
--                                 fake data we can REPLACE with a verified
--                                 value; this row still has no parcel_id so no
--                                 replacement is possible).
--
-- Net effect: 236 + 14 = 250 of 257 = 97.3% (>=95% threshold).

SET statement_timeout = 0;

-- (a) parcel_id present, backfill lat/lon/assessed_value from FL GIO centroid + JV
UPDATE multi_county_auctions
SET latitude = 28.42871122,
    longitude = -82.54046521,
    assessed_value = 351990,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch4'
WHERE case_number = '51-2025-CA-000973-CAAX-ES' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.23311749,
    longitude = -82.29208709,
    assessed_value = 365210,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch4'
WHERE case_number = '51-2026-CC-002369-CCAX-ES' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.22296575,
    longitude = -82.74197805,
    assessed_value = 59431,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch4'
WHERE case_number = '51-2025-CA-003221-CAAX-WS' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.19839236,
    longitude = -82.24799437,
    assessed_value = 269999,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch4'
WHERE case_number = '51-2025-CC-007475-CCAX-ES' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.18460222,
    longitude = -82.74713044,
    assessed_value = 72062,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch4'
WHERE case_number = '51-2024-CC-004608-CCAX-WS' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.26060848,
    longitude = -82.72608658,
    assessed_value = 122857,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch4'
WHERE case_number = '51-2025-CA-001144-CAAX-WS' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.26015854,
    longitude = -82.71410701,
    assessed_value = 165333,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch4'
WHERE case_number = '51-2024-CA-002049-CAAX-WS' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.17336532,
    longitude = -82.31367573,
    assessed_value = 212591,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch4'
WHERE case_number = '51-2025-CA-002659-CAAX-ES' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.35230729,
    longitude = -82.59666053,
    assessed_value = 260357,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch4'
WHERE case_number = '51-2025-CA-002280-CAAX-WS' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.35991515,
    longitude = -82.59399106,
    assessed_value = 305296,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch4'
WHERE case_number = '51-2025-CA-001266-CAAX-WS' AND county = 'pasco';
UPDATE multi_county_auctions
SET latitude = 28.18072252,
    longitude = -82.75853436,
    assessed_value = 221104,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch4'
WHERE case_number = '51-2025-CA-004053-CAAX-WS' AND county = 'pasco';

-- (b) parcel_id was NULL, resolved via unambiguous local fl_parcels address
-- match -- also overwrites the fake placeholder lat/lon/assessed_value
-- (28.308 / -82.4396 / 150000.0) with real FL GIO-sourced values now that a
-- real parcel_id has been established. parcel_id itself is also set for the
-- first time on these 3 rows so the I-criterion zone-match sub-condition can
-- resolve against the newly-inserted parcel_zones row below.
UPDATE multi_county_auctions
SET parcel_id = '13-26-21-0140-00000-1230',
    latitude = 28.21850648,
    longitude = -82.16296883,
    assessed_value = 181804,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch4_local_addr_match'
WHERE case_number = '51-2024-CA-000126-CAAX-ES' AND county = 'pasco';
UPDATE multi_county_auctions
SET parcel_id = '29-26-19-0070-00000-2020',
    latitude = 28.19253963,
    longitude = -82.42010042,
    assessed_value = 596065,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch4_local_addr_match'
WHERE case_number = '51-2025-CA-001703-CAAX-ES' AND county = 'pasco';
UPDATE multi_county_auctions
SET parcel_id = '10-26-21-0120-00000-0650',
    latitude = 28.24266395,
    longitude = -82.19777107,
    assessed_value = 232713,
    assessed_value_source = 'fl_gio_statewide_cadastral_JV_shard_pasco_i_fix_batch4_local_addr_match'
WHERE case_number = '51-2025-CA-002109-CAAX-ES' AND county = 'pasco';

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT v.parcel_id, v.jurisdiction_id, v.zone_code, v.zone_name, v.source
FROM (VALUES
  ('06-24-18-0040-00002-0460', 1258, 'R-2', 'Residential Single Family (2-4 du/ac)', 'shard_pasco_i_fix_batch4/INFERRED:dor_uc_001_sfr'),
  ('10-26-20-0020-00200-0640', 1258, 'R-2', 'Residential Single Family (2-4 du/ac)', 'shard_pasco_i_fix_batch4/INFERRED:dor_uc_001_sfr'),
  ('18-26-16-0380-30820-00A0', 1258, 'RMF', 'Multi-Family Residential (Condo)', 'shard_pasco_i_fix_batch4/INFERRED:dor_uc_004_mfr_condo'),
  ('30-26-21-0040-00800-0060', 1258, 'R-2', 'Residential Single Family (2-4 du/ac)', 'shard_pasco_i_fix_batch4/INFERRED:dor_uc_001_sfr'),
  ('31-26-16-0170-00000-3910', 1258, 'MH', 'Mobile Home (4 du/ac)', 'shard_pasco_i_fix_batch4/INFERRED:dor_uc_002_mh'),
  ('32-25-16-0120-00D00-0050', 1258, 'R-2', 'Residential Single Family (2-4 du/ac)', 'shard_pasco_i_fix_batch4/INFERRED:dor_uc_001_sfr'),
  ('33-25-16-0090-00000-0180', 1258, 'R-2', 'Residential Single Family (2-4 du/ac)', 'shard_pasco_i_fix_batch4/INFERRED:dor_uc_001_sfr'),
  ('33-26-20-0220-01000-0010', 1258, 'R-2', 'Residential Single Family (2-4 du/ac)', 'shard_pasco_i_fix_batch4/INFERRED:dor_uc_001_sfr'),
  ('34-24-17-0090-00000-0260', 1258, 'R-2', 'Residential Single Family (2-4 du/ac)', 'shard_pasco_i_fix_batch4/INFERRED:dor_uc_001_sfr'),
  ('34-24-17-0110-00000-4270', 1258, 'R-2', 'Residential Single Family (2-4 du/ac)', 'shard_pasco_i_fix_batch4/INFERRED:dor_uc_001_sfr'),
  ('36-26-15-0840-00000-5500', 1258, 'R-2', 'Residential Single Family (2-4 du/ac)', 'shard_pasco_i_fix_batch4/INFERRED:dor_uc_001_sfr'),
  ('13-26-21-0140-00000-1230', 1258, 'R-2', 'Residential Single Family (2-4 du/ac)', 'shard_pasco_i_fix_batch4/INFERRED:dor_uc_001_sfr'),
  ('29-26-19-0070-00000-2020', 1258, 'R-2', 'Residential Single Family (2-4 du/ac)', 'shard_pasco_i_fix_batch4/INFERRED:dor_uc_001_sfr'),
  ('10-26-21-0120-00000-0650', 1258, 'R-2', 'Residential Single Family (2-4 du/ac)', 'shard_pasco_i_fix_batch4/INFERRED:dor_uc_001_sfr')
) AS v(parcel_id, jurisdiction_id, zone_code, zone_name, source)
WHERE NOT EXISTS (
  SELECT 1 FROM parcel_zones pz
  WHERE pz.parcel_id = v.parcel_id AND pz.jurisdiction_id = v.jurisdiction_id
);
