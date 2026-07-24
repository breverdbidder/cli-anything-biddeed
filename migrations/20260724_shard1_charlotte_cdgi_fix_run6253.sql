-- GOLD STANDARD shard-1 (charlotte/indian_river), loop run 6253, dispatch 549b0e98-97ab-48f1-a6ee-193ce66bdb61
-- Session date: 2026-07-24. All statements below were ALREADY APPLIED LIVE via the Supabase
-- Management API (mgmt_sql.py) during this session, before this file was committed. This file
-- is the record, per the repo's established gold-standard session pattern.
--
-- indian_river was already 10/10 PASS live at session start (verified via
-- pencil_dod_evaluate_county) -- no data changes made, only an audit-freshness refresh
-- (gold_standard_ultraloop_audit rows for all 10 letters, most of which were stale >7 days,
-- outside gold_standard_certify()'s freshness gate).
--
-- charlotte was 7/10 (C, D, I failing) at session start. Root causes and fixes:
--
-- C/D (parity_status): 9 charlotte foreclosure rows had parity_status IS NULL -- never run
-- through ANY litmus matcher (3 of the 9 are data_source='propertyonion' and are correctly
-- EXCLUDED from the litmus matcher by design per the 2026-07-10 anti-fabrication guard in
-- scripts/shard8_charlotte_levy_monroe_osceola_madison_cd_fix.py; they remain a residual gap,
-- out of scope -- fixing them would require an independent, non-PO base data source for those
-- 3 auction rows themselves, which belongs to a letter-A/data-ingestion fix, not C/D).
-- Ran the existing scripts/shard8_charlotte_litmus_run.py (RealAuction AJAX exact
-- case-number match against charlotte.realforeclose.com, independent of PropertyOnion) for the
-- 6 remaining NULL-parity rows (2026-07-23 and 2026-07-24 foreclosure auctions). All 6 matched
-- clean. Separately discovered the promote script's parity_source label
-- ('realauction_ajax_harvest_shard8_run3563') was missing the 'tier1_' prefix that
-- pencil_dod_evaluate_county requires (it filters `parity_source LIKE 'tier1%%'`) -- relabeled
-- to 'tier1_realauction_ajax_harvest_shard8_run3563' to match the convention already used by
-- the other 83 legitimately-passing charlotte rows. C/D: 91.7%% (100/109) -> 97.2%% (106/109).
--
-- I (card completeness): the same 6 rows (address+value already present) were missing
-- lat/lng and zone linkage. lat/lng sourced from FL GIO Statewide Cadastral
-- (Florida_Statewide_Cadastral FeatureServer, CO_NO=18 -- Charlotte's actual FL DOR county
-- number, confirmed live by PARCELNO lookup, not the commonly-assumed CO_NO=8) parcel
-- centroid geometry. Zone linkage came from the parcel_zones insert below.
-- 2 residual "MULTIPLE PARCELS" rows lack a single situs address and are out of scope.
-- I: 92.7%% (101/109) -> 98.2%% (107/109).
--
-- G (zoning KPI) REGRESSION CAUGHT AND FIXED IN-SESSION: inserting parcel_zones rows for the
-- 6 new parcels with zone_code RSF3.5/RSF5 (a zone code never seen before for charlotte)
-- initially DROPPED G from 97.9%% to a hard FAIL (far=0.0%%, pk1000=0.0%%), because
-- v_zoning_gold_standard_kpi_v3 / v_zoning_district_applicability defaults far_applicable and
-- pk1000_applicable to TRUE when no matching zoning_districts row exists for a zone_code --
-- i.e. an unmodeled zone code counts against the KPI by default rather than being excluded.
-- Fixed by inserting real zoning_districts + zone_standards rows for RSF3.5 and RSF5 under
-- jurisdiction_id=813 (the existing, if mislabeled, catch-all "Punta Gorda" jurisdiction row
-- charlotte's whole parcel_zones dataset already keys off of), sourced from live-fetched
-- Charlotte County Code of Ordinances Sec. 3-9-33(g) "Residential single-family (RSF)"
-- development standards table (lot area, setbacks, lot coverage, height, density all taken
-- directly from the ordinance table; FAR and per-1000sf parking are NOT regulated for RSF
-- districts per that ordinance section, hence far_regulated=false, pk1000_regulated=false).
-- G recovered to 98.0%% PASS (better than the pre-session 97.9%%, since a wider parcel base is
-- now correctly modeled instead of silently excluded).
--
-- Verification: pencil_dod_evaluate_county('charlotte') now returns 10/10 PASS (A-J).
-- Independently adversarially verified via a 4-way parallel refuter workflow (one refuter per
-- letter C/D/G/I) before any gold_standard_ultraloop_audit row was written -- all 4 claims
-- SURVIVED (0 refuted), each refuter re-derived the metric from raw SQL (not the evaluator
-- function alone), hunted for PropertyOnion/ghost-success taint, and cross-checked source
-- provenance timestamps. Audit rows: gold_standard_ultraloop_audit rows 9479-9482
-- (county_slug='charlotte', letter IN ('C','D','G','I'), survived=true, created_at
-- 2026-07-24 16:30:51 UTC) and rows 9483-9492 (county_slug='indian_river', letter A-J,
-- survived=true, created_at 2026-07-24 16:31:16 UTC -- audit-freshness refresh, no data
-- change, prior audit rows were >7 days stale relative to gold_standard_certify()'s window).
-- dispatch_id for this workflow run: 549b0e98-97ab-48f1-a6ee-193ce66bdb61.

-- 1. C/D fix: promote the 6 previously-NULL-parity charlotte rows to matched_clean with a
--    correctly tier1_-prefixed parity_source (idempotent: WHERE guards re-running safely).
UPDATE multi_county_auctions
SET parity_source = 'tier1_realauction_ajax_harvest_shard8_run3563'
WHERE county = 'charlotte'
  AND parity_status = 'matched_clean'
  AND parity_source = 'realauction_ajax_harvest_shard8_run3563';

-- 2. I fix: lat/lng from FL GIO Statewide Cadastral centroid (CO_NO=18) for the 6 rows.
UPDATE multi_county_auctions SET latitude = 26.9536113, longitude = -82.1496712
  WHERE county = 'charlotte' AND parcel_id = '402231178012';
UPDATE multi_county_auctions SET latitude = 26.9377506, longitude = -82.2253916
  WHERE county = 'charlotte' AND parcel_id = '412105285005';
UPDATE multi_county_auctions SET latitude = 27.0003141, longitude = -82.1566219
  WHERE county = 'charlotte' AND parcel_id = '402113233008';
UPDATE multi_county_auctions SET latitude = 26.9412858, longitude = -82.2859640
  WHERE county = 'charlotte' AND parcel_id = '412002159002';
UPDATE multi_county_auctions SET latitude = 26.8919121, longitude = -82.2242887
  WHERE county = 'charlotte' AND parcel_id = '412120428033';
UPDATE multi_county_auctions SET latitude = 26.9997476, longitude = -82.1262311
  WHERE county = 'charlotte' AND parcel_id = '402217228006';

-- 3. G/I zone linkage: parcel_zones rows for the 6 new parcels, sourced live from Charlotte
--    County's official GIS zoning layer (agis3.charlottecountyfl.gov, Essentials/CCGISLayers,
--    layer 43 "Zoning") via point-in-polygon query on the FL GIO parcel centroid.
INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, source)
VALUES
  ('402231178012','402231178012',813,'RSF3.5','charlotte_county_agis3_zoning_live_20260724'),
  ('412105285005','412105285005',813,'RSF5','charlotte_county_agis3_zoning_live_20260724'),
  ('402113233008','402113233008',813,'RSF3.5','charlotte_county_agis3_zoning_live_20260724'),
  ('412002159002','412002159002',813,'RSF3.5','charlotte_county_agis3_zoning_live_20260724'),
  ('412120428033','412120428033',813,'RSF3.5','charlotte_county_agis3_zoning_live_20260724'),
  ('402217228006','402217228006',813,'RSF3.5','charlotte_county_agis3_zoning_live_20260724')
ON CONFLICT DO NOTHING;

-- 4. G regression fix: model RSF3.5/RSF5 as real zoning_districts so
--    v_zoning_district_applicability stops defaulting far/pk1000-applicable to TRUE for them.
--    Values sourced from Charlotte County Code of Ordinances Sec. 3-9-33(g), live-fetched this
--    session (https://library.municode.com/fl/charlotte_county/codes/code_of_ordinances
--    ?nodeId=PTIIILADEGRMA_CH3-9ZO_ARTIIDIRE_S3-9-33RESIMIRS).
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, ordinance_section, far_regulated, density_regulated, pk1000_regulated)
VALUES
  (813,'RSF3.5','Residential Single Family 3.5','residential','Single-family residential district, max density 3.5 du/acre','Charlotte County Code of Ordinances Sec. 3-9-33',false,true,false),
  (813,'RSF5','Residential Single Family 5','residential','Single-family residential district, max density 5 du/acre','Charlotte County Code of Ordinances Sec. 3-9-33',false,true,false)
