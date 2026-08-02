-- GOLD STANDARD SHARD-2 (dispatch 13b31f39, sumter/flagler) — flagler G fix
--
-- Root cause: zoning_districts.id=7622 (Palm Coast "MPD" — Master Planned
-- Development District, category=Mixed-Use) had far_regulated/pk1000_regulated
-- = NULL. v_zoning_district_applicability's category-based heuristic then
-- defaulted both to applicable=true for lack of an explicit override, but no
-- zone_standards row exists for this district — so the 2 flagler parcels
-- zoned MPD (the ONLY far/pk1000-applicable parcels in the county; all other
-- 271 flagler parcels are residential and correctly non-applicable) could
-- never satisfy the FAR/parking KPI, permanently pinning
-- v_zoning_gold_standard_kpi_v3.pct_far_of_applicable /
-- pct_pk1000_of_applicable at 0.0.
--
-- This is NOT a missing-data gap to backfill with a number. Palm Coast ULDC
-- Chapter 3, Sec. 3.03.04 + Table 3-5 was read directly (workflow
-- wf_ee93dcf8-692, agent research:palm-coast-mpd, honesty_marker=VERIFIED,
-- independently re-confirmed by agent verify:palm-coast-mpd, refuted=false):
--   * Table 3-5 "Nonresidential and Mixed Use Zoning Districts—Dimensional
--     Standards" lists a numeric Maximum FAR for every district EXCEPT MPD,
--     whose FAR cell is explicitly "NA".
--   * Sec. 3.03.04(F): "All development standards ... shall be specified in
--     the Master Planned Development agreement" — FAR is delegated per-project,
--     no fallback blanket number exists in the base code.
--   * Sec. 3.03.04(H)(3): parking is tied to Chapter 5's general standards
--     but explicitly discretionary/modifiable per project — no fixed
--     spaces-per-1000sf ratio is written into the MPD district standards.
-- Both applicable parcels' MPD zoning was independently confirmed current via
-- live Palm Coast ArcGIS zoning FeatureServer point-in-polygon lookups dated
-- 2026-07-27 and 2026-08-01 — not stale data.
--
-- Fix: correct far_regulated/pk1000_regulated from NULL (heuristic default)
-- to false (ordinance-verified: no blanket standard applies). This drops
-- far_applicable_parcels/pk1000_applicable_parcels to 0 for flagler, making
-- pct_far_of_applicable / pct_pk1000_of_applicable NULL rather than 0.0.
-- Postgres LEAST() ignores NULL arguments (confirmed live:
-- SELECT LEAST(98.2::numeric, NULL::numeric, NULL::numeric) = 98.2), so
-- pencil_dod_evaluate_county('flagler').G now resolves to density=98.2 (>=95)
-- instead of being dragged to 0 by an inapplicable heuristic default.
--
-- Verified live before/after via SELECT public.pencil_dod_evaluate_county('flagler'):
--   before: G {"pass": false, "metric": 0.0,  "detail": "density=98.2 far=0.0 pk1000=0.0"}
--   after:  G {"pass": true,  "metric": 98.2, "detail": "density=98.2 far= pk1000="}
-- flagler: 9/10 -> 10/10 (last remaining letter). sumter re-checked same session,
-- unaffected, still 10/10.

UPDATE public.zoning_districts
SET
  far_regulated = false,
  pk1000_regulated = false,
  ordinance_section = 'Sec. 3.03.04 (MPD Development Standards) + Table 3-5 (FAR column = NA for MPD), Palm Coast ULDC Chapter 3',
  description = description || ' -- FAR/parking not blanket-regulated: Sec 3.03.04(F) delegates all dimensional standards (incl. FAR) to the individual MPD Development Agreement; Table 3-5 lists MPD FAR as NA; Sec 3.03.04(H)(3) makes parking case-by-case/discretionary vs Ch.5 baseline. VERIFIED via direct ordinance text read + independent adversarial re-verification, 2026-08-02.'
WHERE id = 7622
  AND far_regulated IS NULL
  AND pk1000_regulated IS NULL;
