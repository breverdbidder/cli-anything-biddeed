-- Gold Standard shard-4 baker (dispatch 80db2753-d593-429f-bae8-e1c57b14bd41)
-- Case 022025CA000002CAAXMX: real parcel/geo/value research + J deal-decision.
--
-- Parcel VERIFIED via two independent live sources (cross-matching, session
-- 2026-08-10): bakerpa.com property card (owner HOLMES MICHAEL T JR/SANDRA J,
-- 13.21ac improved agriculture parcel) and Baker County ArcGIS FeatureServer
-- (parcels_web2/FeatureServer/0, PARCELNO match, same owner/site-address
-- attributes). Address already matched our existing scraped
-- property_address exactly (source: RealAuction case card).
-- Assessed Value-Non School $58,218 and Total Just Value $110,489 both read
-- directly off https://www.bakerpa.com/propertydetails.php?parcel=073S21000000000100.
-- Latitude/longitude: area-weighted centroid computed directly (this
-- migration's author, not an agent estimate) from the parcel polygon
-- returned by the ArcGIS FeatureServer query
-- (.../FeatureServer/0/query?where=PARCELNO='073S21000000000100'&f=geojson&outSR=4326).
--
-- Zoning linkage checked and NOT found: parcel 073S21000000000100 is absent
-- from parcel_zones / v_zoning_gold_standard_card for baker (verified live).
-- This is a genuine zoning-ingestion coverage gap for this specific parcel,
-- not something this migration fabricates a fix for -- letter I will NOT
-- count this row as card_complete until baker's zoning layer covers it.
--
-- J: Shapira Formula per CLAUDE.md, (ARV*70%)-Repairs-$10K-MIN($25K,15%*ARV),
-- applied to the VERIFIED Total Just Value ($110,489) as ARV -- same tiered-
-- repair/formula contract as every other county's J-generator scripts in
-- this repo (e.g. scripts/columbia_j_generator.py). All factor notes/scores
-- tagged honesty_marker=INFERRED per existing shapira_v14 convention (the
-- distress scores are model heuristics, not independently sourced facts).
--
-- NOT touched in this migration (left honestly unresolved, evidence in
-- session report): 022025CC000132CCAXMX (not present on any live Baker
-- RealAuction calendar area checked; no address obtainable without solving
-- Baker's Cloudflare Turnstile CAPTCHA on OCRS, out of scope) and
-- 022025CA000117CAAXMX / 022025CA000124CAAXMX (confirmed still live/scheduled
-- but genuinely missing parcel/address at the RealAuction source itself --
-- source-data gap, not a pipeline bug, per 6th independent session to reach
-- this conclusion).

BEGIN;

UPDATE public.multi_county_auctions
SET
  parcel_id = '073S21000000000100',
  city = 'Glen Saint Mary',
  zip = '32040',
  assessed_value = 58218,
  market_value = 110489,
  latitude = 30.243968,
  longitude = -82.249514,
  parity_status = 'matched_clean',
  parity_source = 'tier1_baker_realforeclose_bakerpa_v1:baker:20260810_cdeij_dispatch80db2753',
  parity_confidence = 0.95,
  parity_checked_at = now()
WHERE county = 'baker' AND case_number = '022025CA000002CAAXMX';

INSERT INTO public.bid_decisions
  (case_number, county_slug, parcel_id, address, auction_date, arv, repairs,
   final_judgment, max_bid, bid_judgment_ratio, recommendation, confidence,
   ml_score, factors, arv_source, pipeline_version)
SELECT
  '022025CA000002CAAXMX', 'baker', '073S21000000000100',
  '13446 ARNOLD RHODEN RD, GLEN SAINT MARY, FL- 32040', auction_date,
  110489.00, 25000.00, 330375.81, 25768.95,
  round(25768.95 / NULLIF(330375.81, 0), 4),
  'BID', 0.50, 0.75,
  jsonb_build_object(
    'model', 'shapira_v14',
    'distress_location', jsonb_build_object('score', 5.0, 'note', 'baker county FL', 'honesty_marker', 'INFERRED'),
    'distress_property', jsonb_build_object('score', 5.0, 'note', 'foreclosure distress', 'honesty_marker', 'INFERRED'),
    'distress_owner', jsonb_build_object('score', 7.0, 'note', 'judicial action filed', 'honesty_marker', 'INFERRED'),
    'cma_distressed', jsonb_build_object('value', round(110489.00 * 0.85, 2), 'note', 'distressed comp arm', 'honesty_marker', 'INFERRED'),
    'cma_resale', jsonb_build_object('value', 110489.00, 'note', 'retail resale arm -- Total Just Value, bakerpa.com', 'honesty_marker', 'INFERRED')
  ),
  'shapira_formula_baker_bakerpa_total_just_value_verified',
  'baker_j_gen_dispatch80db2753_v1'
FROM public.multi_county_auctions
WHERE county = 'baker' AND case_number = '022025CA000002CAAXMX'
ON CONFLICT DO NOTHING;

COMMIT;
