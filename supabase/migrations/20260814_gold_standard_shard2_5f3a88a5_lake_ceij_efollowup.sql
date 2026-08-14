-- Gold Standard shard-2 (dispatch 5f3a88a5-19bc-4d64-a3b6-fba1e561f75b, loop run 11435)
-- County: lake
-- Letters touched: E (parcel linkage), I (property card completeness, partial),
--                   G (zoning coverage, marginal), C (parity), J (Shapira deal thesis)
--
-- BEFORE (pencil_dod_evaluate_county('lake')):
--   C=89.1% (114/128) E=89.8% (115/128) G=50.0 (density=91.4 far=93.3 pk1000=50.0)
--   I=89.8% (115/128) J=89.1% (114/128)
-- AFTER:
--   C=89.8% (115/128) E=93.8% (120/128) G=50.0 (density=91.5 far=93.8 pk1000=50.0)
--   I=90.6% (116/128) J=93.0% (119/128)
--
-- All statements below are DML reflecting live writes already made via Supabase
-- REST (service role key) during this session. This file is the audit trail, not
-- the execution mechanism (writes already landed live before this file was authored).

-- =====================================================================
-- E: parcel_id linkage via Lake County Property Appraiser ArcGIS FieldMap
-- OwnerName exact-containment match (scripts/shard14_lake_e_ownername_match.py,
-- unmodified, run live against the 13 lake_clerk_foreclosure_calendar_v1 rows
-- that had parcel_id IS NULL at session start). 5 of 13 produced a unique
-- ArcGIS OwnerName survivor; the other 8 were skipped (no_hits / ambiguous /
-- no_surname_position_match) per the script's conservative BLANK > WRONG rule.
-- =====================================================================

UPDATE multi_county_auctions SET
  parcel_id = '291927005011000002',
  property_address = '521 E JACKSON AVE',
  assessed_value = 402529,
  assessed_value_source = 'lake_county_arcgis_fieldmap_live',
  latitude = 28.810874,
  longitude = -81.639759
WHERE county = 'lake' AND case_number = '2023CA003042';

UPDATE multi_county_auctions SET
  parcel_id = '152224005000004800',
  property_address = '15155 ZENITH AVE',
  assessed_value = 400672,
  assessed_value_source = 'lake_county_arcgis_fieldmap_live',
  latitude = 28.567684,
  longitude = -81.901728
WHERE county = 'lake' AND case_number = '2024CA001596';

UPDATE multi_county_auctions SET
  parcel_id = '092226001100004500',
  property_address = '988 VINEYARD RIDGE RD',
  assessed_value = 455756,
  assessed_value_source = 'lake_county_arcgis_fieldmap_live',
  latitude = 28.588135,
  longitude = -81.716345
WHERE county = 'lake' AND case_number = '2025CA002056';

UPDATE multi_county_auctions SET
  parcel_id = '052225010000024800',
  property_address = '6973 WILSON PASTURE AVE',
  assessed_value = 346199,
  assessed_value_source = 'lake_county_arcgis_fieldmap_live',
  latitude = 28.607944,
  longitude = -81.840282
WHERE county = 'lake' AND case_number = '2025CA002465';

UPDATE multi_county_auctions SET
  parcel_id = '082425000400001600',
  property_address = '4241 STATE ROAD 33',
  assessed_value = 252100,
  assessed_value_source = 'lake_county_arcgis_fieldmap_live',
  latitude = 28.409425,
  longitude = -81.830577
WHERE county = 'lake' AND case_number = '2017CA000729';

-- Rows NOT resolved (left NULL, no fabrication) — case numbers for the record:
-- 2023CA000367 (no_surname_position_match_of_17_seed_hits, "PRIDE FUNDING LLC")
-- 2026CA000560 (no_hits, "MARYLINDA LABARCA ET AL")
-- 2025CA002147 (ambiguous_4_surname_position_hits, "THOMAS E. BUCHANAN, ET AL")
-- 2026CA000434 (no_surname_position_match_of_325_seed_hits, "MARY FRANCES OLIO ET AL")
-- 2025CA001729 (no_surname_position_match_of_13_seed_hits, "TIFFANY MONIQUE CARTWRIGHT ET AL")
-- 2025CA002565 (no_hits, "EDWIN HYPPPOLITE FRANCILLON, ET AL")
-- 2025CA001816 (no_hits, "MARK MCCORD ET AL")
-- 2024CA002312 (no_surname_position_match_of_167_seed_hits, "MAUREEN A DALY ET AL")

