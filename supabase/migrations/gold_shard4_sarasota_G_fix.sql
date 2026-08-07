-- GOLD STANDARD shard-4 sarasota-only, key sarasota-G (letter G, pk1000 sub-metric).
--
-- ROOT CAUSE (confirmed this session): pk1000_applicable_parcels for sarasota = 10 parcels
-- total (small pool). Exactly 1 of those 10, zoning_district_id=13488 (jurisdiction 1699,
-- "Longboat Key (Sarasota)", code M-1 "Marine Commercial Services District", category=
-- commercial), had ZERO zone_standards row at all -> parking_per_1000sf read as NULL ->
-- 9/10 = 90.0%.
--
-- v_zoning_district_applicability check: M-1 has far_regulated/pk1000_regulated/
-- density_regulated all NULL, falling to the default rule (category IN commercial/industrial/
-- mixed-use AND name NOT ILIKE '%pud%' -> TRUE). Marine Commercial Services is a genuine
-- commercial-use district (boat storage, marinas, marine retail) -- not an agricultural/
-- conservation true-N/A case -- so including it in the denominator is correct; this is a real
-- data gap, not an evaluator bug.
--
-- FIX SOURCE: no new scraping needed. A duplicate/legacy jurisdiction row, id=1047
-- ("Longboat Key", no county suffix, category="Non-Residential"), carries its own M-1 district
-- (zoning_district_id=7990, same code, same name "Marine Commercial Services District") with a
-- fully-populated zone_standards row already scraped from the real Longboat Key Municode
-- ordinance on 2026-02-09 (confidence_score=0.85):
--   source: https://library.municode.com/fl/longboat_key/codes/code_of_ordinances?nodeId=
--           TIT15LADECO_CH158ZOCO_ARTIVZODI_158.058ESZODI
--   parking_per_1000sf=4.00, plus lot/setback/height/coverage/open-space standards.
-- Copying that already-verified row onto zoning_district_id=13488 (the district
-- parcel_zones actually references for the Sarasota-scoped jurisdiction 1699) is a same-
-- real-world-district backfill across a duplicate jurisdiction seed, not a fabrication.
--
-- Verified via pencil_dod_evaluate_county('sarasota'): G.pk1000 90.0 -> 100.0 after this
-- insert (density=93.0 and far=95.0 are unaffected -- they trace to different districts
-- entirely: North Port R-3/MH, Sarasota CG/CI/CN, Venice PUD/RMF-4/RMH, City of Sarasota
-- DTC/RMF-2, and this same Longboat Key M-1 district for FAR specifically -- those remain
-- open gaps for a future session).

INSERT INTO public.zone_standards (
  zoning_district_id, min_lot_sqft, min_lot_width_ft, min_lot_depth_ft,
  max_height_ft, max_stories, front_setback_ft, side_setback_ft, rear_setback_ft,
  corner_setback_ft, max_lot_coverage_pct, max_impervious_pct, max_far,
  max_density_du_acre, min_open_space_pct, parking_per_unit, parking_per_1000sf,
  buffer_requirements, landscaping_requirements, source_url, ordinance_section,
  effective_date, confidence_score, scraped_at
)
SELECT
  13488, min_lot_sqft, min_lot_width_ft, min_lot_depth_ft,
  max_height_ft, max_stories, front_setback_ft, side_setback_ft, rear_setback_ft,
  corner_setback_ft, max_lot_coverage_pct, max_impervious_pct, max_far,
  max_density_du_acre, min_open_space_pct, parking_per_unit, parking_per_1000sf,
  buffer_requirements, landscaping_requirements, source_url, ordinance_section,
  effective_date, confidence_score, scraped_at
FROM public.zone_standards
WHERE zoning_district_id = 7990
AND NOT EXISTS (SELECT 1 FROM public.zone_standards WHERE zoning_district_id = 13488);
