-- Gold Standard shard-2 (dispatch b3eafd22): taylor letter E fix for case
-- 23-505 CA, the sole parcel_id=NULL row (11 of 12 auctions_total -> 91.7%).
--
-- ROOT CAUSE (VERIFIED live, 2026-08-26): case 23-505 CA, property_address
-- "1205 Sweetgum Lane Northeast Steinhatchee, FL 32359", was never parcel-
-- linked (parcel_id, latitude, longitude, assessed_value all NULL).
--
-- FIX: queried the FL GIO Statewide Cadastral FeatureServer directly
-- (https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/
-- Florida_Statewide_Cadastral/FeatureServer/0/query, CO_NO=72 for Taylor
-- per fl_counties.co_no) for an exact address match:
--   PARCEL_ID=09459-119, PHY_ADDR1="1205 SWEETGUM LN  NE",
--   PHY_CITY="Steinhatchee", PHY_ZIPCD=32359, JV=287370, LND_VAL=99500,
--   DOR_UC=001 (single family) -- exact match to our stored address.
-- Centroid (returnCentroid=true, outSR=4326): lat=29.689720817015733,
-- lon=-83.36362337393638.
--
-- This closes E for taylor (11/12 -> 12/12 = 100%). It does NOT close I:
-- v_zoning_gold_standard_card requires this parcel_id to also carry a
-- zone_code in parcel_zones, and taylor's zoning substrate (loaded via the
-- NCFRPC Future Land Use Plan Map GeoPDF, point-in-polygon, per prior
-- sessions e.g. 20260809_gold_standard_taylor_i_06578076_c5a8b2c7.sql) does
-- not yet cover this parcel -- confirmed live via
-- v_zoning_gold_standard_card WHERE county='taylor' AND parcel_id='09459-119'
-- returning zero rows. Determining the correct FLU/zoning classification
-- for this Steinhatchee-area parcel requires the same GeoPDF point-in-
-- polygon method as the prior 11 taylor zone_code rows; this session did
-- not have reliable tooling to do that lookup with confidence, and a
-- guessed zone_code is explicitly banned (ghost-success). Left as an open,
-- well-scoped follow-up for I (taylor stays at 11/12 = 91.7% for I this
-- session).

UPDATE public.multi_county_auctions
SET parcel_id = '09459-119',
    latitude = 29.689720817015733,
    longitude = -83.36362337393638,
    assessed_value = 287370,
    assessed_value_source = 'fl_gio_cadastral_co72_exact_addr_match_20260826',
    geo_source = 'fl_gio_cadastral_co72_centroid_20260826'
WHERE lower(county) = 'taylor'
  AND case_number = '23-505 CA'
  AND parcel_id IS NULL;