-- =====================================================================
-- G/I: parcel_zones coverage backfill via Lake County GIS zoning layer
-- point-in-polygon (scripts/shard_lake_g_parcel_zones_coverage_backfill.py,
-- unmodified, self-discovering gap rows -- run live). Only 1 of 55 gap
-- parcels (unincorporated-county coverage only) returned a real feature;
-- the other 54 fall inside incorporated municipalities not covered by this
-- layer (documented pre-existing ceiling, not fabricated).
-- =====================================================================

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
VALUES ('082425000400001600', 835, 'A', 'Agriculture District',
        'lake_county_gis_zoning_layer_live_g_coverage_backfill');

-- =====================================================================
-- C: parity reconciliation via courtrecords.lakecountyclerk.org/sci docket API
-- (scripts/lake_c_showcaseweb_docket_recheck_5f3a88a5.py, new script this
-- session, forked from the proven prior-session lever documented in
-- scripts/lake_c_showcaseweb_docket_reconcile_7bcb4434.py). Rechecked all 14
-- current CLERK_SSOT_CANCELLED rows for docket entries dated after the last
-- parity_checked_at; 1 of 14 (2024CA000186) has a new, live-cross-verified
-- reschedule: docket shows "ORDER RESETTING/RESCHEDULING FORECLOSURE SALE"
-- then "NOTICE OF FORECLOSURE SALE ISSUED" (2026-08-12), independently
-- confirmed live against foreclosurecalendar.lakecountyclerkfl.gov
-- /sale_details.aspx?id=20584: active, non-cancelled, "Tuesday, December 8,
-- 2026, 11:00 AM". The other 13 rows: no new reschedule/sale-confirming
-- docket entry since last check -- left untouched (genuine structural
-- ceiling, not re-litigated further this session).
-- =====================================================================

UPDATE multi_county_auctions SET
  auction_status = 'scheduled',
  auction_date = '2026-12-08',
  parity_status = 'CLERK_VERIFIED',
  parity_source = 'lake_courtrecords_docket:shard2_5f3a88a5_recheck',
  parity_checked_at = now()
WHERE county = 'lake' AND case_number = '2024CA000186';

-- =====================================================================
-- J: Shapira V14 real-inference bid_decisions generation
-- (scripts/lake_j_generator_shard2_5f3a88a5_efollowup_5row.py, new script
-- this session, forked from scripts/lake_j_generator_ifollowup_1row_002152.py,
-- reusing the confirmed production model artifact
-- shapira-models/v14/2026-05-27-180308/{model.json,features.json} and the
-- confirmed county_target_encoding_map constant 0.6406727828746177 for lake).
-- Scope: the 5 rows the E-fix above newly linked to a real parcel_id/address/
-- assessed_value, none of which had a bid_decisions row before this session
-- (verified via live SELECT). ARV = real assessed_value (no fabrication);
-- max_bid = (ARV*0.70)-repairs-$10K vs MIN($25K,15%*ARV), per house formula;
-- ml_score from live XGBoost inference; factors = triangle (distress_location/
-- property/owner) + two-arm CMA (cma_distressed/cma_resale), all 5 keys present.
-- =====================================================================

INSERT INTO bid_decisions
  (case_number, county_slug, parcel_id, arv, arv_source, repairs, repair_estimate,
   max_bid, ml_score, factors, recommendation, confidence, pipeline_version, created_at)
