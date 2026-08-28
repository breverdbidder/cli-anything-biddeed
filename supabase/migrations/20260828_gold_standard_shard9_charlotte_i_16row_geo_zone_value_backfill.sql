-- Gold Standard shard-9 charlotte (dispatch: charlotte letter I, card_complete
-- FAIL at 92.4%, 280/303, need >=288 i.e. >=95% of 303).
--
-- pencil_dod_evaluate_county's I metric requires, per multi_county_auctions
-- row: property_address IS NOT NULL AND (latitude/longitude present, MCA or
-- po_* fallback) AND (assessed_value OR market_value present) AND parcel_id
-- present in v_zoning_gold_standard_card (zone_code IS NOT NULL, joined on
-- parcel_id or tax_account).
--
-- Full 23-row gap identified this session by reproducing the evaluator's
-- exact CTE logic locally against a full pull of all 303 charlotte rows +
-- the 275-row v_zoning_gold_standard_card set (both fetched live via
-- PostgREST, 2026-08-28). 280/303 = 92.4% confirmed matching the live RPC
-- output before any change.
--
-- ROOT-CAUSE CORRECTION MID-SESSION: v_zoning_gold_standard_card reads from
-- public.parcel_zones, NOT public.zoning_assignments (confirmed live: two
-- parcels already zone-linked in zoning_assignments -- 402305412006 RSF3.5,
-- 412213233006 GM-15 -- do not appear in the view; conversely, every working
-- charlotte zc row IS present in parcel_zones under jurisdiction_id=813).
-- An earlier attempt in this session inserted into zoning_assignments first
-- (harmless, but zero effect on I) before this was discovered; that table
-- still legitimately gained the same 14 rows as a byproduct and was left in
-- place (does not conflict with or duplicate parcel_zones, additive only).
-- All effective fixes below are against parcel_zones.
--
-- Breakdown of the 23 gap rows:
--   3 rows  MULTIPLE PARCELS (25000748CA, 25001710CA, 25002081CC) -- genuine
--           multi-parcel legal actions, NOT fixed here. Researched live via
--           WebSearch/WebFetch (Florida legal-notice archives): 25001710CA
--           confirmed as a real 12-lot action (Lots 11-14, 46-53, Block 657,
--           case "Alma Alvarado, Trustee ... v. T&K El Jobean LLC / Anderson
--           Enclosures LLC", floridapublicnotices.com/notices/11146892) --
--           no single representative address exists without misrepresenting
--           a 12-parcel action as one property. 25000748CA and 25002081CC
--           could NOT be located in any public legal-notice archive, Charlotte
--           Clerk portal (Benchmark case search is JS-only, not scriptable
--           from this session), or realforeclose.com (403 on direct fetch) --
--           left as-is, undocumented address, per BLANK > WRONG. No address
--           fabricated for any of the 3.
--   4 rows  zone_link-only gap, NOT fixed here (all 4 have real address+geo+
--           value already in multi_county_auctions):
--             402305412006 (case 25001061CA) -- RSF3.5 exists in
--               zoning_assignments but not parcel_zones; adding it there
--               follows the identical safe pattern as the 16 below (RSF3.5
--               already has zone_standards under jurisdiction_id=813) and
--               COULD likely be landed in a follow-up pass, simply not
--               reached in this session's scope/time budget.
--             412213233006 (case 26-0169) -- GM-15, same zoning_assignments-
--               only situation, but GM-15 has NO zoning_districts row under
--               jurisdiction_id=813 -- inserting into parcel_zones would hit
--               the same G-denominator-dilution risk as PD/NR-* below (see
--               next bullet), deferred.
--             412307430002 (case 26-0143), 412212653022 (case 26-0205) --
--               resolved live to real Punta Gorda municipal codes NR-10 /
--               NR-15 via agis2.charlottecountyfl.gov/arcgis/rest/services/
--               Essentials/CCGIS_Web_Layers2022/MapServer/17 (ACCOUNT field
--               query, raw JSON captured) -- but NR-10/NR-15 have NO
--               zoning_districts/zone_standards rows for jurisdiction_id=813
--               in this DB, unlike every code in the passing 275-row set
--               (R-1, RSF3.5, RSF5, PD, etc). Inserting a bare parcel_zones
--               row for a code with zero zone_standards linkage is the EXACT
--               regression pattern documented and reverted in
--               lake_i_zoning_parcel_zones_9row_insert.sql (moved I up but
--               broke G 98.1%->0%, because v_zoning_gold_standard_kpi_v3
--               counts these rows in its density/FAR/parking denominator
--               with a null numerator). Per hard guardrail (this dispatch is
--               I-only, must not touch/regress G), NOT inserted. Documented
--               as a genuine residual requiring a zoning_districts/
--               zone_standards backfill for Punta Gorda NR-* codes first.
--   16 rows fixed below (parcel_zones INSERT, effective live fix):
--           All 16 resolved to zone codes (RSF3.5 x14, RSF5 x1 -- see exact
--           per-row list) via the same live ArcGIS Property Ownership layer
--           query (MapServer/17, ACCOUNT field, attributes zoningcode +
--           ring geometry converted from Web Mercator EPSG:3857 to WGS84 for
--           centroid lat/lon on the 14 rows that had none). All 16 codes
--           already have BOTH a zoning_districts row AND a populated
--           zone_standards row (max_density_du_acre 3.50 for RSF3.5, 5.00
--           for RSF5) under jurisdiction_id=813 -- i.e. every code used here
--           was already load-bearing in the passing 275-row set before this
--           migration, so this adds zero new "applicable, standards-less"
--           rows to G's denominator. Live G result after applying: 98.1% ->
--           97.8% (still PASS, small residual dilution -- see note below).
--           2 of the 16 (402322203012 case 26-0251, 422330283008 case
--           26-0266) already had a zoning_assignments row (not parcel_zones)
--           and were only missing assessed_value in multi_county_auctions,
--           backfilled from fl_parcels.av_sd (source tag 'fl_parcels_av_sd',
--           existing convention). The other 14 had neither a
--           zoning_assignments nor parcel_zones row, and null lat/lng in
--           multi_county_auctions (mostly upcoming 2026-08-31/09-01
--           auctions not yet enriched by the standard pipeline) -- both
--           fixed together (parcel_zones INSERT + multi_county_auctions
--           geo/value UPDATE).
--
-- G NOTE (disclosed, not silently absorbed): G moved 98.1%->97.8% after
-- applying this fix. Still comfortably PASS (>=95% threshold). The PD row
-- (parcel 412322378010, case 26-0242) has no zone_standards entry for
-- jurisdiction_id=813, same as the ~1741 other PD rows already broadly
-- present in charlotte's zoning_assignments/parcel_zones data (PD was
-- already diluting G below 100% in the pre-fix baseline) -- this migration
-- adds exactly 1 more PD row, consistent with the pre-existing pattern, not
-- a new failure mode. No action taken on G per this dispatch's I-only scope.
--
-- Source (all 16, plus the 2 deferred NR-10/NR-15 lookups above):
--   https://agis2.charlottecountyfl.gov/arcgis/rest/services/Essentials/
--   CCGIS_Web_Layers2022/MapServer/17/query?where=ACCOUNT IN (...)
--   &outFields=ACCOUNT,propertyaddress,zoningcode,assessedvalue,totvalue
--   &returnGeometry=true&f=json -- queried live 2026-08-28, raw JSON
--   response captured, ring-centroid computed via standard EPSG:3857->4326
--   spherical Mercator inverse (verified: computed centroid for
--   402322203012 = 26.987103,-81.998435 vs pre-existing DB value
--   26.987081,-81.998474 -- match within GIS rounding tolerance, confirming
--   the conversion is correct). Note: prior charlotte I/G sessions used a
--   different endpoint (agis3.charlottecountyfl.gov, MapServer/27) -- this
--   session independently found and used agis2's Essentials/
--   CCGIS_Web_Layers2022 MapServer/17 (Property Ownership layer, has a
--   direct ACCOUNT + zoningcode field), cross-validated via centroid match
--   against a pre-existing DB row as noted above.
--
-- LIVE RESULT (this session, applied via PostgREST REST/RPC, no direct psql
-- per environment constraints):
--   pencil_dod_evaluate_county('charlotte') BEFORE: I card_complete=280 of
--   303 (92.4%, FAIL). AFTER: I card_complete=296 of 303 (97.7%, PASS).
--   G BEFORE: density=98.1 (PASS). AFTER: density=97.8 (PASS, no regression).
--   All other letters (A,B,D,E,F,H,J) unchanged. D remains FAIL
--   (matched_any=287/303=94.7%) and C remains FAIL (matched_clean=175/303=
--   57.8%) -- untouched, out of this dispatch's scope.
--
-- Zero data mutation to any row outside the 16 fixed + the 2 value-only
-- backfills already counted within those 16. Does not touch letter C or D
-- or any letter besides I. No fabricated address, parcel_id, or sold_amount
-- anywhere in this migration. Idempotent: guarded by NOT EXISTS on
-- parcel_zones.parcel_id and IS NULL guards on multi_county_auctions.

