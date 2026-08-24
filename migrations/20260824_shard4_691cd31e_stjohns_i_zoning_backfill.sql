-- SHARD-4 (dispatch 691cd31e) — st_johns: real zoning backfill for the
-- 21-row I (card_complete) gap.
--
-- STATE AT SESSION START (fresh RPC, 2026-08-24):
--   pencil_dod_evaluate_county('st_johns') -> I FAIL, card_complete=87 of 108
--   (80.6%, need >=95% i.e. >=103/108). All other letters A-H,J PASS.
--
-- ROOT CAUSE (re-diagnosed fresh this session, NOT a repeat of the
-- 2026-08-09 shard4/7d59c973 "view returns 0 rows" claim — that claim does
-- NOT reproduce: `v_zoning_gold_standard_card` correctly returns 84 rows for
-- county='st_johns' when queried with the evaluator's own normalized join
-- `lower(county) = norm_county_key('st_johns')` = 'st johns'. The 0-rows
-- finding in that prior report was from a raw `county='st_johns'` query that
-- never normalizes the underscore, which is a different bug in that
-- session's own diagnostic query, not in the view or the evaluator).
--
-- The REAL root cause, confirmed live: the 21 blocking rows in
-- multi_county_auctions all have complete property_address, lat/long
-- (real, non-null on every row) and assessed_value -- the ONLY missing
-- ingredient is a matching parcel_zones row with zone_code NOT NULL for
-- their parcel_id. These 21 parcel_ids do not exist AT ALL in parcel_zones
-- (checked directly, zero rows), i.e. the two source jurisdictions with
-- zoning coverage (881 = St. Augustine city, 84 parcels total: 30 in 881 +
-- 54 in 1364) simply never had these particular STRAPs scraped. Most (19 of
-- 21) are TD26-xxxx tax-deed cases -- a batch of parcels that entered
-- multi_county_auctions after the last zoning-coverage sweep for st_johns.
--
-- FIX: queried St. Johns County's own authoritative GIS REST services
-- (public, no auth) for each of the 21 blocked parcels:
--   1. Parcel/MapServer/0 (https://www.gis.sjcfl.us/portal_sjcgis/rest/
--      services/Parcel/MapServer/0) queried by STRAP -> real parcel polygon
--      geometry (all multipart features per STRAP, several parcels have
--      2-6 separate ring features under one STRAP).
--   2. Zoning/MapServer/0 (same host) queried with the FULL parcel polygon
--      geometry (not a single averaged-vertex centroid, which was checked
--      and found unreliable for concave/ROW-strip parcels -- one 32-vertex
--      parcel's naive vertex-average centroid fell OUTSIDE its own ring) via
--      esriSpatialRelIntersects, to find every zoning polygon the parcel
--      touches.
--   3. For parcels intersecting a single zoning polygon: used that code
--      directly (16 of 21).
--   4. For parcels intersecting >1 zoning polygon: computed an area-overlap
--      fraction (20x20 grid sample of the parcel's largest ring against
--      each candidate zoning polygon) to find which zone covers the clear
--      majority of the parcel. This cleanly resolved 2 more parcels where
--      one zone covered ~100% and the other ~0% (a boundary-adjacent sliver
--      touch, not real straddling): 0041750020 -> RS-2, 2447000040 -> PUD,
--      0096200020 -> PUD (multi-feature STRAP, majority zone).
--   5. 3 parcels (0439900000/TD26-0096, 0436700000/TD26-0098,
--      0435900000/TD26-0105 -- all small Hastings-area lots) came back with
--      TWO zoning polygons (OR and RS-3) each covering ~100% of the parcel
--      per the area-overlap test, i.e. the county's own source GIS zoning
--      layer has two overlapping/coincident polygons over these specific
--      small lots. This is a genuine ambiguity in the source data itself,
--      not a resolvable case. Per HARD GUARDRAIL 3 (never fabricate a value
--      to force a pass), these 3 are LEFT UNFIXED. BLANK > WRONG.
--
-- JURISDICTION ASSIGNMENT: all 18 resolved codes (RS-3, RS-2, PUD, RG-2, SA,
-- OR) belong to the unincorporated-county Land Development Code vocabulary
-- that already backs jurisdiction_id=1364 (Unincorporated St. Johns County)
-- -- confirmed by cross-referencing existing zoning_districts rows for 1364
-- (OR, PUD, R-1-C, RG-1, RMH(S), RS-1, RS-3, SA, SAB already present) vs.
-- jurisdiction_id=881 (St. Augustine city), which has ONLY "R-1" as its
-- entire code vocabulary across all 30 existing parcel_zones rows. None of
-- the 18 resolved codes match St. Augustine's R-1-only scheme, so all 18 are
-- inserted under jurisdiction_id=1364. (No county GIS layer publishes
-- municipal boundaries as a queryable service to confirm incorporation
-- status directly -- this is the best available evidence and is flagged
-- HYPOTHESIS-supported-by-vocabulary-match, not blind guessing: source zone
-- codes returned by the county's own live Zoning GIS service, not invented.)
--
-- Two of the 18 resolved codes (RG-2, RS-2) do not yet have a
-- zoning_districts row for jurisdiction 1364 -- added below for G-metric /
-- FAR-density join integrity (not required for the I metric itself, since
-- v_zoning_gold_standard_card.zone_code comes from parcel_zones directly and
-- the zoning_districts join is a LEFT JOIN, but leaving them absent would
-- silently break any future join relying on district-level standards).
--
-- EXPECTED RESULT: card_complete 87 -> 105 of 108 (97.2%), I: FAIL -> PASS.
-- (105 = 87 + 18; the 3 ambiguous rows remain incomplete.)
--
-- Applied live via Supabase Management API (SUPABASE_ACCESS_TOKEN) and
-- PostgREST, 2026-08-24. This file documents what was executed.

-- 1. Add the two missing zoning_districts rows (real LDC codes, sourced from
--    the same live GIS Zoning layer + county LDC naming convention already
--    used for sibling codes RS-1/RS-3/RG-1 in this jurisdiction).
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, ordinance_section)
VALUES
  (1364, 'RS-2', 'Residential, Single Family', 'Residential', 'LDC Article II Sec 2.01.02.B (GIS zoning code, sibling of RS-1/RS-3)'),
  (1364, 'RG-2', 'Residential, General', 'Residential', 'LDC Article II Sec 2.01.02.B (GIS zoning code, sibling of RG-1)')
ON CONFLICT DO NOTHING;

-- 2. Insert real zone_code rows for the 18 confidently-resolved parcels,
--    sourced live from gis.sjcfl.us Parcel + Zoning MapServer (STRAP ->
--    full parcel geometry -> zoning-polygon intersect/area-majority).
INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, source, effective_date)
VALUES
  ('0349400000', 1364, 'RS-3', 'sjcfl_gis_zoning_mapserver_live_lookup:shard4_691cd31e_20260824', '2026-08-24'),
  ('0100160510', 1364, 'PUD',  'sjcfl_gis_zoning_mapserver_live_lookup:shard4_691cd31e_20260824', '2026-08-24'),
  ('0618080011', 1364, 'PUD',  'sjcfl_gis_zoning_mapserver_live_lookup:shard4_691cd31e_20260824', '2026-08-24'),
  ('0962311340', 1364, 'RS-3', 'sjcfl_gis_zoning_mapserver_live_lookup:shard4_691cd31e_20260824', '2026-08-24'),
  ('1168500000', 1364, 'RS-3', 'sjcfl_gis_zoning_mapserver_live_lookup:shard4_691cd31e_20260824', '2026-08-24'),
  ('2447900000', 1364, 'RS-3', 'sjcfl_gis_zoning_mapserver_live_lookup:shard4_691cd31e_20260824', '2026-08-24'),
  ('0412400050', 1364, 'RG-2', 'sjcfl_gis_zoning_mapserver_live_lookup:shard4_691cd31e_20260824', '2026-08-24'),
  ('0416600000', 1364, 'RS-3', 'sjcfl_gis_zoning_mapserver_live_lookup:shard4_691cd31e_20260824', '2026-08-24'),
  ('0467300000', 1364, 'RS-3', 'sjcfl_gis_zoning_mapserver_live_lookup:shard4_691cd31e_20260824', '2026-08-24'),
  ('1028200001', 1364, 'SA',   'sjcfl_gis_zoning_mapserver_live_lookup:shard4_691cd31e_20260824', '2026-08-24'),
  ('2222400000', 1364, 'SA',   'sjcfl_gis_zoning_mapserver_live_lookup:shard4_691cd31e_20260824', '2026-08-24'),
  ('1848340165', 1364, 'RS-2', 'sjcfl_gis_zoning_mapserver_live_lookup:shard4_691cd31e_20260824', '2026-08-24'),
  ('2447900001', 1364, 'RS-3', 'sjcfl_gis_zoning_mapserver_live_lookup:shard4_691cd31e_20260824', '2026-08-24'),
  ('1104600000', 1364, 'SA',   'sjcfl_gis_zoning_mapserver_live_lookup:shard4_691cd31e_20260824', '2026-08-24'),
  ('0386950000', 1364, 'OR',   'sjcfl_gis_zoning_mapserver_live_lookup:shard4_691cd31e_20260824', '2026-08-24'),
  ('0041750020', 1364, 'RS-2', 'sjcfl_gis_zoning_mapserver_live_lookup:shard4_691cd31e_20260824_area_majority', '2026-08-24'),
  ('2447000040', 1364, 'PUD',  'sjcfl_gis_zoning_mapserver_live_lookup:shard4_691cd31e_20260824_area_majority', '2026-08-24'),
  ('0096200020', 1364, 'PUD',  'sjcfl_gis_zoning_mapserver_live_lookup:shard4_691cd31e_20260824_area_majority', '2026-08-24')
ON CONFLICT DO NOTHING;

-- 3. NOT fixed, documented for the next session (or a future non-HTTP
--    unblocking tool): case CA25-1600 remains unfixed (wait, corrected --
--    CA25-1600's parcel 0041750020 WAS resolved above via area-majority).
--    The genuinely unresolved 3 (source GIS has two coincident zoning
--    polygons over the same small lot, ~100%/~100% area overlap each):
--      TD26-0096 parcel_id=0439900000  (OR vs RS-3, both ~100% overlap)
--      TD26-0098 parcel_id=0436700000  (OR vs RS-3, both ~100% overlap)
--      TD26-0105 parcel_id=0435900000  (OR vs RS-3, both ~100% overlap)
--    No insert performed for these three -- left as genuine structural gap.
--
-- 4. SELF-CAUGHT REGRESSION (fixed before session end, never left broken):
--    step 1 above added new zoning_districts rows for RS-2/RG-2 with
--    density_regulated left NULL. v_zoning_district_applicability defaults
--    density_applicable=true when density_regulated IS NULL and category is
--    not commercial/industrial, so RS-2/RG-2 immediately counted as
--    "density-applicable" parcels requiring a non-null max_density_du_acre
--    -- which step 1 had left NULL. This dropped G (density KPI) from
--    100.0% to 94.1% (FAIL) as an unintended side effect, caught by a fresh
--    pencil_dod_evaluate_county('st_johns') re-run before claiming done.
--    FIX: pulled the real LDC Table 6.01 (Article VI) minimum-lot-area
--    figures for RS-2 (10,000 sqft) and RG-2 SF Dwellings (7,500 sqft,
--    same as RG-1's real DB-stored value) directly from
--    https://www.sjcfl.us/wp-content/uploads/2024/01/article-vi.pdf, and
--    computed max_density_du_acre using the exact same 43,560/min_lot_sqft
--    formula already used by this county's real (non-INFERRED) OR/RS-1/RG-1
--    zone_standards rows -- verified the formula reproduces all 3 existing
--    real values exactly (RS-1: 43560/13200=3.30 matches DB; RG-1:
--    43560/7500=5.81 matches DB; OR: 43560/43560=1.00 matches DB) before
--    trusting it for the two new codes. Result: RS-2=4.36 DU/acre,
--    RG-2=5.81 DU/acre (both real, sourced, not fabricated). Set
--    density_regulated=true explicitly on both districts and inserted
--    zone_standards rows with these values plus the other real Table 6.01
--    fields (lot width, coverage %, setbacks, height) for the same two
--    codes. G restored to density=100.0% / PASS after this fix, confirmed
--    via a second fresh evaluator re-run.

UPDATE public.zoning_districts
SET density_regulated = true
WHERE jurisdiction_id = 1364 AND code IN ('RS-2', 'RG-2');

INSERT INTO public.zone_standards
  (zoning_district_id, min_lot_width_ft, min_lot_sqft, max_lot_coverage_pct,
   max_impervious_pct, front_setback_ft, side_setback_ft, rear_setback_ft,
   max_height_ft, max_density_du_acre, source_url, ordinance_section, confidence_score)
VALUES
  (14202, 90, 10000, 30.00, 70.00, 25.00, 8.00, 10.00, 35, 4.36,
   'https://www.sjcfl.us/wp-content/uploads/2024/01/article-vi.pdf',
   'LDC Table 6.01 (Art VI Sec 6.01.01), RS-2 row; density = 43560/10000 sqft min lot, same formula as sibling RS-1/RG-1/OR rows',
   1.00),
  (14203, 75, 7500, 35.00, 70.00, 25.00, 8.00, 10.00, 35, 5.81,
   'https://www.sjcfl.us/wp-content/uploads/2024/01/article-vi.pdf',
   'LDC Table 6.01 (Art VI Sec 6.01.01), RG-2 SF Dwellings row; density = 43560/7500 sqft min lot, matches RG-1 SF value exactly (same min lot area)',
   1.00);
-- (zoning_district_id 14202/14203 are the RS-2/RG-2 ids returned by the
--  step-1 INSERT ... RETURNING when this migration was applied live; if
--  re-running from scratch, substitute the ids your own INSERT returns.)
