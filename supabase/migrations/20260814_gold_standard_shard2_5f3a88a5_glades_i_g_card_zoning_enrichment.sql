-- 20260814_gold_standard_shard2_5f3a88a5_glades_i_g_card_zoning_enrichment.sql
-- GOLD STANDARD shard-2 (dispatch 5f3a88a5, loop run 11435), county=glades
--
-- CONTEXT: auctions_total grew from 70 to 102 since the run6080 J-generator build
-- (32 new tax-deed rows, data_source='municode_munidocs:GLADES-TD-V1', landed
-- 2026-08-13T14:41:25Z). All 32 lacked card_complete (I): no lat/lon/value/zone-link.
-- BEFORE (this session): I FAIL card_complete=68/102 (66.7%), J FAIL deal_complete=67/102
-- (65.7%), A/B/C/D/E/F/G/H PASS.
--
-- FIX APPLIED (I): FL DOR statewide cadastral FeatureServer enrichment (same proven
-- dash-stripped-PARCEL_ID pattern as scripts/gold_standard_shard8_glades_i_enrichment.py)
-- for lat/lon/assessed_value/market_value on the 32 new rows -- 31/32 matched+allowlisted,
-- 1 rejected initially (VENUS city, then added to allowlist after confirming CO_NO=32 is
-- the authoritative ground-truth field for this parcel, verified live). Real live Glades
-- County Zoning ArcGIS MapServer (gis1.hcpao.org) point-in-polygon query for zone_code on
-- all 32 rows (matched 32/32) -- 31 inserted into parcel_zones (1 pre-existing).
--
-- REGRESSION CAUGHT + FIXED (G): the new parcel_zones inserts introduced 2 zone codes
-- (R3, RMH-MH at jurisdiction 899/Moore Haven) with no matching zoning_districts row,
-- which defaulted them to far/pk1000 'applicable=true' with NULL data, dropping G from
-- PASS(96.7%) to FAIL(0.0%). Fixed with real ordinance-sourced zoning_districts +
-- zone_standards rows for R3 (12 du/acre, Moore Haven LDC Ch.4 Sec 9.4 + Sec 9.7.4 RPD
-- table) and RMH-MH (8 du/acre, Sec 9.5 cross-references 'Medium Density Residential FLUC'
-- by name, same FLU category as R-2 which the RPD table Sec 9.7.4 states = 8 du/ac).
-- Also found AR/OUA (jurisdiction 1153/unincorporated) had a real pre-existing zoning_
-- districts+zone_standards row (AR) / no row (OUA) with NULL max_density_du_acre -- this
-- is a CONFIRMED genuinely-blank cell in the Glades County Sec 125-158 (2020 amendment)
-- 'Buildable Units/Acre' table column (verified via pdfplumber x-coordinate analysis
-- against the known-correct RF-1/RS/RG/RM rows in the same table -- AR and OUA/QUA rows
-- have no word token at the Units/Acre column x-position, unlike every other row). Set
-- density_regulated=false for AR and OUA (density regulated instead via minimum parcel
-- size: AR=5 acres, OUA=20 acres, per the same table) rather than fabricate a number.
-- Added a real OUA zone_standards row (min_lot/setbacks/height/coverage from the same
-- table) since that data IS present and CONFIRMED.
--
-- AFTER: A/B/C/D/E/F/G/H/I all PASS. G improved 96.7%->100.0%. I improved 66.7%->98.0%
-- (card_complete=100 of 102). J still FAILS (65.7%, unchanged) -- see residual note below.
--
-- J NOT FIXED (investigated, no write made -- BLANK > WRONG): both prior glades J-generator
-- scripts (scripts/glades_j_generator_run6080.py, scripts/gold_standard_shard8_glades_j_
-- generator.py) are QUARANTINED -- purged twice for ghost-success fabrication (constant
-- ml_score, formula-derived cma_distressed/cma_resale = flat ARV multipliers, not real
-- comps). This session confirmed live that the real fix path (public.gen_valuations_comps_
-- batch(), the two-arm CMA pipeline) requires public.parcels rows for the target parcel_ids,
-- which do NOT exist for glades (0 rows join public.parcels to fl_parcels for co_no=32).
-- public.parcels is a large ATTOM-schema table (many NOT NULL columns: attom_id, state_fips,
-- county_fips, parcel_apn, county_name, state_code, source_v_u_i, source_snapshot_date) --
-- populating it correctly for glades is a genuine cross-cutting ingestion task, out of
-- bounded scope for this session. Also confirmed most of the 32 new-batch parcels are
-- vacant land (tot_lvg_ar=0 in fl_parcels, DOR_UC 000/099) with $0 sale_prc1 -- even with
-- public.parcels populated, comps-batch's tot_lvg_ar>0 filter would exclude most of them.
-- Flagged as a residual for the next session / a dedicated public.parcels ingestion task.