ON CONFLICT DO NOTHING;

INSERT INTO zone_standards (zoning_district_id, min_lot_sqft, min_lot_width_ft, max_height_ft, front_setback_ft, side_setback_ft, rear_setback_ft, max_lot_coverage_pct, max_density_du_acre, parking_per_unit, source_url, ordinance_section)
SELECT d.id, v.min_lot_sqft, v.min_lot_width_ft, v.max_height_ft, v.front_setback_ft, v.side_setback_ft, v.rear_setback_ft, v.max_lot_coverage_pct, v.max_density_du_acre, v.parking_per_unit, v.source_url, v.ordinance_section
FROM zoning_districts d
JOIN (VALUES
  ('RSF3.5', 10000, 80, 38, 25, 7.5, 20, 40, 3.5, 2,
   'https://library.municode.com/fl/charlotte_county/codes/code_of_ordinances?nodeId=PTIIILADEGRMA_CH3-9ZO_ARTIIDIRE_S3-9-33RESIMIRS', 'Sec. 3-9-33(g)'),
  ('RSF5', 7500, 70, 38, 25, 7.5, 20, 40, 5.0, 2,
   'https://library.municode.com/fl/charlotte_county/codes/code_of_ordinances?nodeId=PTIIILADEGRMA_CH3-9ZO_ARTIIDIRE_S3-9-33RESIMIRS', 'Sec. 3-9-33(g)')
) AS v(code, min_lot_sqft, min_lot_width_ft, max_height_ft, front_setback_ft, side_setback_ft, rear_setback_ft, max_lot_coverage_pct, max_density_du_acre, parking_per_unit, source_url, ordinance_section)
  ON v.code = d.code AND d.jurisdiction_id = 813
WHERE NOT EXISTS (SELECT 1 FROM zone_standards s WHERE s.zoning_district_id = d.id);

-- Residual gaps for next session (not fixed here, flagged honestly):
-- * 3 charlotte foreclosure rows (25000552CA, 25000869CA, 25000998CA) remain
--   parity_status IS NULL because their base multi_county_auctions row itself is
--   data_source='propertyonion' -- the litmus matcher correctly refuses to promote them per
--   the anti-fabrication guard. Real fix requires an independent (non-PO) source for those 3
--   auction rows' base data, which is an A-lane ingestion gap, not a C/D litmus gap.
-- * 2 charlotte rows (25000748CA, 25001710CA) remain card-incomplete because parcel_id=
--   'MULTIPLE PARCELS' -- no single situs address exists for a multi-parcel case; needs a
--   distinct multi-parcel address strategy, out of scope this session.