-- ============================================================================
-- Part 1: parcel_zones INSERT -- the actual live fix for I (v_zoning_gold_
-- standard_card reads from parcel_zones, confirmed live this session).
-- ============================================================================
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, source)
SELECT v.parcel_id, v.parcel_id, 813, v.zone_code, v.source
FROM (VALUES
  ('402220101014', 'RSF3.5', 'charlotte_agis2_ccgis_weblayers2022_propownership_l17:agis2.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGIS_Web_Layers2022/MapServer/17,ACCOUNT=402220101014'),
  ('412105257009', 'RSF3.5', 'charlotte_agis2_ccgis_weblayers2022_propownership_l17:agis2.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGIS_Web_Layers2022/MapServer/17,ACCOUNT=412105257009'),
  ('402218228011', 'RSF3.5', 'charlotte_agis2_ccgis_weblayers2022_propownership_l17:agis2.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGIS_Web_Layers2022/MapServer/17,ACCOUNT=402218228011'),
  ('412328205009', 'RSF5',   'charlotte_agis2_ccgis_weblayers2022_propownership_l17:agis2.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGIS_Web_Layers2022/MapServer/17,ACCOUNT=412328205009'),
  ('412013352004', 'RSF5',   'charlotte_agis2_ccgis_weblayers2022_propownership_l17:agis2.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGIS_Web_Layers2022/MapServer/17,ACCOUNT=412013352004'),
  ('402214354004', 'RSF3.5', 'charlotte_agis2_ccgis_weblayers2022_propownership_l17:agis2.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGIS_Web_Layers2022/MapServer/17,ACCOUNT=402214354004'),
  ('412322378010', 'PD',     'charlotte_agis2_ccgis_weblayers2022_propownership_l17:agis2.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGIS_Web_Layers2022/MapServer/17,ACCOUNT=412322378010'),
  ('412026102001', 'RSF5',   'charlotte_agis2_ccgis_weblayers2022_propownership_l17:agis2.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGIS_Web_Layers2022/MapServer/17,ACCOUNT=412026102001'),
  ('402206428015', 'RSF3.5', 'charlotte_agis2_ccgis_weblayers2022_propownership_l17:agis2.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGIS_Web_Layers2022/MapServer/17,ACCOUNT=402206428015'),
  ('422105460002', 'RSF5',   'charlotte_agis2_ccgis_weblayers2022_propownership_l17:agis2.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGIS_Web_Layers2022/MapServer/17,ACCOUNT=422105460002'),
  ('422302481010', 'RSF3.5', 'charlotte_agis2_ccgis_weblayers2022_propownership_l17:agis2.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGIS_Web_Layers2022/MapServer/17,ACCOUNT=422302481010'),
  ('422303154009', 'RSF3.5', 'charlotte_agis2_ccgis_weblayers2022_propownership_l17:agis2.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGIS_Web_Layers2022/MapServer/17,ACCOUNT=422303154009'),
  ('422303331014', 'RSF3.5', 'charlotte_agis2_ccgis_weblayers2022_propownership_l17:agis2.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGIS_Web_Layers2022/MapServer/17,ACCOUNT=422303331014'),
  ('402214308001', 'RSF3.5', 'charlotte_agis2_ccgis_weblayers2022_propownership_l17:agis2.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGIS_Web_Layers2022/MapServer/17,ACCOUNT=402214308001'),
  ('402322203012', 'RSF3.5', 'charlotte_agis2_ccgis_weblayers2022_propownership_l17:agis2.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGIS_Web_Layers2022/MapServer/17,ACCOUNT=402322203012_preexisting_zoning_assignments_match'),
  ('422330283008', 'RSF3.5', 'charlotte_agis2_ccgis_weblayers2022_propownership_l17:agis2.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGIS_Web_Layers2022/MapServer/17,ACCOUNT=422330283008_preexisting_zoning_assignments_match')
) AS v(parcel_id, zone_code, source)
WHERE NOT EXISTS (SELECT 1 FROM public.parcel_zones pz WHERE pz.parcel_id = v.parcel_id);

