-- Gold Standard shard-4 (dispatch 0bf31675): wakulla letter I (property card
-- completeness) backfill, run in the same workflow as the sibling wakulla-E
-- task (parcel_id=null probe on TXD-124/125/126/127).
--
-- BASELINE (verified live via pencil_dod_evaluate_county('wakulla') at
-- session start, immediately after the sibling wakulla-E task):
--   I: {"pass": false, "detail": "card_complete=41 of 52", "metric": 78.8}
--   auctions_total: 52.
--
-- See scripts/wakulla_shard4_0bf31675_i_card_completeness_backfill.py for the
-- full narrative (source verification, G-regression catch-and-fix, and the
-- ground-truth-doc correction on the 4 CA rows also needing zone_code).
--
-- SUMMARY:
--   4 rows (2026-TXD-124/125/126/127): GENUINE STRUCTURAL GAP, confirmed
--     fresh this session (WebFetch of wakullaclerk.org tax_deed_sales.php) --
--     "Redeemed" status, zero identifying data (no cert#, no address, no
--     PDF) published anywhere. Left UNRESOLVED, not fabricated.
--   4 rows (26-CA-19/31, 25-CA-9, 25-CA-145): assessed_value/market_value
--     backfilled from FL GIO Statewide Cadastral ArcGIS (JV field), matched
--     by spatial + exact-PARCEL_ID + address cross-check.
--   6 parcel_zones rows inserted (new zoning district lever found this
--     session: Wakulla County's official "Zoning_Master Pro" ArcGIS
--     FeatureServer, services9.arcgis.com/vAltLjtfYIJc7pDt/Zoning_Map/
--     FeatureServer/30 -- a full-extent, county-published zoning DISTRICT
--     boundary map, distinct from the older springshed-clipped "ZoningWakulla"
--     layer the 2026-08-28 session used, which correctly withheld 25-CA-105/
--     TXD-122 as parent-parcel-only hits). Point-in-polygon at each row's
--     exact stored lat/lon:
--       25-CA-105    (00-00-055-429-19932-034): PUD
--       2026-TXD-122 (30-2S-01W-000-04171-004): AG
--       2026-TXD-097 (23-5S-02W-128-02816-078): RSU1
--       26-CA-19     (00-00-073-335-10187-025): PUD
--       26-CA-31     (13-4S-02W-000-01923-000): RR1
--       25-CA-145    (06-3S-01W-243-04301-039): PUD
--   1 row (25-CA-9, 00-00-075-262-10242-B02): NO zoning hit -- exact point
--     falls in an unmapped seam between polygons (300m buffer query returns
--     8 distinct neighboring codes: RSU2/RR1/RR2/C2/AG/CO/C4). Left
--     UNRESOLVED, not fabricated -- genuinely can't determine which district
--     governs this exact point without guessing.
--
-- G-REGRESSION CAUGHT AND FIXED (same session): the 6 parcel_zones inserts
-- transiently broke G (95.0 PASS -> FAIL, far=0.0/pk1000=0.0) because RSU1
-- had no zoning_districts row for jurisdiction_id=1402 at all --
-- v_zoning_district_applicability treats a code with no match as
-- "default-applicable=true" (documented fleet-wide pattern, see
-- 20260724x_gold_standard_shard3_wakulla_g_regression_fix.sql for the
-- identical RR5/C2/PUD precedent on this same jurisdiction). Fixed by
-- inserting the missing RSU1 zoning_districts row (far_regulated=false,
-- pk1000_regulated=false, citing LDC Sec. 5-28 per the ArcGIS layer's own
-- Informatio field), matching the existing R1/RMH1/RR1/RSU2 sibling pattern.
--
-- RESULT (live, verified via pencil_dod_evaluate_county('wakulla')
-- immediately after all writes, including the G-regression fix):
--   I: {"pass": false, "detail": "card_complete=47 of 52", "metric": 90.4}
--     <- IMPROVED (78.8 -> 90.4, 41/52 -> 47/52), still FAIL (threshold
--     >=95%, needs >=50/52) -- structurally cannot pass this session per the
--     task's own math note (max reachable even with ALL 8 non-ceiling rows
--     fixed is 49/52=94.2%, still below 95%; this session additionally found
--     zoning coverage for the 4 CA rows the ground-truth doc had not
--     anticipated needing, landing at 47/52 instead of the expected ceiling).
--   No regression on A/B/C/D/E/F/G/H/J (G's transient regression caught and
--   fixed within this same session before final report; final state
--   byte-identical to pre-session baseline: A pass fc=12 td=40 | B pass
--   100.0 | C FAIL 78.8 (unchanged, out of scope) | D pass 100.0 | E FAIL
--   92.3 (unchanged, out of scope -- see sibling wakulla-E task) | F pass
--   100.0 | G pass 95.0 (far=/pk1000= blank, restored) | H pass 3.3h | J
--   FAIL 86.5 (unchanged, out of scope).

BEGIN;

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
VALUES
  ('00-00-055-429-19932-034', 1402, 'PUD',  'Planned Unit Development',              'Wakulla_County_Zoning_Master_Pro_ArcGIS_services9.arcgis.com/vAltLjtfYIJc7pDt/Zoning_Map/FeatureServer/30_wakulla_shard4_0bf31675_i'),
  ('30-2S-01W-000-04171-004', 1402, 'AG',   'AG Agricultural District',              'Wakulla_County_Zoning_Master_Pro_ArcGIS_services9.arcgis.com/vAltLjtfYIJc7pDt/Zoning_Map/FeatureServer/30_wakulla_shard4_0bf31675_i'),
  ('23-5S-02W-128-02816-078', 1402, 'RSU1', 'Semi-Urban Residential District',       'Wakulla_County_Zoning_Master_Pro_ArcGIS_services9.arcgis.com/vAltLjtfYIJc7pDt/Zoning_Map/FeatureServer/30_wakulla_shard4_0bf31675_i'),
  ('00-00-073-335-10187-025', 1402, 'PUD',  'Planned Unit Development',              'Wakulla_County_Zoning_Master_Pro_ArcGIS_services9.arcgis.com/vAltLjtfYIJc7pDt/Zoning_Map/FeatureServer/30_wakulla_shard4_0bf31675_i'),
  ('13-4S-02W-000-01923-000', 1402, 'RR1',  'Semi-Rural Residential District',       'Wakulla_County_Zoning_Master_Pro_ArcGIS_services9.arcgis.com/vAltLjtfYIJc7pDt/Zoning_Map/FeatureServer/30_wakulla_shard4_0bf31675_i'),
  ('06-3S-01W-243-04301-039', 1402, 'PUD',  'Planned Unit Development',              'Wakulla_County_Zoning_Master_Pro_ArcGIS_services9.arcgis.com/vAltLjtfYIJc7pDt/Zoning_Map/FeatureServer/30_wakulla_shard4_0bf31675_i')
ON CONFLICT DO NOTHING;

INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, ordinance_section, far_regulated, pk1000_regulated)
VALUES (
  1402, 'RSU1',
  'RSU1 Semi-Urban Residential District -- VERIFIED zone_code from Wakulla County official Zoning_Master_Pro ArcGIS layer (services9.arcgis.com/vAltLjtfYIJc7pDt/Zoning_Map/FeatureServer/30, CUR_ZONING field, Informatio field cites Wakulla LDC Sec. 5-28), same documentation-gap class as this jurisdiction''s existing R1/RMH1/RR1/RSU2 rows (dimensional standards not sourced this session)',
  'residential', 'Sec. 5-28', false, false
)
ON CONFLICT DO NOTHING;

COMMIT;

-- assessed_value/market_value PATCHes for 26-CA-19 (250045), 26-CA-31
-- (151262), 25-CA-9 (152344), 25-CA-145 (277716) were made directly via
-- PostgREST PATCH against multi_county_auctions (not expressible as a single
-- idempotent INSERT here since these are updates to existing rows) -- see
-- scripts/wakulla_shard4_0bf31675_i_card_completeness_backfill.py
-- patch_assessed_values() for the exact, re-runnable PATCH calls.
