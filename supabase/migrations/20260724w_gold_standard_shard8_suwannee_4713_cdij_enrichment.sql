-- Gold Standard shard-8 follow-up: suwannee case 4713 (parcel 11943002000) enrichment.
--
-- Context: a fresh calendar-sweep (calendar_sweep_mca.py, data_source=calendar_sweep_mca_v3)
-- inserted a 14th suwannee row after the 2026-07-24 3rd-firing session had already exhaustively
-- confirmed suwannee at 8/10 (only B/F failing, structurally blocked on real-world auction
-- timing -- see .claude/session-logs/2026-07-24-gold-standard-shard8-suwannee-3rd.yml, DO NOT
-- re-investigate B/F). This new row (case_number='4713', sale_type='tax_deed',
-- parcel_id='11943002000', auction_date='2026-08-06', tier1_sale_status='REDEEMED',
-- tier1_authoritative=true, created_at='2026-07-24 05:59:04+00') was missing parity_status,
-- parity_source, data_source, latitude, longitude, assessed_value, market_value -- dropping
-- C/D/I/J from 100% (13/13) to 92.9% (13/14).
--
-- The other 7 rows in the same 2026-08-06 tax-deed batch (4706/4707/4709/4710/4711/4712/4784)
-- were already enriched by scripts/shard6_run3645_suwannee_cd_realtaxdeed_fix.py (parity via
-- live suwannee.realtaxdeed.com AJAX harvest, parcel_id-matched) and by the session documented
-- in scripts/gold_standard_shard11_suwannee_a_i_fix.py (real assessed/market value from the
-- Suwannee Property Appraiser's GSA-Corp-hosted system, suwannee-search.gsacorp.io; real
-- lat/lon from the free US Census Geocoder; zone_code from a DOR-use-code-to-district map
-- onto Suwannee's existing 4 generic zoning_districts, jurisdiction_id=895).
--
-- This migration re-ran that EXACT same pipeline for case 4713/parcel 11943002000, live,
-- this session (2026-07-24):
--
--   1. Live re-harvest of suwannee.realtaxdeed.com AJAX (08/06/2026, tax_deed platform) via
--      scripts/shard2_run2450_ajax_realforeclose_harvest.py:harvest_date() confirmed case 4713
--      IS present in the same official 8-row result set as the 7 siblings, with
--      parcel_id=11943002000 exact-matching our stored value, and a real property_address
--      "21981 160th St, Live Oak, FL". This is genuine parity evidence, not an assumption.
--
--   2. GSA Corp livesearch (suwannee-search.gsacorp.io/api/livesearch/21981%20160th%20St)
--      resolved to real parcel /parcel/0304S11E11943002000 (numeric tail 11943002000 matches
--      our parcel_id exactly). The parcel detail page returned real, current-year values:
--        Assessed Value = $50,944
--        Market Value   = $54,541
--        Use Code       = "0200: MOBILE HOME" (same use-code bucket as siblings 4706/5001030050/
--                          5001030120/6611340090, all mapped to zone_code=R1)
--
--   3. US Census Geocoder (geocoding.geo.census.gov) against "21981 160th St, Live Oak, FL"
--      returned a real, distinct match: lat=30.15855812964, lon=-83.205195727617,
--      zip=32060.
--
--   4. scripts/shard8_run6080_suwannee_j_generator_real.py (the real per-property XGBoost v14.0
--      inference generator for suwannee's bid_decisions) was re-run live after (2) unblocked
--      arv derivation from assessed_value. The v14.0 model artifacts (model.json, features.json)
--      were fetched live from Supabase Storage bucket shapira-models at the path recorded in
--      shapira_models (is_production=true, model_version='v14.0'), matching production exactly.
--      The generator is idempotent and auto-detected exactly 1 incomplete bid_decisions row
--      (case 4713) among suwannee's 14 auctions; it inserted one real row with arv=50944 (from
--      the real assessed_value fetched in step 2), a genuine per-row XGBoost ml_score=0.0742,
--      and all 5 required factor keys.
--
-- SQL actually executed live via the Supabase Management API (mgmt_sql pattern from
-- scripts/gold_standard_precert_guard_refresh.py; direct psql/pooler password auth confirmed
-- broken from this environment again this session, consistent with every prior session this
-- month):

-- Step A: multi_county_auctions enrichment (C/D/I)
UPDATE multi_county_auctions
SET
  property_address = '21981 160TH ST, LIVE OAK, FL 32060',
  latitude = 30.15855812964,
  longitude = -83.205195727617,
  assessed_value = 50944.00,
  market_value = 54541.00,
  data_source = 'calendar_sweep_mca_v3',
  parity_status = 'matched_clean',
  parity_source = 'tier1:shard6_run3645_suwannee_realtaxdeed_ajax:tax_deed:2026-08-06',
  updated_at = now()
WHERE county = 'suwannee' AND case_number = '4713';

-- Step B: parcel_zones row for I (same DOR-use-code-to-district mapping as the 7 sibling
-- parcels; use_code 0200 MOBILE HOME -> R1, jurisdiction_id=895 Live Oak/Suwannee County)
INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
VALUES (
  '11943002000', NULL, 895, 'R1', 'Single-Family Residential',
  'shard_gold_run3645_suwannee_zoning_real:2026-07-24:dor_usecode_to_district_map:0304S11E11943002000:use_code=0200: MOBILE HOME'
)
ON CONFLICT DO NOTHING;

-- Step C: bid_decisions row for J was inserted by re-running
-- scripts/shard8_run6080_suwannee_j_generator_real.py directly (not raw SQL -- it computes a
-- real per-row XGBoost inference). Resulting row, for reference/audit (values are the actual
-- live-computed output, not fabricated):
--   INSERT INTO bid_decisions (case_number, county_slug, parcel_id, arv, arv_source, repairs,
--     repair_estimate, max_bid, ml_score, factors, recommendation, confidence,
--     pipeline_version, created_at)
--   VALUES ('4713', 'suwannee', '11943002000', 50944.00,
--     'shapira_v14_real_multi_county_auctions.assessed_value', 4075.52, 4075.52, 20660.80,
--     0.0742,
--     '{"distress_location":0.6027,"distress_property":0.6143,"distress_owner":0.35,"cma_distressed":40755.2,"cma_resale":51962.88}'::jsonb,
--     'BID', 0.5, 'suwannee_j_generator_run6080_shapira_v14_real_v2', now());

-- ── VERIFICATION (live, this session) ──────────────────────────────────────────────────────
--
-- pencil_dod_evaluate_county('suwannee') BEFORE this fix (immediately prior, same session):
--   A PASS fc=4 td=10 | B FAIL null | C FAIL 92.9 (matched_clean=13) | D FAIL 92.9 (matched_any=13)
--   E PASS 100 | F FAIL null | G PASS 100 | H PASS 0 | I FAIL 92.9 (card_complete=13 of 14)
--   J FAIL 92.9 (deal_complete=13) | auctions_total=14
--
-- pencil_dod_evaluate_county('suwannee') AFTER this fix (live re-check, same session):
--   A PASS fc=4 td=10 | B FAIL null (unchanged, out of scope) | C PASS 100 (matched_clean=14)
--   D PASS 100 (matched_any=14) | E PASS 100 | F FAIL null (unchanged, out of scope) | G PASS 100
--   H PASS 0 | I PASS 100 (card_complete=14 of 14) | J PASS 100 (deal_complete=14)
--   auctions_total=14
--
-- Net: suwannee remains 8/10 (B, F still FAIL -- genuinely blocked on real-world auction
-- timing per the 3rd-firing session, correctly NOT touched by this fix), with C/D/I/J restored
-- from 92.9% back to 100% now that the 14th row (case 4713) carries the same real,
-- verifiable data as its 13 siblings. No fabricated values were written: every field above was
-- independently confirmed live against suwannee.realtaxdeed.com (parity), suwannee-search.gsacorp.io
-- (assessed/market value + use_code), and geocoding.geo.census.gov (lat/lon) this session.
--
-- NOTE: a gold_standard_ultraloop_audit row was NOT inserted for this fix -- that table's
-- dispatch_id is a real FK into summit_chat_dispatch, and this was an ad hoc (non-SUMMIT-
-- dispatched) follow-up session with no corresponding dispatch row. Fabricating a dispatch_id
-- to satisfy the FK would itself be a HONESTY PROTOCOL violation, so it was correctly skipped
-- rather than worked around. This migration file is the audit trail instead.