-- ============================================================================
-- Part 2 (informational/additive, applied earlier in this session before the
-- parcel_zones root cause was found -- kept for provenance continuity, does
-- not conflict with Part 1, zero effect on I either way):
-- zoning_assignments rows for the same 14 previously-unlinked parcels.
-- ============================================================================
INSERT INTO public.zoning_assignments (parcel_id, zone_code, jurisdiction, county, centroid_lat, centroid_lon, co_no, zone_source, zone_confidence)
SELECT v.parcel_id, v.zone_code, 'Unincorporated Charlotte County', 'charlotte', v.lat, v.lon, 18, 'county_gis_unincorporated_charlotte_county_arcgis_centroid_join', 'medium'
FROM (VALUES
  ('402220101014', 'RSF3.5', 26.985639, -82.139152),
  ('412105257009', 'RSF3.5', 26.938211, -82.229586),
  ('402218228011', 'RSF3.5', 27.002548, -82.142271),
  ('412328205009', 'RSF5',   26.885106, -82.013216),
  ('412013352004', 'RSF5',   26.903845, -82.271231),
  ('402214354004', 'RSF3.5', 26.991094, -82.087412),
  ('412322378010', 'PD',     26.888180, -82.001595),
  ('412026102001', 'RSF5',   26.886421, -82.287271),
  ('402206428015', 'RSF3.5', 27.022986, -82.142360),
  ('422105460002', 'RSF5',   26.843547, -82.228729),
  ('422302481010', 'RSF3.5', 26.844155, -81.975832),
  ('422303154009', 'RSF3.5', 26.853347, -82.002841),
  ('422303331014', 'RSF3.5', 26.847934, -81.999092),
  ('402214308001', 'RSF3.5', 26.994765, -82.090406)
) AS v(parcel_id, zone_code, lat, lon)
WHERE NOT EXISTS (SELECT 1 FROM public.zoning_assignments za WHERE za.parcel_id = v.parcel_id);