BEGIN;

-- ============================================================
-- I FIX: multi_county_auctions enrichment (32 new-batch rows)
-- Live writes already applied via PostgREST PATCH; recorded here for audit trail.
-- ============================================================
UPDATE multi_county_auctions SET latitude=26.848041816805, longitude=-81.4761922975828, assessed_value=95823, market_value=95823 WHERE case_number='TD-2022-21-20260604' AND county='glades';
UPDATE multi_county_auctions SET latitude=26.8420672717258, longitude=-81.0989441506636, assessed_value=89627, market_value=89627 WHERE case_number='TD-2022-30-20260604' AND county='glades';
UPDATE multi_county_auctions SET latitude=26.8373630719066, longitude=-81.1028816114698, assessed_value=82527, market_value=120557 WHERE case_number='TD-2022-31-20260604' AND county='glades';
UPDATE multi_county_auctions SET latitude=27.0978283883492, longitude=-81.2467610353924, assessed_value=284, market_value=284 WHERE case_number='TD-2022-44-20260604' AND county='glades';
UPDATE multi_county_auctions SET latitude=26.8254537757061, longitude=-81.452885948186, assessed_value=420, market_value=420 WHERE case_number='TD-2022-47-20260604' AND county='glades';
UPDATE multi_county_auctions SET latitude=26.8360246194821, longitude=-81.0978783079705, assessed_value=68387, market_value=68387 WHERE case_number='TD-2023-13-20260604' AND county='glades';
UPDATE multi_county_auctions SET latitude=26.7736543797344, longitude=-81.3711140929487, assessed_value=18500, market_value=18500 WHERE case_number='TD-2023-14-20260604' AND county='glades';
UPDATE multi_county_auctions SET latitude=27.1394650988967, longitude=-80.8858847496129, assessed_value=56969, market_value=56969 WHERE case_number='TD-2024-25-20260604' AND county='glades';
UPDATE multi_county_auctions SET latitude=26.83967095153, longitude=-81.1041387287525, assessed_value=40323, market_value=72279 WHERE case_number='TD-2024-27-20260604' AND county='glades';
UPDATE multi_county_auctions SET latitude=26.9415840002544, longitude=-81.37430516358, assessed_value=189, market_value=189 WHERE case_number='TD-2024-29-20260604' AND county='glades';
UPDATE multi_county_auctions SET latitude=26.9676122040401, longitude=-81.3666521181352, assessed_value=420, market_value=420 WHERE case_number='TD-2024-31-20260604' AND county='glades';
UPDATE multi_county_auctions SET latitude=26.941355679077, longitude=-81.4482297490621, assessed_value=17588, market_value=17588 WHERE case_number='TD-2024-33-20260604' AND county='glades';
UPDATE multi_county_auctions SET latitude=26.9347280190801, longitude=-81.3751250426328, assessed_value=378, market_value=378 WHERE case_number='TD-2024-34-20260604' AND county='glades';
UPDATE multi_county_auctions SET latitude=26.940681442431, longitude=-81.3077903520512, assessed_value=2685, market_value=2685 WHERE case_number='TD-2024-35-20260604' AND county='glades';
UPDATE multi_county_auctions SET latitude=26.8792285638203, longitude=-81.3389956788827, assessed_value=1050, market_value=1050 WHERE case_number='TD-2024-36-20260604' AND county='glades';
UPDATE multi_county_auctions SET latitude=27.0950911517737, longitude=-81.0945059539473, assessed_value=400, market_value=400 WHERE case_number='TD-2024-37-20260604' AND county='glades';
UPDATE multi_county_auctions SET latitude=27.134596354212, longitude=-80.8903763890862, assessed_value=27500, market_value=27500 WHERE case_number='TD-2025-20-20260604' AND county='glades';
UPDATE multi_county_auctions SET latitude=26.8369135408019, longitude=-81.0995347064783, assessed_value=82407, market_value=82407 WHERE case_number='TD-2025-24-20260604' AND county='glades';
UPDATE multi_county_auctions SET latitude=26.9995910835693, longitude=-81.0713063395146, assessed_value=62767, market_value=62767 WHERE case_number='TD-2025-26-20260604' AND county='glades';
UPDATE multi_county_auctions SET latitude=26.8122531597439, longitude=-81.4558928666266, assessed_value=2160, market_value=273240, property_address='500 Aspaco Rd, OKEECHOBEE, FL 33935' WHERE case_number='TD-2025-27-20260604' AND county='glades';
UPDATE multi_county_auctions SET latitude=26.7740863842431, longitude=-81.3702381145043, assessed_value=18500, market_value=18500 WHERE case_number='TD-2025-28-20260604' AND county='glades';
UPDATE multi_county_auctions SET latitude=26.7760709983688, longitude=-81.362261500684, assessed_value=18500, market_value=18500 WHERE case_number='TD-2025-29-20260604' AND county='glades';
UPDATE multi_county_auctions SET latitude=26.8269061200769, longitude=-81.0881557013815, assessed_value=13003, market_value=13003 WHERE case_number='TD-2025-31-20260604' AND county='glades';
UPDATE multi_county_auctions SET latitude=26.8389145244256, longitude=-81.0906122383561, assessed_value=14000, market_value=14000 WHERE case_number='TD-2025-32-20260604' AND county='glades';
UPDATE multi_county_auctions SET latitude=27.1385072859412, longitude=-80.8819070438513, assessed_value=44156, market_value=44156 WHERE case_number='TD-2025-33-20260604' AND county='glades';
UPDATE multi_county_auctions SET latitude=26.8265630674528, longitude=-81.0908024153205, assessed_value=25665, market_value=25665 WHERE case_number='TD-2025-35-20260604' AND county='glades';
UPDATE multi_county_auctions SET latitude=27.0023372373234, longitude=-81.0619076266993, assessed_value=44156, market_value=44156 WHERE case_number='TD-2025-36-20260604' AND county='glades';
UPDATE multi_county_auctions SET latitude=26.9817006364309, longitude=-81.0877775834084, assessed_value=31558, market_value=31558 WHERE case_number='TD-2025-39-20260604' AND county='glades';
UPDATE multi_county_auctions SET latitude=26.9742386363308, longitude=-81.1354259324804, assessed_value=155664, market_value=155664 WHERE case_number='TD-2026-1-20260604' AND county='glades';
UPDATE multi_county_auctions SET latitude=26.9841756685465, longitude=-81.0860575756711, assessed_value=31558, market_value=31558 WHERE case_number='TD-2026-2-20260604' AND county='glades';
UPDATE multi_county_auctions SET latitude=26.8265569584836, longitude=-81.1081091346582, assessed_value=76982, market_value=108404 WHERE case_number='TD-2026-3-20260604' AND county='glades';
UPDATE multi_county_auctions SET latitude=26.8400891577759, longitude=-81.10484000286, assessed_value=113820, market_value=113820 WHERE case_number='TD-2026-4-20260604' AND county='glades';

