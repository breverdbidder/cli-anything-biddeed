-- Gold Standard shard-1 (dispatch f7cf6ec7): wakulla letter G (zoning
-- density/FAR/parking coverage) fix -- backfill max_density_du_acre for the
-- RSU1 and RSU2 zoning districts (jurisdiction_id=1402, Wakulla County
-- unincorporated), the last documentation gap blocking G from PASS.
--
-- BASELINE (verified live via pencil_dod_evaluate_county('wakulla') at
-- session start):
--   G: {"pass": false, "detail": "density=92.7 far= pk1000=", "metric": 92.7}
--   (threshold >=95.0; density_applicable_parcels=41, density_na_parcels=7)
--
-- DIAGNOSIS: v_zoning_gold_standard_card for county=wakulla showed 8 parcels
-- with NULL max_density_du_acre, split across 3 zone_codes in
-- jurisdiction_id=1402:
--   PUD  (5 parcels, zoning_districts.id=12720) -- prior session already
--     sourced this as a STRUCTURAL fact: Wakulla LDC Article IV sets
--     density/intensity per-development for PUDs, not a single fixed
--     district-wide standard. Correctly excluded from the density-applicable
--     denominator (part of the 7 density_na_parcels). NOT a gap. Left as-is.
--   RSU1 (1 parcel, zoning_districts.id=14274) -- genuine documentation gap,
--     zone_code itself already verified from Wakulla County's official
--     Zoning_Master_Pro ArcGIS layer in a prior session, but zone_standards
--     row (dimensional standards) never populated.
--   RSU2 (2 parcels, zoning_districts.id=14207) -- same genuine gap as RSU1.
-- zone_standards had ZERO rows for either district id before this session
-- (confirmed via direct query on zoning_district_id IN (14274,14207)).
--
-- SOURCE (live WebFetch this session, two independent fetches per section
-- with different extraction prompts, cross-checked and consistent):
--   RSU-1: http://wakullacounty.elaws.us/code/coor_pti_ch5_artiii_sec5-28
--     "Sec. 5-28. RSU-1 Semi-Urban Residential District regulations."
--     Density: 2 dwelling units per acre. Area: 20,000 sqft. Width: 100 ft
--     (40 ft cul-de-sac). Depth: 200 ft.
--   RSU-2: http://wakullacounty.elaws.us/code/coor_pti_ch5_artiii_sec5-28.1
--     "Sec. 5-28.1. RSU-2 Semi-Urban Single-Family Residential District."
--     Density: 2 dwelling units per acre. Area: 20,000 sqft. Width: 100 ft
--     (40 ft cul-de-sac). Depth: 200 ft. Front 25 ft / Side 8 ft / Rear 15 ft
--     setbacks. Max height 35 ft.
--   (RSU-1 and RSU-2 sharing the same density figure is plausible on its
--   face -- both are "Semi-Urban" tiers of the same residential character --
--   and was independently re-confirmed via a second, more detailed fetch of
--   the RSU-2 section quoting the full narrative table before being trusted.)
--
-- WRITE: INSERT into public.zone_standards (no prior rows existed for either
-- zoning_district_id, so this is a fresh insert, not an UPDATE/overwrite).
-- Applied live via PostgREST POST -- see below for the exact statement
-- equivalent; actual apply was a REST POST returning ids 6505 (RSU1) and
-- 6506 (RSU2).
--
-- RESULT (VERIFIED live via pencil_dod_evaluate_county('wakulla')
-- immediately after the write, re-read fresh):
--   G: {"pass": true, "detail": "density=100.0 far= pk1000=", "metric": 100.0}
--   <- 92.7 (FAIL) -> 100.0 (PASS). All 41/41 density-applicable parcels now
--   have a real, ordinance-sourced max_density_du_acre. far=/pk1000= remain
--   blank/all-NA for wakulla as before (0-applicable, unaffected by this fix,
--   LEAST() ignores the NULLs) -- unchanged, not a regression.
--   No other letter touched or re-queried for regression beyond confirming
--   the RPC's full JSON response matched pre-session values for A/B/C/D/E/
--   F/H/I/J (all byte-identical to the pre-write baseline read at session
--   start, except G).

INSERT INTO public.zone_standards
  (zoning_district_id, max_density_du_acre, min_lot_sqft, min_lot_width_ft,
   front_setback_ft, side_setback_ft, rear_setback_ft, max_height_ft,
   source_url, ordinance_section, confidence_score)
VALUES
  (14274, 2.0, 20000, 100, NULL, NULL, NULL, NULL,
   'http://wakullacounty.elaws.us/code/coor_pti_ch5_artiii_sec5-28',
   'Sec. 5-28, Wakulla County LDC, Part I Ch.5 Art.III (RSU-1 Semi-Urban Residential District regulations)',
   0.95),
  (14207, 2.0, 20000, 100, 25, 8, 15, 35,
   'http://wakullacounty.elaws.us/code/coor_pti_ch5_artiii_sec5-28.1',
   'Sec. 5-28.1, Wakulla County LDC, Part I Ch.5 Art.III (RSU-2 Semi-Urban Single-Family Residential District)',
   0.95)
ON CONFLICT DO NOTHING;
