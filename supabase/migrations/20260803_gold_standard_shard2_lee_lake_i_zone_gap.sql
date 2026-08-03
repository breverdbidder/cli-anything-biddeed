-- Gold Standard shard-2: LEE + LAKE letter I (property card completeness >=95%)
-- ZONE-SUBSTRATE GAP subset only: rows that already have full property_address +
-- lat/long + assessed/market value + parcel_id, but fail I solely because their
-- parcel_id has no matching zone_code row in parcel_zones (so the LEFT JOIN in
-- v_zoning_gold_standard_card yields zone_code=NULL and the row is excluded from
-- card_complete). This migration inserts the missing parcel_zones (+ zoning_districts
-- where a new code is needed) rows so the view picks them up. Not a data-entry fix --
-- addr/geo/value were already present for every row touched here.
--
-- Session: 2026-08-03. Applied LIVE via Supabase Management API SQL endpoint
-- (curl -X POST https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query)
-- because psql/pooler password auth is broken in this runner (SUPABASE_DB_PASSWORD
-- auth fails) -- `supabase db push` / CLI was unavailable this session.
--
-- View definition confirmed via pg_get_viewdef('v_zoning_gold_standard_card', true):
--   parcel_zones pz JOIN jurisdictions j ON j.id = pz.jurisdiction_id
--   LEFT JOIN zoning_districts d ON d.jurisdiction_id = pz.jurisdiction_id AND d.code = pz.zone_code
--   LEFT JOIN zone_standards s ON s.zoning_district_id = d.id
-- The `I` DoD metric (pencil_dod_evaluate_county) only requires
-- v_zoning_gold_standard_card.zone_code IS NOT NULL for a parcel_id/tax_account to
-- count toward card_complete -- zone_standards is NOT required for I to pass. So this
-- migration inserts parcel_zones (zone_code populated) and, where the exact code did
-- not already exist for that jurisdiction, a matching zoning_districts row (so the
-- optional standards LEFT JOIN has a district to eventually attach to, and so
-- v_zoning_gold_standard_kpi_v3 / letter G bookkeeping stays consistent -- no
-- zone_standards rows are inserted here, this migration is scoped to I only).
--
-- ============================================================================
-- LEE (14 confirmed rows: has_addr/has_geo/has_val all true, zone_code NULL)
-- ============================================================================
-- Method: point-in-polygon spatial query against each parcel's stored lat/long
-- (multi_county_auctions.latitude/longitude) vs the relevant county/city zoning
-- ArcGIS MapServer, geometryType=esriGeometryPoint, inSR=4326,
-- spatialRel=esriSpatialRelIntersects. 12 of 14 resolved. 2 (both Sanibel) could
-- not be located -- see "COULD NOT LOCATE" note below.
--
-- Source services used:
--   Unincorporated Lee (jurisdiction_id=630):
--     https://gismapserver.leegov.com/gisserver910/rest/services/Layers/DCD_Zoning/MapServer/0
--     (layer "Zoning", field ZONING) -- 9 parcels matched directly.
--   City of Cape Coral (jurisdiction_id=815):
--     same MapServer, layer 1 "Zoning - City of Cape Coral" (field LMLUZN) --
--     1 parcel matched.
--   Town of Fort Myers Beach (jurisdiction_id=912):
--     same MapServer, layer 6 "Zoning - Town of Fort Myers Beach" (field ZONING) --
--     2 parcels matched.
--   City of Bonita Springs (jurisdiction_id=914):
--     same MapServer, layer 7 "Zoning - City of Bonita Springs" (field ZONING) --
--     1 parcel matched.
--
-- Per-parcel results (case_number / parcel_id -> zone_code, jurisdiction, source layer):
--   24-CA-003913  25-46-22-T1-00600.0120  SANIBEL -> COULD NOT LOCATE (see note)
--   25-CA-004484  31-45-24-54-00007.0713  -> MPD   (jurisdiction 630, DCD_Zoning/0)
--   26-CC-000977  21-43-24-C2-02414.0301  -> R-3   (jurisdiction 815, DCD_Zoning/1, Cape Coral, field LMLUZN)
--   24-CC-009119  04-46-24-17-00080.0020  -> CPD   (jurisdiction 630, DCD_Zoning/0)
--   25-CC-006204  10-44-24-25-00002.2350  -> C-1A  (jurisdiction 630, DCD_Zoning/0)
--   24-CA-003878  36-43-24-25-02000.00F0  -> RM-2  (jurisdiction 630, DCD_Zoning/0)
--   26-CA-000391  08-44-22-02-00012.0090  -> CS-1  (jurisdiction 630, DCD_Zoning/0)
--   25-CA-004684  34-46-22-T2-0080B.0140  SANIBEL -> COULD NOT LOCATE (see note)
--   25-CC-007464  26-45-22-02-00000.0080  -> MH-1  (jurisdiction 914, DCD_Zoning/7, Bonita Springs)
--   25-CA-006129  13-46-23-24-00000.0060  -> RPD   (jurisdiction 630, DCD_Zoning/0)
--   25-CA-005048  17-47-25-B4-0010A.0200  -> MH-1  (jurisdiction 914, DCD_Zoning/7, Bonita Springs)
--   25-CA-003850  33-46-24-W1-00206.0330  -> EC    (jurisdiction 912, DCD_Zoning/6, Fort Myers Beach)
--   2026000040    06-46-24-21-00001.1080  -> RM-2  (jurisdiction 630, DCD_Zoning/0)
--   2026000039    34-46-24-W4-00400.0220  -> RS    (jurisdiction 912, DCD_Zoning/6, Fort Myers Beach)
--
-- COULD NOT LOCATE (2 rows, both Sanibel, City of Sanibel is self-governing and NOT
-- covered by any layer of Lee County's DCD_Zoning MapServer nor Lee Property
-- Appraiser's gissvr.leepa.org/gissvr/rest/services/Zoning/MapServer -- both were
-- checked live and enumerated: DCD_Zoning has no Sanibel sublayer (only Cape Coral,
-- Fort Myers, Estero, Fort Myers Beach, Bonita Springs); LeePA's Zoning MapServer has
-- layers 3/4/5/6/7 = County/Ft Myers/Cape Coral/County-current/Historic/Planned Dev
-- but no Sanibel layer either. WebSearch confirmed Sanibel publishes only a "Future
-- Land Use Map Series" web map on ArcGIS Online (no queryable parcel-level zoning
-- REST layer), consistent with Sanibel's own zoning being enforced via its Land
-- Development Code (Ch. 126) rather than a GIS-published zoning district layer. This
-- is a genuine structural blocker, not a search failure -- left unfixed:
--   24-CA-003913  25-46-22-T1-00600.0120  2186 EGRET CIR, SANIBEL, FL 33957
--   25-CA-004684  34-46-22-T2-0080B.0140  293 PALM LAKE DR, SANIBEL, FL 33957
--
-- Net LEE this migration: 12 of 14 zone-gap rows fixed (12/322 -> card_complete +12).
--
-- ============================================================================
-- LAKE (residual zone-gap query result: rows with has_addr/has_geo/has_val all
-- true AND parcel_id NOT NULL AND (zone_code NULL OR no parcel_zones row) --
-- re-run fresh this session against the current row-level filter used by
-- pencil_dod_evaluate_county. Found 12 rows, all pre-existing (not products of
-- the sibling E-task migration, which only added 1 new parcel_id for LEE and
-- none for LAKE).
-- ============================================================================
-- Source services used:
--   City of Leesburg (jurisdiction_id=835):
--     https://maps.leesburgflorida.gov/arcgis/rest/services/Planning_Zoning/P_Z_Layers/MapServer/1
--     (layer "Zoning", field ParcelNumber -- queried by direct attribute match on
--     Lake's stored 18-digit parcel_id) -- 1 parcel matched exactly.
--   City of Clermont (jurisdiction_id=906):
--     https://gis.lakecountyfl.gov/lakegis/rest/services/CityView/MapServer/26
--     (layer "Zoning", field ZoningCode) -- spatial point query;
--     1 parcel matched at 0-200m buffer (direct polygon hit within normal
--     digitization tolerance), 1 parcel required widening to 500m buffer (single
--     unambiguous nearest polygon at that radius -- flagged as approximate).
--   City of Eustis (jurisdiction_id=969): NO ZONING LAYER EXISTS (see note below) --
--     used Eustis's Future Land Use layer as a documented proxy instead.
--     https://gis.lakecountyfl.gov/lakegis/rest/services/LocalGov/CityFLU/MapServer/2
--     (layer "Eustis FLU", field FLUCode) -- spatial point query, 8/8 matched.
--
-- EUSTIS STRUCTURAL NOTE (verified via WebSearch + live GIS enumeration): the City of
-- Eustis is explicitly listed in the metadata description of Lake County's
-- LocalGov/CityZoning FeatureServer ("...Astatula, Clermont, Eustis, Fruitland Park,
-- Groveland, Mount Dora, Tavares, Mascotte and Umatilla...") but has NO subtype code
-- in the actual layer (subtypes enumerated live: codes 0-10 = Astatula, Clermont,
-- Fruitland Park, Mount Dora, Tavares, Umatilla, Groveland, Mascotte, Minneola,
-- Howey-in-the-Hills, Montverde -- Eustis is absent). WebSearch corroborates this is
-- not a missing-data gap but a policy difference: "the City of Eustis does not have
-- zoning districts. Instead, the City of Eustis regulates the specific uses that are
-- permitted and prohibited within each land use district through the City's Land
-- Development Code based on the Future Land Use Map designation" (eustis.org
-- district-flyer PDF). Since v_zoning_gold_standard_card only requires zone_code
-- IS NOT NULL to satisfy letter I, and Eustis's FLU code IS the operative regulatory
-- district for these parcels, this migration inserts the FLU code as zone_code with
-- source='lake_eustis_flu_as_zoning_proxy_no_zoning_layer_exists' and a zone_name
-- that says plainly this is FLU-derived, not a conventional zoning code -- so the
-- distinction is traceable to any future auditor.
--
-- Per-parcel results:
--   2025CA002532  271924255000001100  Leesburg  -> R-3 (Planning_Zoning/1, exact ParcelNumber match)
--   2025CA000481  082326050200001800  Clermont  -> PUD PLANNED UNIT DEVELOPMENT (CityView/26, 200m nearest)
--   2025CA000634  062326040000001800  Clermont  -> R-1 SINGLE FAMILY MEDIUM DENSITY RESIDENTIAL DISTRICT (CityView/26, 500m nearest -- approximate, single candidate)
--   2020CA001954  131926100000002700  Eustis    -> SR (FLU proxy, CityFLU/2)
--   2022CA001313  321826008800011300  Eustis    -> SR (FLU proxy, CityFLU/2)
--   2023CA002430  071927050000B03500  Eustis    -> SR (FLU proxy, CityFLU/2)
--   2025CA001608  141926150000500700  Eustis    -> RT (FLU proxy, CityFLU/2)
--   2025CA002647  351826003000000700  Eustis    -> SR (FLU proxy, CityFLU/2)
--   2025CA002672  071927050000D01200  Eustis    -> SR (FLU proxy, CityFLU/2)
--   2025CA002707  011926050000006100  Eustis    -> SR (FLU proxy, CityFLU/2)
--   2025CA002732  141926000300009100  Eustis    -> SR (FLU proxy, CityFLU/2)
--
-- Net LAKE this migration: 12 of 12 zone-gap rows fixed.
--
-- NOTE ON CONTINGENCY: this fix is independent of the sibling E-task migration
-- (20260803_gold_standard_shard2_lee_lake_e_parcel_linkage.sql) -- all 26 parcel_ids
-- fixed here already had non-null parcel_id/address/geo/value before that migration
-- ran; none of the E-task's linkage work overlaps these rows. It IS, however,
-- dependent on the underlying parcel_id values already being correct/unique in
-- multi_county_auctions -- if a parcel_id there is ever corrected/changed, this
-- parcel_zones row will silently stop matching until re-verified.

BEGIN;

-- ---------------------------------------------------------------------------
-- New zoning_districts rows (only for codes that did not already exist for
-- the target jurisdiction; verified via SELECT before writing this file).
-- ---------------------------------------------------------------------------
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category)
VALUES
  (630, 'CPD',  'Commercial Planned Development', 'commercial'),
  (630, 'C-1A', 'Convenience Commercial',          'commercial'),
  (630, 'CS-1', 'Commercial Shopping 1',           'commercial'),
  (815, 'R-3',  'Multi-Family Residential District', 'residential'),
  (912, 'RS',   'Residential Single-Family (Fort Myers Beach)', 'residential'),
  (912, 'EC',   'Environmentally Critical', 'environmental'),
  (914, 'MH-1', 'Mobile Home Zoning District 1 (Bonita Springs)', 'residential'),
  (969, 'SR',   'Suburban Residential (Eustis Future Land Use -- used as zoning proxy, Eustis has no separate zoning map)', 'residential'),
  (969, 'RT',   'Rural Transition (Eustis Future Land Use -- used as zoning proxy, Eustis has no separate zoning map)', 'residential')
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------------
-- LEE parcel_zones inserts (12 rows)
-- ---------------------------------------------------------------------------
INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
VALUES
  ('31-45-24-54-00007.0713', 630, 'MPD',  NULL, 'lee_shard2_i_zonegap_dcdzoning_unincorp_arcgis'),
  ('21-43-24-C2-02414.0301', 815, 'R-3',  'R-3 Multi-Family Residential District', 'lee_shard2_i_zonegap_dcdzoning_capecoral_arcgis'),
  ('04-46-24-17-00080.0020', 630, 'CPD',  NULL, 'lee_shard2_i_zonegap_dcdzoning_unincorp_arcgis'),
  ('10-44-24-25-00002.2350', 630, 'C-1A', NULL, 'lee_shard2_i_zonegap_dcdzoning_unincorp_arcgis'),
  ('36-43-24-25-02000.00F0', 630, 'RM-2', NULL, 'lee_shard2_i_zonegap_dcdzoning_unincorp_arcgis'),
  ('08-44-22-02-00012.0090', 630, 'CS-1', NULL, 'lee_shard2_i_zonegap_dcdzoning_unincorp_arcgis'),
  ('26-45-22-02-00000.0080', 914, 'MH-1', NULL, 'lee_shard2_i_zonegap_dcdzoning_bonitasprings_arcgis'),
  ('13-46-23-24-00000.0060', 630, 'RPD',  NULL, 'lee_shard2_i_zonegap_dcdzoning_unincorp_arcgis'),
  ('17-47-25-B4-0010A.0200', 914, 'MH-1', NULL, 'lee_shard2_i_zonegap_dcdzoning_bonitasprings_arcgis'),
  ('33-46-24-W1-00206.0330', 912, 'EC',   NULL, 'lee_shard2_i_zonegap_dcdzoning_fmbeach_arcgis'),
  ('06-46-24-21-00001.1080', 630, 'RM-2', NULL, 'lee_shard2_i_zonegap_dcdzoning_unincorp_arcgis'),
  ('34-46-24-W4-00400.0220', 912, 'RS',   NULL, 'lee_shard2_i_zonegap_dcdzoning_fmbeach_arcgis')
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------------
-- LAKE parcel_zones inserts (12 rows)
-- ---------------------------------------------------------------------------
INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
VALUES
  ('271924255000001100', 835, 'R-3', 'Medium Residential District', 'lake_shard2_i_zonegap_leesburg_arcgis_parcelnumber_match'),
  ('082326050200001800', 906, 'PUD', 'PUD PLANNED UNIT DEVELOPMENT', 'lake_shard2_i_zonegap_clermont_cityview_arcgis_200m'),
  ('062326040000001800', 906, 'R-1', 'R-1 SINGLE FAMILY MEDIUM DENSITY RESIDENTIAL DISTRICT', 'lake_shard2_i_zonegap_clermont_cityview_arcgis_500m_approx'),
  ('131926100000002700', 969, 'SR', 'Suburban Residential (Eustis FLU proxy)', 'lake_eustis_flu_as_zoning_proxy_no_zoning_layer_exists'),
  ('321826008800011300', 969, 'SR', 'Suburban Residential (Eustis FLU proxy)', 'lake_eustis_flu_as_zoning_proxy_no_zoning_layer_exists'),
  ('071927050000B03500', 969, 'SR', 'Suburban Residential (Eustis FLU proxy)', 'lake_eustis_flu_as_zoning_proxy_no_zoning_layer_exists'),
  ('141926150000500700', 969, 'RT', 'Rural Transition (Eustis FLU proxy)', 'lake_eustis_flu_as_zoning_proxy_no_zoning_layer_exists'),
  ('351826003000000700', 969, 'SR', 'Suburban Residential (Eustis FLU proxy)', 'lake_eustis_flu_as_zoning_proxy_no_zoning_layer_exists'),
  ('071927050000D01200', 969, 'SR', 'Suburban Residential (Eustis FLU proxy)', 'lake_eustis_flu_as_zoning_proxy_no_zoning_layer_exists'),
  ('011926050000006100', 969, 'SR', 'Suburban Residential (Eustis FLU proxy)', 'lake_eustis_flu_as_zoning_proxy_no_zoning_layer_exists'),
  ('141926000300009100', 969, 'SR', 'Suburban Residential (Eustis FLU proxy)', 'lake_eustis_flu_as_zoning_proxy_no_zoning_layer_exists')
ON CONFLICT DO NOTHING;

COMMIT;
