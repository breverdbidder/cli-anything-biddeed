-- shard10 run2346 (2026-07-02): nassau C/D/I fix + G-regression backfill
-- okaloosa was already 10/10 at session start; no changes needed there.
--
-- Applied LIVE this session via Supabase REST/PostgREST (service role key), not psql
-- (direct DB connection creds in this environment were stale — pooler + direct host
-- both rejected auth; REST API worked throughout). This file is a durable record
-- of the equivalent SQL for repo history / future migration replay.
--
-- Root problem: 7 of nassau's 34 multi_county_auctions rows (all upcoming auctions
-- dated 2026-07-09/07-16) had never been parity-checked or geocoded, holding C/D/I
-- at 79.4% (27/34). Real per-parcel centroid + zoning data was pulled live from
-- Nassau County Property Appraiser's own ArcGIS (maps.ncpafl.com/ncflpa_arcgis) --
-- NassauCountyPublicTaxMap/MapServer/144 (dsp_strap exact match -> polygon geometry,
-- centroid computed as vertex-average in WGS84) and GoMaps4_Citrix/MapServer/0
-- (HOUSE_NO+STREET match -> real ZoningDistrict/FutureLandUse fields).
--
-- 1) multi_county_auctions: 7 rows patched with latitude/longitude + parity_status.
UPDATE public.multi_county_auctions SET
  latitude = v.lat, longitude = v.lon,
  parity_status = 'matched_clean',
  parity_source = 'tier1_official_platform_parcel',
  parity_scope = 'supplementary_litmus_official_platforms_shard10_run2346',
  parity_checked_at = '2026-07-02T08:12:05Z'
FROM (VALUES
  ('f7daf600-0174-4846-87cc-d86286175f4c'::uuid, 30.638108378040943, -81.44901807626408),
  ('a662c9b2-b260-408b-8020-1d01951e5f03'::uuid, 30.606437572876654, -81.59441131356608),
  ('e78034ec-c414-45ea-bdd8-8aea17338250'::uuid, 30.61376785548377,  -81.59162085819392),
  ('be433462-787f-4202-bebd-5c9ebfef5250'::uuid, 30.623754643155372, -81.60369539905474),
  ('00f53ff4-a24a-4f16-9f97-047891aed6cf'::uuid, 30.624271012314825, -81.60397286866645),
  ('2936e525-9e4f-448f-86c0-358cf04598a8'::uuid, 30.568749722793687, -81.50190915036357),
  ('09025e65-77f0-4fec-95ae-068c6edcd915'::uuid, 30.599617208079323, -81.50637097749103)
) AS v(id, lat, lon)
WHERE multi_county_auctions.id = v.id;

-- 2) zoning_districts: RSF-2/PUD/WATER did not exist under jurisdiction 865
--    (City of Fernandina Beach) -- only R-1/R-1A/R-2/R-3/etc existed. These 3 new
--    codes are the Unincorporated Nassau County equivalents actually returned by
--    the county's own GIS for the 6 non-R-3 gap parcels (Yulee/unincorporated
--    addresses). Adding them under jurisdiction 865 matches the pre-existing
--    (imperfect) precedent of using one jurisdiction row for all of nassau.
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, description, ordinance_section) VALUES
  (865, 'RSF-2', 'Residential Single-Family Moderate-Low Density (RS-2 equiv.)', 'Residential',
   'Nassau County unincorporated LDC Art. 9 RS-1/RS-2 district; GIS shapefile code RSF-2 corresponds to ordinance RS-2', 'Art. 9 Sec. 9.01-9.06'),
  (865, 'PUD', 'Planned Unit Development', 'Planned Development',
   'Nassau County unincorporated LDC Art. 25 PUD; district ordinance sets no fixed density ceiling, density controlled by underlying Future Land Use map per Sec. 25.02(A)', 'Art. 25 Sec. 25.02-25.05'),
  (865, 'WATER', 'Water / Submerged Land', 'Conservation',
   'Open water / submerged land Future Land Use designation, not a buildable residential district', NULL);

-- 3) zone_standards: real values sourced from Nassau County's own LDC (via
--    zoneomics.com republication of Municode text -- Municode itself returns
--    HTTP 403 to automated fetch) and the county's 2030 Comprehensive Plan Future
--    Land Use Element (nassaucountyfl.com/DocumentCenter/View/29948, Table
--    "Residential Density Standards": LDR 0-2.0 du/a, MDR 0-3.0 du/a, HDR 3-10 du/a).
--    PUD has no ordinance-fixed density (Sec. 25.02(A): controlled by underlying
--    FLU); the value used (3.0 du/a, MDR) is a majority-weighted approximation --
--    3 of 4 backfilled PUD parcels are FLU=Medium Density, 1 (95521 Hanover Ct) is
--    FLU=Low Density (0-2.0 du/a) -- documented INFERRED, confidence_score=0.5.
--    WATER max_density_du_acre=0.0 reflects the real FutureLandUse=WATER
--    designation (non-buildable), confidence_score=0.9.
INSERT INTO public.zone_standards
  (zoning_district_id, min_lot_sqft, min_lot_width_ft, max_height_ft, front_setback_ft,
   side_setback_ft, rear_setback_ft, max_lot_coverage_pct, max_density_du_acre,
   source_url, ordinance_section, confidence_score)
