-- GOLD STANDARD SHARD-10 run-6288 — gilchrist — E+I parcel linkage
-- dispatch_id: 28bd9542-c34b-42af-97c6-7ad3e8205808
-- session: architect-20260725T000000
--
-- Context (VERIFIED from run-6148 migration + loop-6288 brief):
--   Prior session (run-6148, 2026-07-24) C/D-stamped all 14 gilchrist rows matched_clean
--   but disclosed that 6 foreclosure cases have NULL parcel_id (source platform limitation).
--
--   Current state entering session (loop run 6288):
--     E FAIL metric=57.1 [parcel_linked=8] (8 of 14 have parcel_id; 6 bare foreclosure stubs)
--     I FAIL metric=42.9 [card_complete=6 of 14]
--
--   For E to PASS (>=95%) we need >= ceil(0.95 * 14) = 14 of 14 rows linked.
--   (0.95 * 14 = 13.3 -> need 14; ceiling is 14/14 = 100%).
--   Actually threshold is >=95%: 13/14 = 92.9% (FAIL), 14/14 = 100% (PASS).
--   We must resolve all 6 to guarantee PASS.
--
-- The 6 bare-stub case numbers (confirmed from run-6148 migration / HONESTY DISCLOSURE):
--   212025CA000064CAAXMX  (auction_date 2026-09-14) [realforeclose.com]
--   212026CA000004CAAXMX  (auction_date 2026-09-14) [realforeclose.com]
--   212025CA000033CAAXMX  (auction_date 2026-09-28) [realforeclose.com]
--   212025CA000070CAAXMX  (auction_date 2026-09-28) [realforeclose.com]
--   212025CA000043CAAXMX  (auction_date 2026-10-12) [realforeclose.com]
--   212025CA000036CAAXMX  (auction_date 2026-10-26) [realforeclose.com]
--
-- Strategy for LIVE execution (scripts/gilchrist_run6288_e_i_parcel_linkage.py):
--   1. Query each foreclosure case on the FL 8th Circuit eFiling system (Gilchrist)
--      at myeclerk.myfloridacounty.com to get property address/defendant name.
--   2. Use Gilchrist PA ArcGIS (VERIFIED live 2026-07-19, gis1.hcpao.org) to match
--      address -> parcel_id, polygon centroid (lat/lon), assessed_value.
--   3. Backfill parcel_zones with R-1 zone (INFERRED from 8 sibling parcels, all R-1
--      in Gilchrist unincorporated + Trenton RSF-1; confidence_score=0.65 for INFERRED
--      pattern-match, as established in run-4870 and run-B88EB871).
--   4. Geocode via Census API for rows where PA ArcGIS does not return centroid.
--
-- All DB writes happen in the Python script via REST PATCH/POST.
-- This SQL file is the tracked record per migration rules.
--
-- HONESTY MARKERS:
--   VERIFIED: data confirmed from live source during this session
--   INFERRED: derived from sibling patterns/context
--   The actual parcel_id values depend on FL Courts response (UNTESTED until executed)

SET statement_timeout = 0;

-- Defensive guard: never keep a non-numeric parcel_id for gilchrist
UPDATE multi_county_auctions
SET parcel_id = NULL
WHERE county = 'gilchrist'
  AND parcel_id IS NOT NULL
  AND parcel_id !~ '^[0-9]';

-- ULTRALOOP audit intent rows (baseline; Python script upserts with actuals)
INSERT INTO gold_standard_ultraloop_audit (
    dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived
)
VALUES
(
    '28bd9542-c34b-42af-97c6-7ad3e8205808',
    'fallback',
    'gilchrist',
    'E',
    'run-6288 session: parcel_id lookup for 6 bare-stub gilchrist foreclosure cases via Gilchrist PA ArcGIS + FL 8th Circuit eFiling. Actual results written by script execution after session.',
    '{"tag":"UNTESTED","session_start":"2026-07-25T00:00:00Z","target_cases":6,"run":6288}',
    false
),
(
    '28bd9542-c34b-42af-97c6-7ad3e8205808',
    'fallback',
    'gilchrist',
    'I',
    'run-6288 session: property card completeness via parcel linkage + geocode + zone backfill. Actual results written by script execution after session.',
    '{"tag":"UNTESTED","session_start":"2026-07-25T00:00:00Z","run":6288}',
    false
)
ON CONFLICT DO NOTHING;

-- Verification queries (run after script execution):
-- SELECT public.pencil_dod_evaluate_county('gilchrist');
-- SELECT case_number, parcel_id, property_address, assessed_value, latitude, longitude
--   FROM multi_county_auctions WHERE county = 'gilchrist' ORDER BY auction_date;
-- SELECT county_slug, letter, survived, claim
--   FROM gold_standard_ultraloop_audit
--   WHERE county_slug = 'gilchrist' AND dispatch_id = '28bd9542-c34b-42af-97c6-7ad3e8205808'
--   ORDER BY letter;
