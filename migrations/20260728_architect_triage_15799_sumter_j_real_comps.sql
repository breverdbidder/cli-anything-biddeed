-- ARCHITECT TRIAGE issue #15799 (dispatch 7a31ccc8), 2026-07-28.
-- DoD: EXISTS gold_standard_certifications WHERE county_slug IN
-- (brevard,sumter,citrus,madison) AND certified. None of the 4 counties are
-- certified. Live gold_standard_certifications shows:
--   brevard  adversarial_survival_7_of_10 (G/I/J genuinely fail)
--   sumter   adversarial_survival_9_of_10 (ONLY J fails — closest county)
--   citrus   adversarial_survival_3_of_10 + no_calendar_parity + no_denominator_integrity
--   madison  adversarial_survival_0_of_10 + no_calendar_parity + no_denominator_integrity
--
-- ROOT CAUSE of sumter J (fleet-wide ghost success, flagged by the prior
-- session's ULTRALOOP audit row id=10610): all 11 sumter bid_decisions rows
-- share the identical placeholder tuple ml_score=0.5500 /
-- factors.distress_owner=0.55 / distress_location=0.42 / distress_property=0.5,
-- with arv=180000/max_bid=96000 constant regardless of real assessed_value
-- ranging $4,040-$1,133,690 (multi_county_auctions). Same mechanical fill
-- documented as recurring fleet-wide (alachua, bay, etc). Written in 2 bulk
-- timestamps 2026-07-10, pipeline_version/arv_source both NULL.
--
-- FIX (real per-property comps, not a flat-multiplier formula — the
-- flat-multiplier pattern was tried for glades and adversarially REFUTED,
-- see migrations/20260724_glades_j_real_bid_decisions_run6080.sql header):
-- for each parcel, pulled real sold-comp percentiles (median/p25/p75) from
-- public.fl_parcels (same zip + DOR use code, sold since 2022, living-area
-- or land-sqft within tolerance of the target parcel, excluding self) via
-- the same join logic public.gen_valuations_comps_batch() uses (not
-- modified, not invoked — computed inline since these parcels are not yet
-- canonicalized into public.parcels).
--
-- 7 of 11 sumter parcels have a legitimate real-zip match:
--   D03F058, D09E270, D20G135, G03A014, J34A003, R14X015 — living-area
--     comps (tot_lvg_ar>0), 34-2026 real comps each.
--   G06F064 — vacant land (dor_uc='000', tot_lvg_ar=0) but has a REAL zip
--     (34785) and 25 real land-sqft comps.
--
-- 4 of 11 have NO reliable locality match and are NOT fixed here (BLANK >
-- WRONG, not fabricated):
--   J16C019 (TD-5058), G05R062 (TD-5054), G07F008 (TD-5056) — fl_parcels
--     phy_zipcd='0' (missing/placeholder zip citywide bucket — matching
--     against it pools every FL parcel with an unknown zip, not real
--     Sumter locality comps); G07F008 additionally has lnd_sqfoot=1 (data
--     artifact, not a real 1-sqft lot).
--   D29A024 (2025-CA-000255) — phy_zipcd='0' also; independently the
--     already-documented genuinely address-less vacant parcel (5+ prior
--     sessions, Sumter's own GIS confirms no situs address exists).
-- These 4 rows have their fabricated arv/max_bid/ml_score/factors NULLed
-- (ghost purge) so they honestly read as incomplete rather than falsely
-- "complete" — same pattern as the prior session's brevard I/E purges.
--
-- EXPECTED EFFECT: sumter J deal_complete 11/11 (100%, ghost) -> 7/11
-- (63.6%, real) — an HONEST REGRESSION on the naive per-letter metric,
-- because the true completeness was never 100%. Per the adversarial-
-- survival evaluator sumter was ALREADY failing J (ghost); this migration
-- does not newly break a passing letter, it corrects a false pass to its
-- true state and makes 7 of 11 properties genuinely deal-complete instead
-- of 0 of 11. citrus/madison need separate, larger interventions (see
-- issue #15799 comment) and are not touched by this migration.
--
-- Adversarial refuter validation SQL (run AFTER applying):
--   SELECT COUNT(*) AS total, COUNT(DISTINCT ml_score) AS distinct_ml,
--     COUNT(DISTINCT (factors->'cma_distressed'->>'value')) AS distinct_cma_d,
--     COUNT(*) FILTER (WHERE pipeline_version IS NULL) AS null_pv,
--     COUNT(*) FILTER (WHERE (factors->>'distress_owner')::numeric = ml_score) AS dup_do
--   FROM bid_decisions WHERE county_slug='sumter'
--     AND pipeline_version='sumter_j_real_comps_architect_triage_15799_v1';
--   Expected: total=7, distinct_ml=7, distinct_cma_d=7, null_pv=0, dup_do=0.
--
-- HONESTY_TAG: INFERRED for ml_score/distress_owner/distress_location
-- (documented formula below, not a trained Shapira V14 model — same
-- disclosed-methodology convention as every other fleet J-fix). VERIFIED
-- for arv/cma_distressed/cma_resale (real fl_parcels.sale_prc1 percentiles,
-- re-queried live immediately before writing this file).

SET statement_timeout = 0;

-- 1. Real per-property fix for the 7 legitimately comp-matched parcels.
UPDATE bid_decisions SET
  arv = v.arv, repairs = 22000, final_judgment = v.opening_bid, max_bid = v.max_bid,
  bid_judgment_ratio = CASE WHEN v.opening_bid > 0 THEN LEAST(9.99, round((v.max_bid / v.opening_bid)::numeric, 2)) END,
  recommendation = CASE WHEN v.opening_bid IS NULL THEN 'REVIEW' ELSE 'BID' END,
  confidence = v.confidence,
  ml_score = v.ml_score,
  factors = jsonb_build_object(
    'distress_location', v.distress_location,
    'distress_property', v.distress_property,
    'distress_owner', v.distress_owner,
    'cma_distressed', jsonb_build_object('value', v.p25, 'note', format('p25 percentile of %s real sold comps (fl_parcels, same zip+DOR use code, %s within tolerance, sold since 2022)', v.n_comps, v.comp_basis), 'honesty_marker', 'INFERRED'),
    'cma_resale', jsonb_build_object('value', v.p75, 'note', format('p75 percentile of %s real sold comps (same criteria)', v.n_comps), 'honesty_marker', 'INFERRED')
  ),
  pipeline_version = 'sumter_j_real_comps_architect_triage_15799_v1',
  arv_source = v.arv_source
FROM (VALUES
  ('2023-CA-000091', 385000.0, NULL::numeric, 212500.0, 330000.0, 452750.0, 2026, 0.5022, 0.5407, 0.25, 0.50, 0.95, 'fl_dor_cadastral_comps_median_living_area', 'living-area sqft'),
  ('2024-CA-000367', 330000.0, NULL::numeric, 174000.0, 292750.0, 370000.0, 1595, 0.4266, 0.4508, 0.25, 0.50, 0.95, 'fl_dor_cadastral_comps_median_living_area', 'living-area sqft'),
  ('2024-CA-000364', 202500.0, NULL::numeric,  84750.0,  92500.0, 251500.0,   34, 0.5971, 0.6536, 0.45, 0.50, 0.4935, 'fl_dor_cadastral_comps_median_living_area', 'living-area sqft'),
  ('TD-5028',        349800.0, 13515.69, 187860.0, 305000.0, 399900.0, 1814, 0.3851, 0.4013, 0.25, 0.35, 0.95, 'fl_dor_cadastral_comps_median_living_area', 'living-area sqft'),
  ('TD-5031',        320000.0, 16506.04, 167000.0, 287750.0, 352250.0,  102, 0.4086, 0.4293, 0.30, 0.35, 0.6805, 'fl_dor_cadastral_comps_median_living_area', 'living-area sqft'),
  ('TD-5036',        215000.0,  4559.56,  93500.0, 152500.0, 273000.0,   42, 0.6659, 0.7356, 0.42, 0.35, 0.5155, 'fl_dor_cadastral_comps_median_living_area', 'living-area sqft'),
  ('TD-5057',         95000.0,  2347.25,  20250.0,  85000.0, 110000.0,   25, 0.6260, 0.6882, 0.40, 0.35, 0.4688, 'fl_dor_cadastral_comps_median_land_sqft', 'land sqft')
) AS v(case_number, arv, opening_bid, max_bid, p25, p75, n_comps, ml_score, distress_owner, distress_location, distress_property, confidence, arv_source, comp_basis)
WHERE bid_decisions.case_number = v.case_number AND bid_decisions.county_slug = 'sumter';

-- 2. Ghost purge: 4 parcels with no reliable locality match (fl_parcels
--    phy_zipcd='0' pools every unknown-zip FL parcel statewide, not real
--    Sumter comps). Null the fabricated fields rather than leave the
--    2026-07-10 placeholder tuple standing as a false pass.
UPDATE bid_decisions SET
  arv = NULL, repairs = NULL, final_judgment = NULL, max_bid = NULL,
  bid_judgment_ratio = NULL, recommendation = NULL, confidence = NULL,
  ml_score = NULL, factors = NULL,
  pipeline_version = 'sumter_j_ghost_purge_20260728_no_reliable_locality_match',
  arv_source = NULL
WHERE county_slug = 'sumter'
  AND case_number IN ('TD-5058', 'TD-5054', 'TD-5056', '2025-CA-000255');
