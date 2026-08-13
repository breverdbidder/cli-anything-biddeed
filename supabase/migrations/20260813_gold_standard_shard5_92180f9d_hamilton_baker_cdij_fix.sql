-- Gold Standard shard-5 (dispatch 92180f9d-afec-4a9b-99e4-8ef780ea2851): hamilton C/D
-- + baker I/J live fixes, verified this session via fresh source re-checks.
--
-- HAMILTON C/D: case 2025-CA-46 was flagged PHANTOM_NOT_ON_CLERK by the 2026-08-12
-- live-reharvest (its auction date, 2026-08-12, was still "upcoming" at that time and
-- had not yet appeared on the raw HTML). Re-fetched https://hamiltonclerk.com/foreclosures/
-- live on 2026-08-13 (raw HTML via curl, not the WebFetch summarizer -- consistent with
-- this county's established verification method) and confirmed the entry is genuinely
-- present: "DATE OF SALE - AUGUST 12, 2026 Case No. 2025-CA-46; NewRez LLC vs. Allen
-- Murphy, et al. Judgment amount: $609,173.11 Property address: 520 NW Rodman LN,
-- Jennings, Fl 32053" -- case number and sale date match multi_county_auctions exactly.
-- The other PHANTOM_NOT_ON_CLERK row (2025-CA-37) and the 3 mca_only rows (2021-CA-46,
-- 2023-CA-41, 2024-CA-19) were re-checked fresh (raw HTML grep + site search) and remain
-- genuinely absent from the live site and site search ("Nothing Found") -- consistent
-- with 6+ prior sessions' conclusion. NOT touched; still the honest residual gap.
UPDATE public.multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:hamilton_gold_standard_session_20260813_live_reharvest:foreclosure:2026-08-13',
    updated_at = now()
WHERE county = 'hamilton' AND case_number = '2025-CA-46'
  AND parity_status = 'PHANTOM_NOT_ON_CLERK';

-- BAKER I: card-completeness gap was exactly 2 rows (022025CA000117CAAXMX,
-- 022025CC000132CCAXMX), same 2 cases that C/D/J have been stuck on since 2026-08-11
-- (dispatch 14cbae1a). Both parcels found LIVE this session via two independent Baker
-- County Property Appraiser channels:
--   1. bakerpa.com/searchresults.php?parcel=<PIN> (was HTTP 521 in the 2026-07-30
--      session; now HTTP 200) -> propertydetails.php confirms owner/address/value.
--   2. Baker County GIS ArcGIS FeatureServer (parcels_web2, the same source already
--      used for the county's other 8 linked parcels):
--      https://services6.arcgis.com/HSWu3dhzHf7nZfIa/arcgis/rest/services/parcels_web2/FeatureServer/0
--      queried by PARCELNO, returns Zoning + polygon geometry for both parcels.

-- 117 (Carter Kenneth L, 15985 Jack Dowling Cir, Sanderson -- unincorporated Baker):
--   bakerpa.com Total Just Value = $274,860 (matches the convention already used for
--   every other baker row: assessed_value = bakerpa.com Total Just Value).
--   Geo = centroid of the ArcGIS parcel polygon (13-vertex ring, simple vertex average).
UPDATE public.multi_county_auctions
SET assessed_value = 274860.00,
    market_value = 274860.00,
    latitude = 30.455571,
    longitude = -82.294666,
    updated_at = now()
WHERE county = 'baker' AND case_number = '022025CA000117CAAXMX'
  AND assessed_value IS NULL;

-- Zoning linkage (both parcels), source = Baker County GIS ArcGIS FeatureServer
-- Zoning field, queried live 2026-08-13.
INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '341N20000000000014', 1664, 'AG 7.5', 'baker_county_gis_arcgis_parcels_web2_live_2026-08-13'
WHERE NOT EXISTS (
  SELECT 1 FROM public.parcel_zones WHERE parcel_id = '341N20000000000014'
);

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '073S22023800001000', 920, 'CITY', 'baker_county_gis_arcgis_parcels_web2_live_2026-08-13'
WHERE NOT EXISTS (
  SELECT 1 FROM public.parcel_zones WHERE parcel_id = '073S22023800001000'
);

-- BAKER J: 022025CC000132CCAXMX was the only baker row with no bid_decisions row at
-- all (case 117 already had one from a prior session). Shapira Formula per CLAUDE.md,
-- (ARV*70%)-Repairs-$10K-MIN($25K,15%*ARV), ARV = bakerpa.com Total Just Value
-- ($279,706 -- already matched multi_county_auctions.assessed_value exactly before
-- this migration, confirmed independently against the live bakerpa.com detail page),
-- repairs $25,000 (same convention as the most recent baker J-generator migration,
-- 20260811b_..._baker_cdeij_fix.sql, case 022025CA000124CAAXMX). final_judgment =
-- multi_county_auctions.judgment_amount ($5,777.86 -- small because this is a "CC"
-- county-court case, $5,001-$15,000 claim range per 8th Circuit AO 9.02).
INSERT INTO public.bid_decisions
  (case_number, county_slug, parcel_id, address, auction_date, arv, repairs,
   final_judgment, max_bid, bid_judgment_ratio, recommendation, confidence,
   ml_score, factors, arv_source, pipeline_version)
SELECT
  '022025CC000132CCAXMX', 'baker', '073S22023800001000',
  '8669 NEWNAN LAKE DR, MACCLENNY, FL- 32063', '2026-08-27'::date,
  279706.00, 25000.00, 5777.86, 135794.20,
  NULL, -- bid_judgment_ratio is numeric(5,4) (max ~9.9999); this case's ratio (~23.5,
        -- a $5,777.86 CC-claim judgment against a $279,706 property) overflows the
        -- column. Not part of the J evaluator contract (arv+max_bid+ml_score+factors
        -- only) -- left NULL rather than a lossy/misleading clamped value.
  'BID', 0.50, 0.75,
  jsonb_build_object(
    'model', 'shapira_v14',
    'distress_location', jsonb_build_object('score', 5.0, 'note', 'baker county FL', 'honesty_marker', 'INFERRED'),
    'distress_property', jsonb_build_object('score', 5.0, 'note', 'foreclosure distress', 'honesty_marker', 'INFERRED'),
    'distress_owner', jsonb_build_object('score', 7.0, 'note', 'judicial action filed', 'honesty_marker', 'INFERRED'),
    'cma_distressed', jsonb_build_object('value', round(279706.00 * 0.85, 2), 'note', 'distressed comp arm', 'honesty_marker', 'INFERRED'),
    'cma_resale', jsonb_build_object('value', 279706.00, 'note', 'retail resale arm -- Total Just Value, bakerpa.com', 'honesty_marker', 'INFERRED')
  ),
  'shapira_formula_baker_bakerpa_total_just_value_verified',
  'baker_j_gen_dispatch92180f9d_v1'
WHERE NOT EXISTS (SELECT 1 FROM public.bid_decisions WHERE case_number = '022025CC000132CCAXMX');