SELECT zd.id, 8700, 75, 35, 25, 10, 10, 35, 3.0,
  'https://www.zoneomics.com/code/nassau-county-unincorporated-FL/chapter_9 (LDC Art.9); density=MDR ceiling per 2030 Comp Plan FLU Element (nassaucountyfl.com/DocumentCenter/View/29948), parcel FutureLandUse=MEDIUM DENSITY confirmed via maps.ncpafl.com GoMaps4_Citrix',
  'Art.9 Sec.9.04(B)(1)-(2), 9.05, 9.06', 0.75
FROM public.zoning_districts zd WHERE zd.jurisdiction_id = 865 AND zd.code = 'RSF-2';

INSERT INTO public.zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score)
SELECT zd.id, 3.0,
  'https://www.zoneomics.com/code/nassau-county-unincorporated-FL/chapter_29 (LDC Art.25 Sec.25.02(A): PUD density set by underlying FLU, no fixed ceiling; min site 10 upland acres Sec.25.03). Value=MDR FLU ceiling (0-3.0 du/a), majority of 4 backfilled PUD parcels; 1 (95521 Hanover Ct) is FLU=LOW DENSITY (0-2.0 du/a) -- district-level approximation, INFERRED',
  'Art.25 Sec.25.02-25.03', 0.5
FROM public.zoning_districts zd WHERE zd.jurisdiction_id = 865 AND zd.code = 'PUD';

INSERT INTO public.zone_standards (zoning_district_id, max_density_du_acre, source_url, confidence_score)
SELECT zd.id, 0.0,
  'maps.ncpafl.com GoMaps4_Citrix: FutureLandUse=WATER for 95076 Oelsner Dr (44-2N-28-5160-000A-0030) -- open water/submerged land, 0 du/a is accurate non-buildable density',
  0.9
FROM public.zoning_districts zd WHERE zd.jurisdiction_id = 865 AND zd.code = 'WATER';

-- 4) parcel_zones: link the 7 gap parcels (1 already-existing R-1... actually R-3
--    code existed with full standards already; only these 6 needed the new
--    zoning_districts/zone_standards rows above).
INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source) VALUES
  ('00-00-31-101G-0001-2169', '00-00-31-101G-0001-2169', 865, 'R-3', 'Multiple family dwelling district', 'shard10_run2346_nassau_ncpa_gis'),
  ('42-2N-27-4460-0027-0000', '42-2N-27-4460-0027-0000', 865, 'RSF-2', 'Residential Single-Family Moderate-Low Density (RS-2 equiv.)', 'shard10_run2346_nassau_ncpa_gis_ordinance_backed'),
  ('42-2N-27-4374-0028-0000', '42-2N-27-4374-0028-0000', 865, 'PUD', 'Planned Unit Development', 'shard10_run2346_nassau_ncpa_gis_ordinance_backed'),
  ('42-2N-27-1090-0079-0000', '42-2N-27-1090-0079-0000', 865, 'PUD', 'Planned Unit Development', 'shard10_run2346_nassau_ncpa_gis_ordinance_backed'),
  ('42-2N-27-1090-0121-0000', '42-2N-27-1090-0121-0000', 865, 'PUD', 'Planned Unit Development', 'shard10_run2346_nassau_ncpa_gis_ordinance_backed'),
  ('44-2N-28-5160-000A-0030', '44-2N-28-5160-000A-0030', 865, 'WATER', 'Water / Submerged Land', 'shard10_run2346_nassau_ncpa_gis_ordinance_backed'),
  ('41-2N-28-1140-0064-0000', '41-2N-28-1140-0064-0000', 865, 'PUD', 'Planned Unit Development', 'shard10_run2346_nassau_ncpa_gis_ordinance_backed');

-- NOTE ON THE G-REGRESSION CAUGHT MID-SESSION: the first attempt (7 parcel_zones
-- rows with zone_code only, no matching zoning_districts/zone_standards) flipped
-- G from PASS (100%) to FAIL (0%) because v_zoning_district_applicability had no
-- record for RSF-2/PUD/WATER and treated them as measurable-but-missing rather
-- than N/A. Those 6 rows were deleted, the zoning_districts+zone_standards backfill
-- above was applied, then the 6 parcel_zones rows were re-inserted. Final state:
-- nassau A-J all PASS (10/10), okaloosa unaffected (still 10/10).
