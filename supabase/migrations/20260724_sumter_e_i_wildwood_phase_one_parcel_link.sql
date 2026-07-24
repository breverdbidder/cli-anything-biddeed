-- Gold Standard: sumter E/I residual fix — case 2025-CA-000255 (Wildwood Phase One LLC)
--
-- Context: sumter E (parcel linkage) and I (property card completeness) were both stuck
-- at 90.9% (10 of 11 auctions) with case 2025-CA-000255 as the sole residual across
-- 5 prior AUTOLOOP sessions (audit ids 1028/1032, then repeated dead-ends through
-- id 8624 on 2026-07-24). All 5 prior sessions independently confirmed no parcel
-- linkage found via: app.sumterpa.com GIS viewer, qpublic.schneidercorp.com
-- (403 WAF), FL Statewide Cadastral ArcGIS FeatureServer via naive owner-name query
-- (intermittent 400/504 on this specific service), Sunbiz.org (403 WAF),
-- Trellis.law/UniCourt (403/no results), sumtercountypropertyappraiser.org
-- (confirmed non-official lead-gen site), and myfloridacounty.com ORI search
-- (Cloudflare Turnstile-gated, correctly out of scope).
--
-- NEW SOURCE this session: SWFWMD (Southwest Florida Water Management District)
-- public ArcGIS parcel mirror, a distinct government agency's copy of Sumter County
-- parcel data, never queried by any prior session:
--   https://www25.swfwmd.state.fl.us/arcgis12/rest/services/BaseVector/parcel_search/MapServer/16
--   query: OWNNAME LIKE '%WILDWOOD PHASE%' -> exactly one match
--
-- Independently cross-verified against a SECOND government source (FL DOR
-- Statewide Cadastral FeatureServer, a different hosting service/agency than
-- SWFWMD) by PARCEL_ID='D29A024':
--   https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/Florida_Statewide_Cadastral/FeatureServer/0
--   query: PARCEL_ID='D29A024' -> OWN_NAME='WILDWOOD PHASE ONE LLC', JV=1133690, LND_VAL=1133690
--
-- Both sources agree exactly on owner name, parcel ID, and assessed/land value.
-- Only one parcel statewide is owned by "WILDWOOD PHASE ONE LLC" (verified via
-- exact-match OWNNAME query returning a single row) -- no ambiguity.
--
-- Neither source is PropertyOnion-derived (CANON requirement for B/F letters --
-- N/A here since this is E/I, but noted for consistency). Parcel is vacant land
-- (DOR_UC=010, NO_RES_UNT=0, TOT_LVG_AR=0, no situs address) in Sec 29, Twn 18S,
-- Rng 23E, Sumter County FL -- consistent with a "Phase One" land-holding LLC name.
--
-- Lat/long computed as parcel geometry centroid, converted from two independent
-- projected CRSs (EPSG:2882 via SWFWMD, EPSG:3086 via FL DOR cadastral) to
-- WGS84 -- both conversions agree to ~10m (28.89376 vs 28.89375 lat).

UPDATE multi_county_auctions
SET parcel_id = 'D29A024',
    latitude = 28.893758,
    longitude = -82.035730,
    assessed_value = 1133690,
    market_value = 1133690,
    legal_description = 'BEG AT NW COR OF THE LANDS DES (Sec 29, Twn 18S, Rng 23E, Sumter County FL) -- vacant land parcel D29A024, owner WILDWOOD PHASE ONE LLC',
    assessed_value_source = 'fl_dor_statewide_cadastral_swfwmd_crosscheck'
WHERE county = 'sumter' AND case_number = '2025-CA-000255';
