-- SHARD-11 (dispatch dd396ee4-e383-45ea-8953-5ad92fb1c1af), county=hardee
--
-- E (parcel_linked) backfill for the single hardee auction row, case
-- 25000327CAAXMX (1841 State Road 66, Zolfo Springs FL 33890).
--
-- SOURCING (CONFIRMED, cross-verified two independent ways):
--   1. WebSearch surfaced a real-estate MLS aggregator (LandSearch, MLS# C7519048)
--      listing parcel number "25-34-25-0000-01290-0000" for this exact address.
--   2. That parcel number, reformatted to FL GIO's PARCEL_ID string convention
--      (concatenated digits, no dashes: '2534250000012900000'), was queried LIVE
--      against the FL GIO Statewide Cadastral 2025 ArcGIS FeatureServer
--      (services9.arcgis.com/.../Florida_Statewide_Cadastral/FeatureServer/0) and
--      returned exactly one feature:
--        CO_NO=35, PARCEL_ID=2534250000012900000, PHY_ADDR1="1841 ST RD 66",
--        PHY_CITY="ZOLFO SPRINGS", PHY_ZIPCD=33890, DOR_UC="001" (single family),
--        JV=361086, LND_VAL=100000, TOT_LVG_AR=2511, ACT_YR_BLT=2005,
--        OWN_NAME="SOTO JUSTIN"
--   3. OWN_NAME "SOTO JUSTIN" independently matches the foreclosure defendant name
--      "Justin Soto" from the live hardeeclerk.com re-fetch used for the C/D fix in
--      this same session ("Newrez LLC vs Justin Soto Et Al") -- two unrelated
--      sources (FL GIO cadastral roll vs. clerk civil docket) agreeing on owner
--      name is strong independent corroboration this is the correct parcel, not a
--      coincidental address match.
--   4. Geometry centroid (outSR=4326 / WGS84) = lat 27.488751706504146,
--      lng -81.76432746090056 -- falls within the Zolfo Springs / SR-66 corridor
--      of Hardee County, consistent with the property address.
--
-- NOTE ON CO_NO: this live FL GIO lookup returned CO_NO=35 for Hardee, which
-- matches fl_counties_manifest.yml's index (35: [Hardee, null]) but does NOT match
-- either the live `fl_counties` DB table (co_no=25, also mirrored in
-- jurisdictions.co_no=25) or the session brief's stated "CO_NO for Hardee=21".
-- Flagging this three-way CO_NO discrepancy (21 vs 25 vs 35) as a data-quality issue
-- for a future session -- NOT resolved here, out of scope for a single-parcel
-- E/I fix. The live cadastral API response (35) is the ground truth used for this
-- specific parcel lookup since it returned a verified, cross-corroborated match.
--
-- FIELDS BACKFILLED (JV used for both assessed_value and market_value per the same
-- convention ingest_county.py's DOR_UC_MAP crosswalk uses when no separate market
-- value source exists):
--   parcel_id = '2534250000012900000'
--   latitude = 27.488751706504146, longitude = -81.76432746090056
--   assessed_value = 361086, market_value = 361086
--   assessed_value_source = 'fl_gio_cadastral_2025_co35'
--   living_area_sqft = 2511, year_built = 2005
--   owner_name = 'SOTO JUSTIN'
--
-- This migration file documents a change that was ALREADY APPLIED live via REST
-- PATCH in this session (see actions/evidence_query in the session's structured
-- output). Re-running this UPDATE is idempotent (same values, WHERE-scoped to the
-- single case_number) and safe to replay from a fresh DB state.
--
-- I (card_complete) is intentionally NOT addressed by this migration: linking this
-- parcel to jurisdiction_id=927 (Wauchula)'s real zoning_districts would be a
-- FACTUALLY WRONG jurisdiction match -- 1841 SR-66 is in the Zolfo Springs
-- corridor / likely unincorporated Hardee County, not inside Wauchula city limits,
-- and jurisdictions.id=1014 (Zolfo Springs) has zero zoning_districts scraped.
-- Forcing a Wauchula linkage here would repeat exactly the SYN-HRD-* fabrication
-- purged earlier in this session. I remains honestly FAIL.

SET statement_timeout = 0;

BEGIN;

UPDATE public.multi_county_auctions
SET parcel_id = '2534250000012900000',
    latitude = 27.488751706504146,
    longitude = -81.76432746090056,
    assessed_value = 361086,
    market_value = 361086,
    assessed_value_source = 'fl_gio_cadastral_2025_co35',
    living_area_sqft = 2511,
    year_built = 2005,
    owner_name = 'SOTO JUSTIN'
WHERE lower(county) = 'hardee'
  AND case_number = '25000327CAAXMX'
  AND data_source = 'hardee_clerk_direct';

COMMIT;
