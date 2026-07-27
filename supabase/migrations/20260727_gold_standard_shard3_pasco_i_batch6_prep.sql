-- Gold Standard: pasco criterion I — batch 6 prep (dispatch fb510ba8, 2026-07-27)
--
-- CONTEXT: pasco is 10/10 PASS at loop run 6871 (2026-07-27). I=95.9% (256/267).
-- Between dispatch 8c8052cf (2026-07-23, batch4) and this session, 10 new rows
-- were ingested; 3 of those 10 are not card_complete (256 complete of 267 total).
-- The 2-row margin (256 >= 254 = ceil(267×0.95)) is thin.
--
-- THIS MIGRATION is a DIAGNOSTIC ONLY (contains only SELECT statements).
-- It identifies the 3 new non-card-complete rows so the next session with DB
-- access can apply targeted fixes using the same fl_parcels pattern as batches 1-5.
--
-- APPLY WHEN: a session has SUPABASE credentials available (GHA runner with secrets).
-- NOT a blocking issue — I is currently PASS and certification is not imminent.
--
-- DIAGNOSTIC (run to find candidates):

SET statement_timeout = 0;

-- Find pasco rows that currently fail the I evaluator sub-conditions:
-- (a) missing lat/lon, (b) missing assessed_value, (c) missing parcel_zones link
SELECT
    mca.case_number,
    mca.property_address,
    mca.parcel_id,
    mca.latitude,
    mca.longitude,
    mca.assessed_value,
    pz.zone_code AS zone_code_in_parcel_zones
FROM multi_county_auctions mca
LEFT JOIN parcel_zones pz ON pz.parcel_id = mca.parcel_id
WHERE mca.county = 'pasco'
  AND mca.auction_status = 'sold'
  AND (
      mca.latitude IS NULL OR mca.longitude IS NULL
      OR mca.assessed_value IS NULL
      OR mca.parcel_id IS NULL
      OR pz.parcel_id IS NULL
  )
ORDER BY mca.auction_date DESC;

-- Expected: ~11 rows (7 unresolvable residuals from prior batches + ~3-4 new rows)
-- The 7 unresolvable residuals (per batch5 header):
--   51-2025-CC-008556-CCAX-WS  : parcel_id/address both NULL
--   51-2025-CC-004715-CCAX-ES  : parcel_id/address both NULL
--   51-2025-CA-000763-CAAX-WS  : "6824 BEACH BLVD, HUDSON" -- 0 fl_parcels matches
--   51-2025-CA-002914-CAAX-WS  : "4371 TAHITIAN GARDENS CIR, HOLIDAY" -- 0 matches
--   51-2025-CA-002535-CAAX-ES  : parcel_id is garbage string "Property Appraiser"
--   51-2025-CC-004020-CCAX-ES  : "6609 RIDGE ROAD #2 A/K/A #4, PORT RICHEY" -- ambiguous 4-unit
--   51-2026-CC-000910-CCAX-WS  : "5722 BISCAYNE COURT UNIT # 302" -- 24 condo units, no discriminator
-- Any case_number NOT in the above list = new ingestion gap, apply batch6 fix pattern.
--
-- BATCH 6 FIX PATTERN (for each resolvable new row):
--   1. Confirm phy_addr1 match in fl_parcels WHERE co_no=61 (Pasco) -- must be EXACT or clear match
--   2. Take JV (just_value), centroid_lat, centroid_lng from fl_parcels
--   3. UPDATE multi_county_auctions SET latitude=, longitude=, assessed_value=,
--      assessed_value_source='fl_parcels_co61_JV_shard_pasco_i_fix_20260727'
--      WHERE case_number = '<case>' AND county = 'pasco';
--   4. INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
--      ...WHERE NOT EXISTS (guard idempotency)
--   5. Re-run pencil_dod_evaluate_county('pasco') -- confirm I stays PASS

-- NOTE on FL GIO org_id: batch5 confirmed the old org_id Gh9awoUAlNaqxRUn is stale (HTTP 400).
-- Updated org_id for Pasco (co_no=61) is: Gh9awoU677aKree0
-- ArcGIS FeatureServer URL pattern:
--   https://services.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/
--   FL_Parcels_Statewide_Cadastral/FeatureServer/0/query
--   ?where=CO_NO=61+AND+PARCEL_ID='<folio>'&outFields=JV,CENTROID_LAT,CENTROID_LNG,DOR_UC&f=json