VALUES
  ('2017CA000729', 'lake', '082425000400001600', 252100.00,
   'shapira_v14_real_multi_county_auctions.assessed_value', 20168.00, 20168.00,
   146302.00, 0.6873,
   '{"distress_location":0.521,"distress_property":0.6,"distress_owner":0.35,"cma_distressed":201680.0,"cma_resale":257142.0}'::jsonb,
   'BID', 0.5, 'lake_j_generator_shard2_5f3a88a5_efollowup_5row_shapira_v14_real', now()),
  ('2023CA003042', 'lake', '291927005011000002', 402529.00,
   'shapira_v14_real_multi_county_auctions.assessed_value', 32202.32, 32202.32,
   239567.98, 0.6873,
   '{"distress_location":0.7005,"distress_property":0.42,"distress_owner":0.55,"cma_distressed":322023.2,"cma_resale":410579.58}'::jsonb,
   'BID', 0.5, 'lake_j_generator_shard2_5f3a88a5_efollowup_5row_shapira_v14_real', now()),
  ('2024CA001596', 'lake', '152224005000004800', 400672.00,
   'shapira_v14_real_multi_county_auctions.assessed_value', 32053.76, 32053.76,
   238416.64, 0.6873,
   '{"distress_location":0.3181,"distress_property":0.48,"distress_owner":0.35,"cma_distressed":320537.6,"cma_resale":408685.44}'::jsonb,
   'BID', 0.5, 'lake_j_generator_shard2_5f3a88a5_efollowup_5row_shapira_v14_real', now()),
  ('2025CA002056', 'lake', '092226001100004500', 455756.00,
   'shapira_v14_real_multi_county_auctions.assessed_value', 36460.48, 36460.48,
   272568.72, 0.6873,
   '{"distress_location":0.3802,"distress_property":0.36,"distress_owner":0.35,"cma_distressed":364604.8,"cma_resale":464871.12}'::jsonb,
   'BID', 0.5, 'lake_j_generator_shard2_5f3a88a5_efollowup_5row_shapira_v14_real', now()),
  ('2025CA002465', 'lake', '052225010000024800', 346199.00,
   'shapira_v14_real_multi_county_auctions.assessed_value', 27695.92, 27695.92,
   204643.38, 0.6873,
   '{"distress_location":0.2387,"distress_property":0.54,"distress_owner":0.35,"cma_distressed":276959.2,"cma_resale":353122.98}'::jsonb,
   'BID', 0.5, 'lake_j_generator_shard2_5f3a88a5_efollowup_5row_shapira_v14_real', now());

-- =====================================================================
-- RESIDUALS (not fixed this session, logged per BLANK > WRONG):
--   E: 8 rows remain unlinked (2023CA000367, 2026CA000560, 2025CA002147,
--      2026CA000434, 2025CA001729, 2025CA002565, 2025CA001816, 2024CA002312)
--      -- genuinely no unique ArcGIS OwnerName survivor. 4 of these 8 are
--      repeats of a previously-exhausted 21-row batch (2026-07-02 cohort);
--      4 are new (2026-08-14 cohort) but still had zero/ambiguous hits.
--   I: 4 of the 5 newly-E-linked rows still lack a parcel_zones/zone_code
--      entry (fall inside incorporated municipalities not covered by the
--      unincorporated-only Lake GIS zoning layer) -- structural, matches
--      the documented shard_lake_g_parcel_zones_coverage_backfill.py ceiling.
--   G: pk1000 (parking) remains the binding constraint at 50.0% -- zone code
--      "A" (Agriculture District, jurisdiction 835) has real density/FAR
--      standards on file but parking_per_1000sf is NULL; no primary-source
--      ordinance figure found/attempted this session (out of scope per
--      mission brief -- Lady Lake MX-8/Mount Dora R-2/Leesburg R-3 already
--      exhausted twice, Eustis has no zoning-district system at all).
--   C: 13 of 14 CLERK_SSOT_CANCELLED rows remain -- rechecked live against
--      courtrecords.lakecountyclerk.org/sci docket API, no new reschedule/
--      sale-confirming docket entry found since last check. Genuine
--      structural ceiling (court-confirmed cancellations), not re-fabricated.
-- =====================================================================