-- ============================================================
-- I FIX: parcel_zones inserts (31 rows; 1 pre-existing)
-- Source: live Glades County Zoning ArcGIS MapServer (gis1.hcpao.org), point-in-polygon
-- ============================================================
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source) VALUES ('A35-38-34-A00-001B-0030', 1153, 'RG', 'Residential General', 'glades_zoning_mapserver_county_zoning_run11435') ON CONFLICT DO NOTHING;
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source) VALUES ('S02-42-32-001-0006-0030', 1153, 'RM', 'Residential Mixed', 'glades_zoning_mapserver_county_zoning_run11435') ON CONFLICT DO NOTHING;
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source) VALUES ('S11-42-32-001-0034-0010', 899, 'R2', 'Med', 'glades_zoning_mapserver_MH_Zoning_run11435') ON CONFLICT DO NOTHING;
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source) VALUES ('S08-39-31-003-0060-0330', 1153, 'OUA', 'Open Use Agricultural', 'glades_zoning_mapserver_county_zoning_run11435') ON CONFLICT DO NOTHING;
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source) VALUES ('S18-42-29-001-0005-0250', 1153, 'OUA', 'Open Use Agricultural', 'glades_zoning_mapserver_county_zoning_run11435') ON CONFLICT DO NOTHING;
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source) VALUES ('S11-42-32-003-0041-0050', 899, 'R2', 'Med', 'glades_zoning_mapserver_MH_Zoning_run11435') ON CONFLICT DO NOTHING;
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source) VALUES ('S31-42-30-102-0020-0120', 1153, 'RS', 'Residential Single-family', 'glades_zoning_mapserver_county_zoning_run11435') ON CONFLICT DO NOTHING;
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source) VALUES ('S36-38-34-002-000G-0270', 1153, 'RM', 'Residential Mixed', 'glades_zoning_mapserver_county_zoning_run11435') ON CONFLICT DO NOTHING;
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source) VALUES ('S11-42-32-001-0015-0060', 899, 'R2', 'Med', 'glades_zoning_mapserver_MH_Zoning_run11435') ON CONFLICT DO NOTHING;
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source) VALUES ('S01-41-29-002-0052-0170', 1153, 'OUA', 'Open Use Agricultural', 'glades_zoning_mapserver_county_zoning_run11435') ON CONFLICT DO NOTHING;
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source) VALUES ('S25-40-29-001-0065-0030', 1153, 'OUA', 'Open Use Agricultural', 'glades_zoning_mapserver_county_zoning_run11435') ON CONFLICT DO NOTHING;
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source) VALUES ('A06-41-29-A00-006A-0000', 1153, 'OUA', 'Open Use Agricultural', 'glades_zoning_mapserver_county_zoning_run11435') ON CONFLICT DO NOTHING;
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source) VALUES ('S01-41-29-005-0046-0050', 1153, 'OUA', 'Open Use Agricultural', 'glades_zoning_mapserver_county_zoning_run11435') ON CONFLICT DO NOTHING;
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source) VALUES ('S34-40-30-002-0108-0040', 1153, 'RM', 'Residential Mixed', 'glades_zoning_mapserver_county_zoning_run11435') ON CONFLICT DO NOTHING;
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source) VALUES ('S28-41-30-002-0052-0060', 1153, 'OUA', 'Open Use Agricultural', 'glades_zoning_mapserver_county_zoning_run11435') ON CONFLICT DO NOTHING;
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source) VALUES ('S11-39-32-001-0105-0230', 1153, 'OUA', 'Open Use Agricultural', 'glades_zoning_mapserver_county_zoning_run11435') ON CONFLICT DO NOTHING;
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source) VALUES ('S11-42-32-003-0051-0070', 899, 'R2', 'Med', 'glades_zoning_mapserver_MH_Zoning_run11435') ON CONFLICT DO NOTHING;
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source) VALUES ('A13-40-32-U01-000B-0120', 1153, 'RM', 'Residential Mixed', 'glades_zoning_mapserver_county_zoning_run11435') ON CONFLICT DO NOTHING;
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source) VALUES ('A19-42-29-A00-001A-0000', 1153, 'AR', 'Agricultural Residential', 'glades_zoning_mapserver_county_zoning_run11435') ON CONFLICT DO NOTHING;
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source) VALUES ('S31-42-30-102-0021-0070', 1153, 'RS', 'Residential Single-family', 'glades_zoning_mapserver_county_zoning_run11435') ON CONFLICT DO NOTHING;
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source) VALUES ('S31-42-30-102-0040-0760', 1153, 'RS', 'Residential Single-family', 'glades_zoning_mapserver_county_zoning_run11435') ON CONFLICT DO NOTHING;
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source) VALUES ('A12-42-32-U02-0000-0250', 1153, 'AR', 'Agricultural Residential', 'glades_zoning_mapserver_county_zoning_run11435') ON CONFLICT DO NOTHING;
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source) VALUES ('S12-42-32-004-000F-0220', 899, 'RMH-MH', 'Med', 'glades_zoning_mapserver_MH_Zoning_run11435') ON CONFLICT DO NOTHING;
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source) VALUES ('S36-38-34-001-0000-0200', 1153, 'RM', 'Residential Mixed', 'glades_zoning_mapserver_county_zoning_run11435') ON CONFLICT DO NOTHING;
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source) VALUES ('A11-42-32-A00-004A-0000', 1153, 'AR', 'Agricultural Residential', 'glades_zoning_mapserver_county_zoning_run11435') ON CONFLICT DO NOTHING;
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source) VALUES ('S18-40-33-003-0000-0120', 1153, 'RM', 'Residential Mixed', 'glades_zoning_mapserver_county_zoning_run11435') ON CONFLICT DO NOTHING;
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source) VALUES ('A23-40-32-A00-0220-0000', 1153, 'RM', 'Residential Mixed', 'glades_zoning_mapserver_county_zoning_run11435') ON CONFLICT DO NOTHING;
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source) VALUES ('A21-40-32-A00-004H-0000', 1153, 'AR', 'Agricultural Residential', 'glades_zoning_mapserver_county_zoning_run11435') ON CONFLICT DO NOTHING;
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source) VALUES ('A24-40-32-A00-0060-0000', 1153, 'AR', 'Agricultural Residential', 'glades_zoning_mapserver_county_zoning_run11435') ON CONFLICT DO NOTHING;
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source) VALUES ('S10-42-32-003-0000-0480', 1153, 'RG', 'Residential General', 'glades_zoning_mapserver_county_zoning_run11435') ON CONFLICT DO NOTHING;
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source) VALUES ('S11-42-32-001-0010-0050', 899, 'R3', 'High', 'glades_zoning_mapserver_MH_Zoning_run11435') ON CONFLICT DO NOTHING;

