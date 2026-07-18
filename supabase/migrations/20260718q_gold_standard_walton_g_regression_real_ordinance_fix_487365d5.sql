-- SHARD-9 dispatch 487365d5-71dc-4492-b06a-a58da6810cb8
-- Walton G self-inflicted regression: caught + fixed same session (P0 rule)
--
-- Root cause: the walton I-enrichment script (scripts/shard9_walton_cd_i_backfill.py,
-- restored from orphaned branch origin/claude/issue-12747-20260718-1601) inserted 4 new
-- zoning_districts rows (Small Neighborhood, Urban Residential, Coastal Center,
-- Low Density Residential 4/1) sourced live from Walton County's EnerGov ArcGIS
-- FeatureServer, but never populated zone_standards for them. v_zoning_gold_standard_kpi_v3
-- counts every parcel_zones row against the density denominator by default
-- (density_applicable defaults to true for non-commercial/industrial categories), so these
-- 4 new districts + their parcel_zones rows dropped walton G density coverage
-- 100.0% -> 89.2% (FAIL) as an honest but real collateral side effect.
--
-- Fix: real max_density_du_acre / max_far values sourced VERBATIM from the Walton County
-- Comprehensive Plan Future Land Use Element (adopted 12/11/18, amended 4/27/2021),
-- fetched live and parsed with pypdf from
-- https://www.mywaltonfl.gov/DocumentCenter/View/3498/Future-Land-Use-Element
--
-- No guessing: every figure below is quoted from Policy L-1.4.1 or L-1.6.2 verbatim.
-- ============================================================================

SET statement_timeout = 0;

INSERT INTO public.zone_standards
  (zoning_district_id, max_density_du_acre, max_far, source_url, ordinance_section, effective_date, confidence_score)
VALUES
  -- Small Neighborhood (SN), id=11995: Policy L-1.6.2(A), Mixed Use FLU category.
  -- "residential density of ten (10) dwelling units per one (1) acre ... maximum
  -- nonresidential intensity of 0.50 FAR (50%)"
  (11995, 10.00, 0.50,
   'https://www.mywaltonfl.gov/DocumentCenter/View/3498/Future-Land-Use-Element',
   'Comprehensive Plan Future Land Use Element Policy L-1.6.2(A), adopted 12/11/18 amended 4/27/2021',
   '2021-04-27', 0.90),

  -- Urban Residential (UR), id=11996: Policy L-1.4.1(A), Residential FLU category.
  -- Base "maximum residential density shall be four (4) dwelling units per one (1) acre"
  -- (10 du/ac is conditional-use only, not recorded as the base standard).
  -- "maximum intensity of 0.50 FAR (50%)"
  (11996, 4.00, 0.50,
   'https://www.mywaltonfl.gov/DocumentCenter/View/3498/Future-Land-Use-Element',
   'Comprehensive Plan Future Land Use Element Policy L-1.4.1(A), adopted 12/11/18 amended 4/27/2021',
   '2021-04-27', 0.90),

  -- Coastal Center (CC), id=11999: Policy L-1.6.2(C), Mixed Use FLU category.
  -- Base "maximum residential density of eight (8) dwelling units per one (1) acre"
  -- (12 du/ac exception applies only to a specific 30-acre Gulf-front parcel per
  -- Case No. 94-923-CA, not recorded as the base standard).
  -- "maximum nonresidential intensity shall be 1.50 FAR (150%)"
  (11999, 8.00, 1.50,
   'https://www.mywaltonfl.gov/DocumentCenter/View/3498/Future-Land-Use-Element',
   'Comprehensive Plan Future Land Use Element Policy L-1.6.2(C), adopted 12/11/18 amended 4/27/2021',
   '2021-04-27', 0.90),

  -- Low Density Residential 4/1 (LDR 4/1), id=12000: Policy L-1.4.1(D), Residential FLU category.
  -- "maximum residential density within the Low Density Residential 4/1 Zoning District
  -- shall be four (4) dwelling units per one (1) acre ... no nonresidential intensity
  -- is permitted" -- max_far intentionally NULL, not applicable per ordinance text.
  (12000, 4.00, NULL,
   'https://www.mywaltonfl.gov/DocumentCenter/View/3498/Future-Land-Use-Element',
   'Comprehensive Plan Future Land Use Element Policy L-1.4.1(D), adopted 12/11/18 amended 4/27/2021',
   '2021-04-27', 0.90)
ON CONFLICT DO NOTHING;

-- Explicit honest FAR-not-applicable override for LDR 4/1 (matches the established
-- Residential Preservation precedent, id=11396), rather than relying only on the
-- category-based default in v_zoning_district_applicability.
UPDATE public.zoning_districts
   SET far_regulated = false
 WHERE id = 12000;

-- ============================================================================
-- VERIFICATION (run after applying)
-- ============================================================================
-- SELECT public.pencil_dod_evaluate_county('walton');
-- Expected G: density=100.0, far=100.0, pass=true (restored from 89.2% FAIL)
-- ============================================================================
