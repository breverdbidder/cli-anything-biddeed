-- SHARD-9 (dispatch 30b3a3ea), county=hardee -- immediate follow-up to
-- 20260719_shard9_hardee_taxdeed_abf_wauchula_verified.sql in the SAME session.
--
-- That migration inserted 3 fully-verified tax-deed rows (A/B/F/C/D/E/I all moved to
-- PASS), but it grew auctions_total from 1 to 4 with no matching bid_decisions rows
-- for the 3 new cases -- pencil_dod_evaluate_county confirmed this REGRESSED J from
-- PASS (100%, 1/1) to FAIL (25%, 1/4). Per campaign rules, regressing a currently-
-- passing letter is P0 and must not be left standing. This migration generates
-- bid_decisions for the 3 new cases using the SAME Shapira V14 heuristic pipeline
-- (pipeline_version='v14.0_heuristic') already used for hardee's one existing J row
-- (case 25000327CAAXMX, see bid_decisions id=124425): ARV = assessed_value * 1.15,
-- max_bid = (ARV*0.70) - repairs($25K) - friction($10K) - MIN($25K, ARV*15%).
--
-- Inputs are the same FL GIO cadastral fields (assessed_value/sqft/year_built)
-- already written to multi_county_auctions by the companion migration; owner_name
-- uses the county GIS "Owner Parcels" cached name (the pre-transfer snapshot -- see
-- the companion migration's note on why this differs from FL GIO's current,
-- post-sale owner) as the best available proxy for the distressed/delinquent owner.
-- All factor sub-objects keep honesty_marker='HYPOTHESIS' (no ML model backs this,
-- same as the existing precedent row) -- this is a heuristic formula pipeline, not a
-- trained classifier; ml_score/confidence mirror the flat 0.45 placeholder the
-- existing hardee row already uses (v14.0_heuristic assigns no differentiated score).
--
-- 252024TD001AXMX is a vacant unimproved lot (JV=$4,950); the formula correctly
-- produces a NEGATIVE max_bid ($-31,869.13) -- the deal does not pencil at any
-- positive price. Left as computed (not floored/fabricated to look viable);
-- recommendation set to 'PASS' accordingly. The evaluator only requires max_bid IS
-- NOT NULL, not that it be positive.

SET statement_timeout = 0;

BEGIN;

INSERT INTO public.bid_decisions
  (case_number, parcel_id, address, auction_date, arv, repairs, max_bid,
   recommendation, confidence, ml_score, factors, county_slug, repair_estimate,
   pipeline_version, arv_source)
SELECT v.case_number, v.parcel_id, v.address, v.auction_date, v.arv, 25000, v.max_bid,
   v.recommendation, 0.45, 0.45,
   jsonb_build_object(
     'cma_resale', jsonb_build_object(
        'arv', v.arv, 'max_bid', v.max_bid,
        'source', 'shapira_formula_v14_heuristic',
        'formula', 'shapira_v14: (ARV*0.70) - repairs($25K) - friction($10K) - cushion(MIN $25K, ARV*15%)',
        'honesty_marker', 'HYPOTHESIS'),
     'cma_distressed', jsonb_build_object(
        'source', 'assessed_value', 'confidence', 'low',
        'estimated_value', v.assessed_value, 'honesty_marker', 'HYPOTHESIS'),
     'distress_owner', jsonb_build_object(
        'owner_name', v.owner_name, 'is_entity', v.is_entity, 'is_estate', v.is_estate,
        'is_lender', false, 'homestead', null, 'score', 0.5, 'honesty_marker', 'HYPOTHESIS'),
     'distress_location', jsonb_build_object(
        'county', 'hardee', 'city', 'wauchula', 'state', 'FL', 'zip', v.zip_code,
        'score', 0.5, 'honesty_marker', 'HYPOTHESIS'),
     'distress_property', jsonb_build_object(
        'parcel_id', v.parcel_id, 'assessed_value', v.assessed_value, 'sqft', v.sqft,
        'year_built', v.year_built, 'property_type', 'unknown', 'score', 0.65,
        'honesty_marker', 'HYPOTHESIS')
   ),
   'hardee', 25000, 'v14.0_heuristic', 'assessed_value_x1.15'
FROM (VALUES
  ('252024TD012AXMX', '0334250200000150002', '510 E PALMETTO ST, WAUCHULA, FL', DATE '2024-09-25',
   177044.80, 63931.36, 'BID', 'MALONE ETTA (EST OF)', false, true, '33873', 153952, 1040, 2009),
  ('252024TD001AXMX', '0434250000063000000', 'N 6TH AVE, WAUCHULA, FL', DATE '2024-05-29',
   5692.50, -31869.13, 'PASS', 'RIEDLINGER PROPERTIES INC', true, false, '33873', 4950, 0, 0),
  ('252023TD013AXMX', '0934250835000010046', '1078 DOWNING CIR, WAUCHULA, FL', DATE '2023-09-20',
   86489.20, 12569.06, 'BID', 'CATARINO TOBIAS FLORES', false, false, '33873', 75208, 1370, 1988)
) AS v(case_number, parcel_id, address, auction_date, arv, max_bid, recommendation,
       owner_name, is_entity, is_estate, zip_code, assessed_value, sqft, year_built)
WHERE NOT EXISTS (
  SELECT 1 FROM public.bid_decisions bd WHERE bd.case_number = v.case_number
);

COMMIT;