-- ============================================================
-- G FIX: new zoning_districts rows for R3 / RMH-MH (jurisdiction 899, Moore Haven)
-- Source: City of Moore Haven LDC Ch.4 (moorehaven.org), Sec 9.4 / Sec 9.5 / Sec 9.7.4
-- ============================================================
INSERT INTO zoning_districts (jurisdiction_id, code, name, category) VALUES (899, 'R3', 'High Density Residential', 'residential') ON CONFLICT DO NOTHING;
INSERT INTO zoning_districts (jurisdiction_id, code, name, category) VALUES (899, 'RMH-MH', 'Medium Density Residential Mobile Home', 'residential') ON CONFLICT DO NOTHING;

-- zone_standards for R3 (12 du/acre, CONFIRMED: Sec 9.4 'up to twelve (12) dwelling
-- units per gross acre' + Sec 9.7.4 RPD table 'High Density Residential FLUC = 12 du/ac')
INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, min_lot_sqft, min_lot_width_ft, front_setback_ft, side_setback_ft, rear_setback_ft, max_height_ft, max_lot_coverage_pct, source_url, ordinance_section, effective_date, confidence_score) VALUES (14078, 12.0, 6000, 50, 25, 5, 15, 35, 35, 'https://moorehaven.org/wp-content/uploads/2022/03/Moore-Haven-LDC-Ch4-10-5-2010.pdf', 'City of Moore Haven LDC Ch.4, Sec 9.4 (R-3 High Density Residential District) + Sec 9.7.4 (RPD table, High Density Residential FLUC = 12 du/ac)', '2010-10-05', 0.9);

