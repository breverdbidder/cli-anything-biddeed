-- Gold Standard alachua (workflow run 14411591), letters E (parcel_linked) and
-- I (card_complete). Fixes ONE row: case_number '01 2025 CC 001127'.
--
-- CONTEXT (fresh live re-check this session, not carried over): 8 of the 9
-- current E-gap rows remain genuinely blocked for the exact reasons already
-- documented in supabase/migrations/20260731p_gold_standard_shard_c1_alachua_ei_no_change.sql
-- and 20260731c_shard3_alachua_ei_freshness_recheck_no_change.sql (re-verified
-- live this session: qpublic.schneidercorp.com still HTTP 403; RealForeclose's
-- own AJAX Parcel ID field is still the placeholder "Property Appraiser" for
-- all empty-docid cases; case 01 2025 CA 003287's Clerk record still shows a
-- 3-lot "MOSES E LEVY GRANT" legal description with no PARCEL-type entry; case
-- 01 2026 CA 000211's Clerk record still shows only a SECTION/TOWN/RANGE
-- legal remark ("THOMAS NAPIER GRANT LOT 24"), no PARCEL-type entry, and the
-- ArcGIS PublicParcel owner-name match for "2900 GAINESVILLE HOLDINGS LLC"
-- is still 2 ambiguous candidates with no disambiguating field).
--
-- The 9th row, 01 2025 CC 001127, is NEWLY resolvable this session: a live
-- re-harvest of the RealForeclose AJAX calendar for its auction date
-- (08/27/2026, AREA=W) surfaced Clerk docid=3700205 (this docid was not
-- present/was not previously resolved in any prior same-day session's
-- documented row set). Following the docid to
-- isol.alachuaclerk.org/RealEstate/SearchDetail.aspx?docid=3700205 (which
-- this session -- unlike prior sessions -- returned full record content, not
-- the JS-required BrowserTest.aspx redirect) surfaces a recorded JUDGMENT
-- (Book 5280, Page 1086, filed 07/07/2026) with:
--   Grantor: ELLIS PARK COMMUNITY ASSOCIATION INC (HOA -- consistent with a
--     "CC" county-civil small-judgment case, Final Judgment Amount $11,219.39)
--   Grantee: RYAN NANCY ROSS
--   Combined Legals -> Type: PARCEL, Parcel Id: 06308-010-008 (single,
--     unambiguous value -- unlike 003287/000211 above, this record HAS a
--     PARCEL-type legal entry)
--   Subdivision: ELLIS PARK PHASE 1 UNIT 1, Lot 18
--
-- Cross-referenced against two independent live sources, both agreeing
-- exactly, zero fabrication:
--   1. Alachua Property Appraiser ArcGIS PublicParcel/FeatureServer/0
--      (services.arcgis.com/cNo3jpluyt69V8Ek), query where=Name='06308-010-008':
--      Owner_Mail_Name="RYAN NANCY ROSS" (exact match to Clerk grantee),
--      FULLADDR="9989 NW 21ST AVE", StatedArea=0.1576 acres. Same query with
--      returnGeometry=true gives a parcel polygon; centroid computed as
--      lat=29.672437665160263, lon=-82.44803403433566.
--   2. FL GIO Statewide_Cadastral FeatureServer (services9.arcgis.com/
--      Gh9awoU677aKree0), spatial point-in-polygon query at that centroid
--      (CO_NO=1, Alachua): PARCEL_ID="06308-010-008" (exact match),
--      PHY_ADDR1="9989 NW 21ST AVE" (exact match), JV=345532, LND_VAL=74000,
--      DOR_UC=001 (single-family residential). JV (DOR "just value") mapped
--      to assessed_value, following the exact convention already used in
--      commit 54c17c98 (scripts/alachua-I_fix.py, "assessed_value=<jv>
--      (ArcGIS/FL GIO JustValue)").
--
-- I-COVERAGE CHECK (residual, not fixed this session): queried
-- v_zoning_gold_standard_card and the underlying parcel_zones table for
-- parcel_id='06308-010-008' -- zero rows. This parcel has never been
-- zoning-assigned (it sits in unincorporated Alachua County, confirmed via a
-- point-in-polygon query against the county's MunicipalBoundary ArcGIS layer
-- returning zero intersecting municipalities). Probed the county's own GIS
-- server (gis.alachuacounty.us/arcgis/rest/services, all folders: EPD,
-- Transportation, Utilities, CityWorks, Operational, Images, Printing) for a
-- zoning layer -- none exists. So while this migration fixes E for this row
-- (parcel_linked), I's card_complete additionally requires this parcel_id to
-- appear in v_zoning_gold_standard_card with zone_code IS NOT NULL, which
-- remains unmet -- a zoning-substrate gap, not something writable via
-- PostgREST without fabricating a zone code from no ordinance source. Real
-- ordinance-backed zoning ingestion for unincorporated Alachua parcels is a
-- separate, larger scope (Phase 4 firecrawl+LLM ordinance work), not a
-- one-row backfill.
--
-- data_source for this row is 'calendar_sweep_mca_v3' (not 'propertyonion'),
-- so no PropertyOnion-exclusion conflict. parity_status was already
-- 'matched_clean' with parity_source 'tier1:shard10_run6253_alachua_ajax_harvest:...'
-- (untouched by this migration).
--
-- BEFORE (live, this session): E FAIL parcel_linked=52/61 (85.2%),
--   I FAIL card_complete=47/61 (77.0%).
-- EXPECTED AFTER this one-row fix: E parcel_linked=53/61 (86.9%, still FAIL,
--   need >=58/61=95.1%); I unchanged at 47/61 (77.0%) because this row still
--   lacks a zone-coverage row in v_zoning_gold_standard_card (see above).
-- Verified via SELECT public.pencil_dod_evaluate_county('alachua') after
-- applying -- see session report / issue comment for the exact post-apply
-- numbers.

BEGIN;

UPDATE public.multi_county_auctions
SET
  parcel_id = '06308-010-008',
  property_address = '9989 NW 21ST AVE',
  latitude = 29.672437665160263,
  longitude = -82.44803403433566,
  assessed_value = 345532,
  updated_at = now()
WHERE county = 'alachua'
  AND case_number = '01 2025 CC 001127'
  AND parcel_id IS NULL
  AND (data_source IS DISTINCT FROM 'propertyonion' OR tier1_authoritative = true);

COMMIT;
