-- GOLD STANDARD shard-1 (dispatch 5ba6ec26, loop run 6080), county=holmes
--
-- Fixes the I and J GHOST-SUCCESS defects confirmed live by two independent
-- ultraloop refuter passes (gold_standard_ultraloop_audit, 2026-07-20T19:33:41Z,
-- survived=false for both letters), even though pencil_dod_evaluate_county
-- already reports I=pass (card_complete=13/13) and J=pass (deal_complete=13/13):
--   I: market_value was the byte-identical placeholder 98000.0 across ALL 13
--      holmes rows, and the 3 foreclosure rows shared one identical
--      lat/lon (30.8663,-85.8183) despite being 3 distinct addresses in 2 towns.
--   J: all 10 tax_deed bid_decisions rows were byte-identical placeholders
--      (arv=85000.00, max_bid=34500.00, ml_score=0.6200,
--      factors.cma_distressed literally the string "opening_bid=0").
-- The DoD schema-presence gate (non-null check only) cannot catch either defect
-- -- both PASS at the evaluator level while being fabricated/templated data.
-- Per CRITERION-PARALLEL PIVOT ("RECONCILE all prior PASSes -- any regression =
-- P0") and the ULTRALOOP verify step ("a claim ships ONLY if it survives
-- refutation"), these are real, actionable defects even though no A-J letter
-- numerically moves from this fix.
--
-- SOURCE (real, independently verified this session): FL GIO Statewide
-- Cadastral FeatureServer (services9.arcgis.com/.../Florida_Statewide_Cadastral),
-- same canonical baseline source used by scripts/ingest_county.py for every
-- other county. Matched by PARCELNO = our stored parcel_id with '.' and '-'
-- stripped (exact match confirmed live for all 13 holmes parcels; this is NOT
-- the same field ingest_county.py reads (PARCEL_ID, largely blank in this
-- county), it's PARCELNO -- documented here since it cost real investigation
-- time to find). Cross-validated independently: FL GIO OWN_NAME for parcel
-- 1626.00-000-000-011.000 = "GILLIS AMBER & ERIC", which matches the existing
-- DB row's plaintiff caption "...V. AMBER LYNN GILLIS...ERIC KEITH GILLIS..."
-- captured from an entirely different source (holmesclerk.com) 5 weeks
-- earlier -- strong independent confirmation this is a correct parcel match,
-- not a coincidental string match.
-- JV = FL DOR "just value" (full market value) -> multi_county_auctions.market_value
-- AV_NSD = FL DOR assessed value, non-school-district -> .assessed_value
-- Centroid geometry (EPSG:3086 NAD83/Florida GDL Albers) reprojected to
-- WGS84 (EPSG:4326) via pyproj -- all 13 resulting lat/lon pairs are distinct
-- and fall within Holmes County, FL (lat 30.76-30.94, lon -85.66 to -85.91).
--
-- B/C/D/F: NOT touched by this migration. Reconfirmed genuinely blocked for a
-- 6th consecutive session (shard12/run3534, shard9/ddbb047c, shard6/run4870,
-- shard1/7abd0202 pass1+pass2, this session) -- holmesclerk.com remains a
-- forward-looking notice board with no disposition/results page, Firecrawl
-- remains at 0 credits (reconfirmed live this session), myfloridacounty.com
-- official records search remains CAPTCHA-gated, GovEase confirmed not used
-- by Holmes. See gold_standard_ultraloop_audit for the fresh survived=true
-- audit rows logged this session re-confirming the block (not re-litigated
-- here). No fabricated sold_amount / outcome rows written -- fail-loud per
-- campaign rules.

SET statement_timeout = 0;

BEGIN;

WITH flgio AS (
  SELECT * FROM (VALUES
    ('HOLMES-LEGACY-123a1bd5-1ea3-4bb4-98ad-a7fc86853e49', 347344::numeric, 281414::numeric, 30.905998::double precision, -85.900524::double precision, 2524::numeric, 'GILLIS AMBER & ERIC'),
    ('TD#2023-225',   5830,  5830, 30.939243, -85.699842, NULL, 'TRSTE LLC'),
    ('TD#2023-185',  16110, 15899, 30.766929, -85.669098, NULL, 'BOWEN BRANDON M & TARA L'),
    ('TD#2023-496',  13971, 11327, 30.843058, -85.840089,  546, 'MANCILL JAMES ERWIN & MELISSA'),
    ('TD#2023-584',   6562,  5082, 30.806809, -85.824066, NULL, 'WILLIAMS KENNETH ADAMS'),
    ('TD#2023-330',   9946,  7708, 30.857129, -85.742772, NULL, 'DERING JOHN S & EDNA TRUSTEES'),
    ('TD#2023-509',   8250,  8250, 30.843640, -85.854231, NULL, 'GRACE DEANDREA'),
    ('TD#2020-349',   5967,  4623, 30.861646, -85.743930, NULL, 'FLORIDA LIVING HOMESITES'),
    ('TD#2024-185',   2678,  2076, 30.790569, -85.674429, NULL, 'LEE ALFONTO PURVIS ESTATE'),
    ('TD#2020-589',   4750,  3678, 30.808647, -85.821804, NULL, 'SAFFORD RUPERT E, II'),
    ('TD#2023-753',   9425,  5474, 30.788572, -85.910128, NULL, 'WILLIAMS BRYAN E & LESLIE L'),
    ('HOLMES-LEGACY-3ca8afb6-fe6d-4c71-bf8a-51df49eebfc3', 105309, 93617, 30.801601, -85.684863, 1155, 'TODAR ILLYANNA MARIE'),
    ('HOLMES-LEGACY-14b20609-70d3-434b-b7a3-e8c45c3ca882', 167391, 124352, 30.794263, -85.658562, 2694, 'JOHNSON JEFFERY')
  ) AS t(case_number, jv, av_nsd, lat, lon, tot_lvg_ar, own_name)
)
UPDATE multi_county_auctions mca
SET
  market_value          = flgio.jv,
  assessed_value         = flgio.av_nsd,
  assessed_value_source  = 'fl_gio_cadastral_av_nsd',
  latitude               = flgio.lat,
  longitude              = flgio.lon,
  living_area_sqft        = COALESCE(flgio.tot_lvg_ar, mca.living_area_sqft),
  owner_name             = COALESCE(mca.owner_name, flgio.own_name)
FROM flgio
WHERE mca.county = 'holmes'
  AND mca.case_number = flgio.case_number;

-- J: refresh the 10 tax_deed bid_decisions rows (the confirmed-defective
-- subset) using the SAME Shapira v14.0 heuristic formula already shipped and
-- accepted fleet-wide (e.g. 20260710_gold_standard_shard11_hardee_j_bid_decision.sql,
-- 20260619_shard11_j_generator.sql), now driven by the real assessed_value
-- just written above instead of the flat 85000/34500 placeholder. The 3
-- foreclosure legacy rows are untouched -- already independently confirmed
-- genuinely varied/real by the 2026-07-20 refuter pass, out of this
-- migration's scope (K3 surgical-changes discipline).
UPDATE bid_decisions bd
SET
  arv              = ROUND(NULLIF(mca.assessed_value, 0) * 1.15, 2),
  arv_source        = 'assessed_value_x1.15',
  repairs           = 25000,
  repair_estimate    = 25000,
  -- NOT floored at 0: these are small vacant tax-deed lots (assessed
  -- $2K-$16K) where the flat $25K repair assumption genuinely pushes every
  -- one negative. Per the accepted 20260619_shard11_j_generator.sql
  -- precedent ("left as computed, not floored/fabricated to look viable"),
  -- a GREATEST(0,...) floor here would collapse all 10 distinct negative
  -- values back to an identical 0.00 -- reproducing the exact ghost-success
  -- pattern (identical value across every row) this migration exists to fix.
  max_bid           = ROUND(
                         NULLIF(mca.assessed_value, 0) * 1.15 * 0.70
                         - 25000
                         - 10000
                         - LEAST(25000, NULLIF(mca.assessed_value, 0) * 1.15 * 0.15)
                       , 2),
  ml_score          = 0.45,
  pipeline_version   = 'v14.0_heuristic',
  factors = jsonb_build_object(
    'distress_location', jsonb_build_object(
      'county', 'holmes', 'city', COALESCE(NULLIF(mca.city, ''), 'unknown'),
      'zip', mca.zip, 'state', 'FL', 'score', 0.50, 'honesty_marker', 'HYPOTHESIS'),
    'distress_property', jsonb_build_object(
      'property_type', COALESCE(mca.property_type, 'unknown'),
      'sqft', mca.living_area_sqft, 'assessed_value', mca.assessed_value,
      'parcel_id', mca.parcel_id,
      'score', CASE WHEN mca.assessed_value > 15000 THEN 0.55 ELSE 0.35 END,
      'honesty_marker', 'HYPOTHESIS'),
    'distress_owner', jsonb_build_object(
      'owner_name', mca.owner_name,
      'is_entity', (mca.owner_name ILIKE '%llc%' OR mca.owner_name ILIKE '%inc%' OR mca.owner_name ILIKE '%trustee%'),
      'is_estate', (mca.owner_name ILIKE '%estate%'),
      'is_lender', false, 'score', 0.50, 'honesty_marker', 'HYPOTHESIS'),
    'cma_distressed', jsonb_build_object(
      'estimated_value', mca.assessed_value, 'source', 'fl_gio_cadastral_av_nsd',
      'confidence', 'low', 'honesty_marker', 'HYPOTHESIS'),
    'cma_resale', jsonb_build_object(
      'arv', ROUND(NULLIF(mca.assessed_value, 0) * 1.15, 2),
      'max_bid', ROUND(
                    NULLIF(mca.assessed_value, 0) * 1.15 * 0.70
                    - 25000 - 10000
                    - LEAST(25000, NULLIF(mca.assessed_value, 0) * 1.15 * 0.15)
                  , 2),
      'formula', 'shapira_v14: (ARV*0.70) - repairs($25K) - friction($10K) - cushion(MIN $25K, ARV*15%)',
      'source', 'shapira_formula_v14_heuristic', 'honesty_marker', 'HYPOTHESIS')
  )
FROM multi_county_auctions mca
WHERE bd.case_number = mca.case_number
  AND mca.county = 'holmes'
  AND bd.case_number LIKE 'TD#%';

COMMIT;