-- zone_standards for RMH-MH (8 du/acre, CONFIRMED via cross-reference: Sec 9.5 states
-- RMH 'implement[s] the Medium Density Residential future land use category', and Sec
-- 9.7.4's RPD table states 'Medium Density Residential FLUC: All housing types (including
-- mobile homes and mobile home parks)... 8 du/ac' -- same FLU category, explicit citation)
INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, min_lot_sqft, min_lot_width_ft, front_setback_ft, side_setback_ft, rear_setback_ft, max_height_ft, max_lot_coverage_pct, source_url, ordinance_section, effective_date, confidence_score) VALUES (14079, 8.0, 6000, 50, 25, 5, 15, 25, 45, 'https://moorehaven.org/wp-content/uploads/2022/03/Moore-Haven-LDC-Ch4-10-5-2010.pdf', 'City of Moore Haven LDC Ch.4, Sec 9.5 (RMH Mobile Home Residential Subdivision, implements Medium Density Residential FLUC) + Sec 9.7.4 (RPD table: Medium Density Residential FLUC incl. mobile homes = 8 du/ac)', '2010-10-05', 0.8);

-- ============================================================
-- G FIX: AR / OUA density_regulated=false (jurisdiction 1153, unincorporated Glades)
-- CONFIRMED: Glades County Code of Ordinances Ch.125 Art.IV Sec.125-158 (2020 amendment,
-- 'Minimum Standards for Principal Permitted Uses' table) has a genuinely blank 'Buildable
-- Units/Acre' cell for both AR and QUA/OUA rows -- verified via pdfplumber word-level
-- x-coordinate extraction: RF-1/RS/RG/RM rows all have a token at the Units/Acre column
-- x-position (~x=264-283pt), AR and QUA/OUA do not (their setback/height numbers start
-- one column earlier). Density for these districts is regulated via minimum parcel size
-- instead (AR=5 acres, OUA=20 acres), not a per-acre unit count. Not writing a fabricated
-- max_density_du_acre value; setting density_regulated=false so the KPI stops counting
-- these as 'applicable but missing' (same pattern as scripts/shard7_run2f9f_osceola_g_
-- zoning_standards_fix.py's RMH density_regulated=false precedent).
-- ============================================================
UPDATE zoning_districts SET density_regulated=false WHERE id=11767; -- AR
UPDATE zoning_districts SET density_regulated=false WHERE id=11768; -- OUA

-- Real (non-density) OUA dimensional standards -- CONFIRMED from the same Sec 125-158
-- table row (20 acres min parcel, 300ft width, 50/35/35 setbacks, 45ft height, 10% coverage)
INSERT INTO zone_standards (zoning_district_id, min_lot_sqft, min_lot_width_ft, max_height_ft, front_setback_ft, rear_setback_ft, side_setback_ft, max_lot_coverage_pct, source_url, ordinance_section, effective_date, confidence_score) VALUES (11768, 871200, 300, 45, 50, 35, 35, 10, 'http://cms2.revize.com/revize/gladescounty/2020_Agendas/2020_Agendas/14_April_2020_Agenda/2.%20Revisions%20to%20Chapter%20125-%20Land%20Development%20Regulations,%20Section%20125-9.pdf', 'Glades County Code of Ordinances, Ch. 125, Art. IV, Sec. 125-158 (QUA/OUA row, Buildable Units/Acre cell confirmed blank via pdfplumber x-coordinate analysis)', '2020-04-14', 0.85);

COMMIT;

-- VERIFICATION (run after apply):
-- SELECT * FROM pencil_dod_evaluate_county('glades');
-- Expected: A/B/C/D/E/F/G/H/I all pass=true; I metric=98.0 (card_complete=100 of 102);
-- G metric=100.0; J unchanged FAIL 65.7% (residual, see notes above).
