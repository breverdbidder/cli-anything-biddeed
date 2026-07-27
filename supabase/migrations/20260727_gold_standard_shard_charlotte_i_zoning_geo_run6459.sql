-- Gold Standard charlotte (co_no=8) criterion I fix, run6459.
--
-- Baseline (VERIFIED via pencil_dod_evaluate_county('charlotte'), live 2026-07-27
-- before this session's I changes): I FAIL card_complete=107 of 113 (94.7%,
-- need >=108/113). C/D were ALSO showing FAIL (matched_clean=106, matched_any=106,
-- both 93.8%) at session start but were independently confirmed to have ALREADY
-- been fixed by a concurrent/prior session (parity_source
-- 'realauction_ajax_harvest_shard12_run6796' on all 4 target case rows,
-- 'po_staleness_reconfirm:charlotte_shard12_run6796:...' on the 3 stale-PO rows) --
-- this session's own re-run of exact_match_and_promote() against those same rows
-- was a confirmed no-op (0 promoted, already matched_clean), and a fresh
-- pencil_dod_evaluate_county() re-query (3rd call, after transient replica-lag
-- on the first two calls from concurrent writers) shows C=110/113=97.3% PASS,
-- D=113/113=100% PASS. No C/D write was made by this migration.
--
-- The 6 non-matched card_complete gap rows (113-107=6, of which 2 are the
-- structural 'MULTIPLE PARCELS' rows out of scope per session brief) are the 4
-- brand-new TODAY (2026-07-27) auction rows, never swept by any zoning
-- ingestion: parcel_zones had ZERO rows for all 4 (verified before this
-- migration). Real zone_code + assessed value + lat/lon centroid sourced live
-- from Charlotte County's official ArcGIS MapServer, discovered by rediscovering
-- the host implied by the existing 103 rows' source label
-- 'charlotte_county_agis3_zoning_live_20260724' (agis3.charlottecountyfl.gov --
-- the gis.charlottecountyfl.gov hostname referenced in scripts/shard7_charlotte_fixes.py
-- does NOT resolve, confirmed via nslookup NXDOMAIN this session):
--   https://agis3.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGISLayers/MapServer/27
--   (layer 27 "Ownership" -- ACCOUNT, zoningcode, assessedvalue, totvalue,
--   propertyaddress, polygon geometry, outSR=4326 for centroid lat/lon)
-- Queried by ACCOUNT=<parcel_id> (exact match), cross-verified propertyaddress
-- on every row matches our own multi_county_auctions.property_address for the
-- same case (street name + number match exactly), confirming correct parcel.
--
-- Values (all queried live 2026-07-27):
--   402219282005 (case 26000203CA, "18510 ELLEN AVE"): zoningcode=RSF3.5,
--     assessedvalue=410883, centroid lon=-82.1403971260875 lat=26.984166669753606
--   402102226010 (case 26000389CA, "16483 HILLSBOROUGH BLVD"): zoningcode=RSF3.5,
--     assessedvalue=13600, centroid lon=-82.17389145812312 lat=27.03253841402509
--   412026104007 (case 25000548CA, "66 OAKLAND HILLS CT"): zoningcode=RSF5,
--     assessedvalue=195844, centroid lon=-82.28556119584307 lat=26.885720857974366
--   412003304011 (case 25001169CC, "9068 TUNIS AVE"): zoningcode=RSF3.5,
--     assessedvalue=77976, centroid lon=-82.30264418651954 lat=26.937675536599258
--
-- jurisdiction_id=813 used for all 4 (Punta Gorda/Charlotte), matching the
-- convention already used by all 103 existing Charlotte parcel_zones rows
-- (parcel_zones has no county column, only jurisdiction_id -- this county's
-- existing rows are all keyed to 813 regardless of actual municipality).
--
-- Applied live via PostgREST (direct psql/pooler auth confirmed broken this
-- session, same documented constraint as prior sessions -- SUPABASE_URL +
-- SUPABASE_SERVICE_ROLE_KEY used instead). This file committed for SHIP-TO-MAIN
-- discipline (the 2026-07-24 session that produced the other 103 rows did not
-- commit its own script/migration -- not repeating that gap).

INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, source)
SELECT '402219282005', '402219282005', 813, 'RSF3.5',
       'charlotte_county_agis3_zoning_live_shard_i_run6459:https://agis3.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGISLayers/MapServer/27/query?where=ACCOUNT=''402219282005''+addressmatch:18510_ELLEN_AVE'
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '402219282005');

INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, source)
SELECT '402102226010', '402102226010', 813, 'RSF3.5',
       'charlotte_county_agis3_zoning_live_shard_i_run6459:https://agis3.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGISLayers/MapServer/27/query?where=ACCOUNT=''402102226010''+addressmatch:16483_HILLSBOROUGH_BLVD'
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '402102226010');

INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, source)
SELECT '412026104007', '412026104007', 813, 'RSF5',
       'charlotte_county_agis3_zoning_live_shard_i_run6459:https://agis3.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGISLayers/MapServer/27/query?where=ACCOUNT=''412026104007''+addressmatch:66_OAKLAND_HILLS_CT'
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '412026104007');

INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, source)
SELECT '412003304011', '412003304011', 813, 'RSF3.5',
       'charlotte_county_agis3_zoning_live_shard_i_run6459:https://agis3.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGISLayers/MapServer/27/query?where=ACCOUNT=''412003304011''+addressmatch:9068_TUNIS_AVE'
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '412003304011');

UPDATE multi_county_auctions
SET latitude = 26.984166669753606, longitude = -82.1403971260875,
    assessed_value = COALESCE(assessed_value, 410883)
WHERE case_number = '26000203CA' AND county = 'charlotte'
  AND latitude IS NULL AND longitude IS NULL;

UPDATE multi_county_auctions
SET latitude = 27.03253841402509, longitude = -82.17389145812312,
    assessed_value = COALESCE(assessed_value, 13600)
WHERE case_number = '26000389CA' AND county = 'charlotte'
  AND latitude IS NULL AND longitude IS NULL;

UPDATE multi_county_auctions
SET latitude = 26.885720857974366, longitude = -82.28556119584307,
    assessed_value = COALESCE(assessed_value, 195844)
WHERE case_number = '25000548CA' AND county = 'charlotte'
  AND latitude IS NULL AND longitude IS NULL;

UPDATE multi_county_auctions
SET latitude = 26.937675536599258, longitude = -82.30264418651954,
    assessed_value = COALESCE(assessed_value, 77976)
WHERE case_number = '25001169CC' AND county = 'charlotte'
  AND latitude IS NULL AND longitude IS NULL;

-- Out of scope, residual/structural finding only (no fix attempted, per brief):
--   25000748CA (id 4249c94b) and 25001710CA (id 00b1cace) -- parcel_id literal
--   'MULTIPLE PARCELS', property_address NULL. One auction row cannot hold N
--   parcel_ids in the current schema; a real fix needs either a
--   multi_county_auctions_parcels join table or a docket-level lookup that
--   enumerates the actual parcel_ids from the court record, which would then
--   require splitting or annotating this single row across N parcels --
--   a schema change, not a data fix. Left untouched.

SELECT public.pencil_dod_evaluate_county('charlotte');
