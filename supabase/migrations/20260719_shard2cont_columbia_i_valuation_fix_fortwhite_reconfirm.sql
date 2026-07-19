-- Columbia County letter I (property card completeness) continuation fix.
-- Dispatch 190ac19f-8ae0-465c-be8b-ec314028eb77, 2nd firing (continuation session).
-- This file documents live writes already applied via PostgREST PATCH during the session
-- (idempotent -- re-running the equivalent UPDATE is a no-op if values already match).
--
-- BASELINE (live pencil_dod_evaluate_county('columbia') at start of this session):
--   I: {"pass":false,"detail":"card_complete=12 of 15","metric":80.0}
--
-- Prior session (dispatch 190ac19f, 1st firing) had already fixed 4 zone-less parcels via
-- gis.columbiacountyfla.com Zoning_Atlas polygon-intersect (see
-- 20260719_shard2_columbia_ei_gis_zone_and_parcel_fix.sql) and left 3 rows genuinely blocked:
--   1) case 2025-63-CA  (parcel 00130-000)          -- missing assessed_value/market_value
--   2) case 2025-249-CA (parcel 28-1S-17-04576-002) -- missing assessed_value/market_value
--   3) case 2025-2196-CC (parcel 04023-000)         -- inside Fort White town limits, zero
--      zoning-atlas coverage in county GIS (polygon-intersect returns 0 features)
--
-- THIS SESSION: followed next-session-priority #1 (direct owner-name / appraiser-record
-- lookup instead of address/parcel lookup, which had already failed) and re-checked
-- priority #2 (Fort White zoning atlas gap) live rather than assuming it unchanged.
--
-- ============================================================================
-- FIX 1: case 2025-63-CA (283 NW COLE TERRACE), parcel 01-3S-15-00130-000
-- ============================================================================
-- Method: Columbia County's OWN property-record page (not the blocked qpublic/columbiapa.org
-- vendor site), https://www.columbiacountyfla.com/ParcelDetails.aspx?ParcelNo=01-3S-15-00130-000
-- (linked directly from the GIS Parcels FeatureServer's own Url field for this ParcelNo --
-- i.e. the county's GIS layer points at this exact appraiser page itself).
-- Live-fetched 2026-07-19. Page confirms:
--   Owner: ROGERS WALTER B (exact match to GIS Parcels layer Owner field from prior session,
--     and exact surname match to the case's own plaintiff field: "MEREDITH I. LAPRADD ... VS.
--     WALTER L. ROGERS, JR." -- two independent confirmations this is the correct parcel).
--   Total Market: $446,650
--   Total Assessed: $32,966 (agricultural-use assessment differential is real -- Columbia
--     County ag-classified land carries a much lower assessed value than market value under
--     FL's greenbelt/agricultural classification statute, not a data error).
-- FIX: assessed_value=32966, market_value=446650, owner_name='ROGERS WALTER B',
--   assessed_value_source='columbiacountyfla.com_ParcelDetails_appraiser_verified'.
--
-- ============================================================================
-- FIX 2: case 2025-249-CA (294 NE OMAR TERRACE), parcel 28-1S-17-04576-002
-- ============================================================================
-- Method: same county-owned ParcelDetails.aspx page for ParcelNo=28-1S-17-04576-002.
-- Live-fetched 2026-07-19. Page confirms:
--   Location field on the page: "294 NE OMAR TER" -- exact match to
--     multi_county_auctions.property_address "294 NE OMAR TERRACE".
--   Owner: STAFFORD JAMES EARL -- surname match to the case's own plaintiff field
--     ("... VS. STACEY EARL STAFFORD A/K/A STACEY E STAFFORD A/K/A STACY STAFFORD, ET AL." --
--     same Stafford family, same parcel).
--   Total Market: $108,541
--   Total Assessed: $38,120
-- FIX: assessed_value=38120, market_value=108541, owner_name='STAFFORD JAMES EARL',
--   assessed_value_source='columbiacountyfla.com_ParcelDetails_appraiser_verified'.
--
-- ============================================================================
-- RE-CHECK (not re-fixed): case 2025-2196-CC (357 SW AMIEL CT), parcel 04023-000
-- ============================================================================
-- Priority #2 explicitly asked to NOT assume the prior session's Fort White finding still
-- holds and to re-query the live ArcGIS FeatureServer/MapServer Zoning_Atlas layer fresh.
-- Done this session:
--   1. Re-fetched the parcel's authoritative polygon from
--      gis.columbiacountyfla.com/hosting/rest/services/Parcels/FeatureServer/1
--      (ParcelNo=33-6S-16-04023-000). Confirms Municipality='Town of Ft. White' (unchanged).
--   2. Confirmed the query mechanism itself works: a plain attribute query against
--      Zoning_Atlas/FeatureServer/1 returned HTTP 400 "Unable to perform query operation"
--      for ANY query today (service degraded), so switched to Zoning_Atlas/MapServer/1,
--      which responds normally. Sanity-checked the MapServer polygon-intersect query against
--      a KNOWN-GOOD parcel (14-3S-16-02123-027, one of the 4 already-fixed zone-less rows) to
--      prove the query mechanics themselves are not the source of a zero-result -- this
--      returned real Zoning_Atlas features (confirming the method works).
--   3. Ran the SAME polygon-intersect query against parcel 33-6S-16-04023-000's real geometry
--      on THREE separate live layers:
--        - Zoning_Atlas/MapServer/1            -> 0 features
--        - Zoning_and_Land_Use/MapServer/1 (new group-layer sublayer, not checked previously)
--                                               -> 0 features
--        - PreJuly_2020_Zoning_Atlas/MapServer  -> 0 features
--      All three return zero features for this parcel today -- the Fort White zoning gap in
--      the county's GIS is RECONFIRMED LIVE, not an assumption carried over from the prior
--      session.
--   4. Searched for a Fort White-specific GIS/zoning ArcGIS REST endpoint (the town's own,
--      separate from the county's). None found -- fortwhitefl.com has no ArcGIS REST service;
--      the county's own service catalog (gis.columbiacountyfla.com/hosting/rest/services) has
--      no folder/service for Fort White zoning specifically, only Ft_White_Limits (boundary),
--      Ft_White_Utility_Plant, and Ft_White_Water_Lines (utilities) -- same negative result as
--      the prior session, now independently reproduced.
-- CONCLUSION: still genuinely blocked. No placeholder registered (same reasoning as prior
-- session: the county layer returns silence, not a real GIS sentinel string to anchor a
-- placeholder district row to -- inventing one would cross into fabrication). Left BLANK.
--
-- ============================================================================
-- RESULT
-- ============================================================================
-- pencil_dod_evaluate_county('columbia') I: 80.0% (12/15) -> 93.3% (14/15).
-- Still FAIL (needs >=95%, i.e. 15/15 at this denominator -- 14/15 rounds to 93.3, no
-- intermediate value clears the bar). The one remaining row (2025-2196-CC / Fort White) is a
-- genuine structural ceiling this session: no fabricated zone code, no invented value.

-- Fix 1: 2025-63-CA
UPDATE multi_county_auctions
SET assessed_value = 32966,
    market_value = 446650,
    owner_name = 'ROGERS WALTER B',
    assessed_value_source = 'columbiacountyfla.com_ParcelDetails_appraiser_verified'
WHERE county = 'columbia' AND case_number = '2025-63-CA';

-- Fix 2: 2025-249-CA
UPDATE multi_county_auctions
SET assessed_value = 38120,
    market_value = 108541,
    owner_name = 'STAFFORD JAMES EARL',
    assessed_value_source = 'columbiacountyfla.com_ParcelDetails_appraiser_verified'
WHERE county = 'columbia' AND case_number = '2025-249-CA';
