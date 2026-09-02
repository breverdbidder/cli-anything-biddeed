-- Lake county letter I (card_complete) denominator-drift fix, session 2026-09-02.
--
-- Baseline (fresh pencil_dod_evaluate_county('lake')): I = card_complete 134/147 (91.2%), FAIL.
-- Denominator = 147 real (non-propertyonion) auction rows
-- (data_source IN lake_clerk_foreclosure_calendar_v1 / calendar_sweep_mca_v3 / null).
--
-- Diagnosis:
--   - 5 of 147 rows have NO parcel_id at all (2025CA001179, 2025CA002825, 2026CA000632,
--     2026CA000030, 2026CA000927) -- E-agent's job per task scope, skipped here (parcel_id
--     IS NULL precondition not met for I).
--   - Of the remaining 142 parcel-linked rows, ALL already have real property_address,
--     lat/lon, and assessed_value/market_value populated. The sole remaining I-blocker for
--     these rows was zone_code resolution via parcel_zones.
--   - 8 parcel-linked rows had zero parcel_zones coverage. 1 of those
--     (011926060000202200, case 2024CA002034) is the sole remaining genuinely
--     GIS-blocked parcel -- confirmed live against EVERY Lake County zoning source this
--     session has access to (unincorporated InteractiveMap/MapServer/50, and all
--     LocalGov/CityZoning MapServer layers: Astatula, Clermont, Fruitland Park, Groveland,
--     Mount Dora, Tavares, Umatilla, Mascotte, Minneola, Howey-in-the-Hills, Montverde,
--     plus dedicated Eustis CityFLU/MapServer/2 and Leesburg
--     maps.leesburgflorida.gov/.../Planning_Zoning layers, plus newly-discovered Lady Lake
--     services5.arcgis.com/WSrmy5ECedUbsQ39 Zoning/FeatureServer/0) -- no feature returned
--     for its centroid in any layer. NOT re-attempted further; left untouched, no fabricated
--     data written. (Note: the other 2 of the original "3 permanently blocked" parcels named
--     in this session's task brief -- 052225010000001900 and 221924085000000100 -- were
--     found ALREADY RESOLVED in parcel_zones by a prior session, sourced
--     lake_county_gis_arcgis / leesburg_fl_gis_arcgis respectively; only
--     011926060000202200 remains genuinely blocked as of this session.)
--
-- Fix: 7 real, sourced parcel_zones INSERTs for the 7 resolvable rows, using each row's
-- on-file real lat/lon against the correct live GIS zoning layer for its municipality
-- (unincorporated Lake, Eustis, Lady Lake, Clermont, Leesburg). Zero coordinates invented,
-- zero zone codes guessed -- every value traces to a live ArcGIS point-in-polygon/attribute
-- query response for that exact parcel.
--
-- IMPORTANT side-effect caught and fixed in the same session: the first insert used the
-- verbatim ArcGIS attribute string "PUD PLANNED UNIT DEVELOPMENT" for the Clermont row
-- (jurisdiction_id=906), which did not match Clermont's existing zoning_districts.code
-- value "PUD" (id=13004, already used by 10 other Lake/Clermont parcel_zones rows). This
-- introduced a brand-new (jurisdiction_id, zone_code) combo with no zone_standards row,
-- which regressed letter G (zoning density/FAR/parking coverage) from PASS 96.0% to FAIL
-- 66.7%. Corrected by normalizing that one row's zone_code to "PUD" to match the
-- established Clermont convention (same physical zoning designation, just the county's own
-- normalized code instead of the raw GIS label) -- NOT a fabrication, a format alignment.
-- G was re-verified back to PASS (96.2%, slightly above the pre-fix baseline) immediately
-- after the correction, per CLAUDE.md's "never move one passing letter to fix another
-- without flagging it" guardrail.
--
-- Net effect (verified via pencil_dod_evaluate_county('lake'), run twice for cache safety):
--   I: card_complete 134/147 (91.2%) FAIL -> 141/147 (95.9%) PASS
--   G: unaffected after the PUD-code correction -> 96.2% PASS (was 96.0% PASS baseline)
--   No other letter touched or regressed (C was already FAIL at 86.4% pre-existing, out of
--   scope for this dispatch, unaffected: 87.8% after, natural denominator drift not
--   attributable to this fix).
--
-- Residual (6 of 147, exact reconciliation 147-141=6):
--   5 rows: no parcel_id at all -- E-agent scope, not attempted here.
--   1 row: 011926060000202200 (2024CA002034) -- genuinely GIS-blocked, no zoning coverage
--     from any reachable Lake County source. Documented, not fabricated.

BEGIN;

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
VALUES
  ('021926000300001700', 969, 'SR', 'Suburban Residential (Eustis FLU district)',
   'eustis_cityflu_gis_live_lake_i_7row_2026-09-02'),
  ('061824039400029250', 869, 'MX-8', NULL,
   'ladylake_zoning_featureserver_live_lake_i_7row_2026-09-02'),
  ('162226191000001600', 906, 'PUD', 'Planned Unit Development',
   'clermont_cityzoning_gis_live_lake_i_7row_2026-09-02'),
  ('221924100000A00300', 835, 'R-2', NULL,
   'leesburg_planning_zoning_gis_live_lake_i_7row_2026-09-02'),
  ('222025120000101000', 835, 'PUD', 'Planned Unit Development',
   'lake_county_gis_zoning_layer_live_lake_i_7row_2026-09-02'),
  ('241926095000001400', 969, 'SR', 'Suburban Residential (Eustis FLU district)',
   'eustis_cityflu_gis_live_lake_i_7row_2026-09-02'),
  ('282326001200030700', 835, 'PUD', 'Planned Unit Development',
   'lake_county_gis_zoning_layer_live_lake_i_7row_2026-09-02');

COMMIT;