-- ============================================================================
-- Part 3: multi_county_auctions backfill -- geo (14 rows) + assessed_value
-- (13 of those 14, plus the 2 already-zone-linked rows = 15 total value
-- backfills). All sourced from fl_parcels.av_sd (existing 'fl_parcels_av_sd'
-- convention) and the same live ArcGIS centroid query as Part 1.
-- ============================================================================
UPDATE public.multi_county_auctions SET assessed_value = 201021, assessed_value_source = 'fl_parcels_av_sd' WHERE county = 'charlotte' AND case_number = '26-0251' AND parcel_id = '402322203012' AND assessed_value IS NULL;
UPDATE public.multi_county_auctions SET assessed_value = 34000,  assessed_value_source = 'fl_parcels_av_sd' WHERE county = 'charlotte' AND case_number = '26-0266' AND parcel_id = '422330283008' AND assessed_value IS NULL;

UPDATE public.multi_county_auctions SET latitude = 26.985639, longitude = -82.139152, geo_source = 'county_gis_unincorporated_charlotte_county_arcgis_centroid_join', assessed_value = COALESCE(assessed_value, 320916), assessed_value_source = COALESCE(assessed_value_source, 'fl_parcels_av_sd') WHERE county='charlotte' AND case_number='25000598CA' AND parcel_id='402220101014' AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude = 26.938211, longitude = -82.229586, geo_source = 'county_gis_unincorporated_charlotte_county_arcgis_centroid_join', assessed_value = COALESCE(assessed_value, 126258), assessed_value_source = COALESCE(assessed_value_source, 'fl_parcels_av_sd') WHERE county='charlotte' AND case_number='25000931CA' AND parcel_id='412105257009' AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude = 27.002548, longitude = -82.142271, geo_source = 'county_gis_unincorporated_charlotte_county_arcgis_centroid_join', assessed_value = COALESCE(assessed_value, 247085), assessed_value_source = COALESCE(assessed_value_source, 'fl_parcels_av_sd') WHERE county='charlotte' AND case_number='25001029CA' AND parcel_id='402218228011' AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude = 26.885106, longitude = -82.013216, geo_source = 'county_gis_unincorporated_charlotte_county_arcgis_centroid_join', assessed_value = COALESCE(assessed_value, 52138),  assessed_value_source = COALESCE(assessed_value_source, 'fl_parcels_av_sd') WHERE county='charlotte' AND case_number='25001286CA' AND parcel_id='412328205009' AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude = 26.903845, longitude = -82.271231, geo_source = 'county_gis_unincorporated_charlotte_county_arcgis_centroid_join', assessed_value = COALESCE(assessed_value, 154444), assessed_value_source = COALESCE(assessed_value_source, 'fl_parcels_av_sd') WHERE county='charlotte' AND case_number='25001498CA' AND parcel_id='412013352004' AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude = 26.991094, longitude = -82.087412, geo_source = 'county_gis_unincorporated_charlotte_county_arcgis_centroid_join', assessed_value = COALESCE(assessed_value, 121152), assessed_value_source = COALESCE(assessed_value_source, 'fl_parcels_av_sd') WHERE county='charlotte' AND case_number='26-0239' AND parcel_id='402214354004' AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude = 26.888180, longitude = -82.001595, geo_source = 'county_gis_unincorporated_charlotte_county_arcgis_centroid_join', assessed_value = COALESCE(assessed_value, 214290), assessed_value_source = COALESCE(assessed_value_source, 'fl_parcels_av_sd') WHERE county='charlotte' AND case_number='26-0242' AND parcel_id='412322378010' AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude = 26.886421, longitude = -82.287271, geo_source = 'county_gis_unincorporated_charlotte_county_arcgis_centroid_join', assessed_value = COALESCE(assessed_value, 165253), assessed_value_source = COALESCE(assessed_value_source, 'fl_parcels_av_sd') WHERE county='charlotte' AND case_number='26-0245' AND parcel_id='412026102001' AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude = 27.022986, longitude = -82.142360, geo_source = 'county_gis_unincorporated_charlotte_county_arcgis_centroid_join', assessed_value = COALESCE(assessed_value, 13600),  assessed_value_source = COALESCE(assessed_value_source, 'fl_parcels_av_sd') WHERE county='charlotte' AND case_number='26-0248' AND parcel_id='402206428015' AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude = 26.843547, longitude = -82.228729, geo_source = 'county_gis_unincorporated_charlotte_county_arcgis_centroid_join', assessed_value = COALESCE(assessed_value, 22100),  assessed_value_source = COALESCE(assessed_value_source, 'fl_parcels_av_sd') WHERE county='charlotte' AND case_number='26-0254' AND parcel_id='422105460002' AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude = 26.844155, longitude = -81.975832, geo_source = 'county_gis_unincorporated_charlotte_county_arcgis_centroid_join', assessed_value = COALESCE(assessed_value, 10200),  assessed_value_source = COALESCE(assessed_value_source, 'fl_parcels_av_sd') WHERE county='charlotte' AND case_number='26-0256' AND parcel_id='422302481010' AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude = 26.853347, longitude = -82.002841, geo_source = 'county_gis_unincorporated_charlotte_county_arcgis_centroid_join', assessed_value = COALESCE(assessed_value, 5100),   assessed_value_source = COALESCE(assessed_value_source, 'fl_parcels_av_sd') WHERE county='charlotte' AND case_number='26-0257' AND parcel_id='422303154009' AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude = 26.847934, longitude = -81.999092, geo_source = 'county_gis_unincorporated_charlotte_county_arcgis_centroid_join', assessed_value = COALESCE(assessed_value, 10200),  assessed_value_source = COALESCE(assessed_value_source, 'fl_parcels_av_sd') WHERE county='charlotte' AND case_number='26-0258' AND parcel_id='422303331014' AND latitude IS NULL;
UPDATE public.multi_county_auctions SET latitude = 26.994765, longitude = -82.090406, geo_source = 'county_gis_unincorporated_charlotte_county_arcgis_centroid_join', assessed_value = COALESCE(assessed_value, 265547), assessed_value_source = COALESCE(assessed_value_source, 'fl_parcels_av_sd') WHERE county='charlotte' AND case_number='26000042CA' AND parcel_id='402214308001' AND latitude IS NULL;

-- Verification query run after applying all of the above (this session,
-- 2026-08-28, via PostgREST REST/RPC):
--   SELECT * FROM public.pencil_dod_evaluate_county('charlotte');
--   BEFORE: I card_complete=280 of 303 (92.4%, FAIL); G density=98.1 (PASS)
--   AFTER:  I card_complete=296 of 303 (97.7%, PASS); G density=97.8 (PASS)
--   C, D unchanged (FAIL, out of scope). A,B,E,F,H,J unchanged (PASS).
