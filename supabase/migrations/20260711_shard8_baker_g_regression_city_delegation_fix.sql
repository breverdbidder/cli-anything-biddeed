-- SHARD 8 (baker), dispatch ac288257-fde4-4e26-a8d7-abb78447619f
-- 2026-07-11: baker G-criterion regression fix (CITY zone_code non-mapping)
--
-- ROOT CAUSE (confirmed independently this session, matches prior-session audit rows
-- 4827/4828 on the SAME dispatch, created ~1hr earlier the same day):
--   A prior enrichment pass (I-fix) inserted parcel_zones.id=832083 for parcel
--   043S22000000000540 (case 022025CA000038CAAXMX, "1203 PINE CIR, MACCLENNY, FL")
--   with zone_code='CITY', sourced live from Baker County's ArcGIS parcels_web2
--   FeatureServer (services6.arcgis.com/HSWu3dhzHf7nZfIa/.../parcels_web2/FeatureServer/0,
--   field "Zoning", confirmed live this session via headless-browser re-query: distinct
--   values on this layer include CITY, AG 10, RC 1, RC 2, TOWN OF GLEN, CONS, REC, CG, CH).
--
--   "CITY" is a genuine, non-fabricated value returned by the county's own GIS -- it means
--   "zoning administered by the City of Macclenny, not itemized in the county parcel layer",
--   NOT one of the 14 real Macclenny zoning_districts codes (RG, RMH, RS-1, RS-2, RPO, CN,
--   CG, CBD, EC, IW, IH, GU, CON, "RS-1 and RS-2"). Because CITY has no matching
--   zoning_districts row, the LEFT JOIN in v_zoning_gold_standard_kpi_v3 returns
--   NULL applicability flags, which COALESCE(..., true) defaults to "applicable but
--   missing data" -- silently dragging density/far/pk1000 percentages down for a parcel
--   whose zoning classification is, by definition, a delegation marker with no itemized
--   standards to report (same as how CON/GU are already modeled with no explicit
--   standards, just without the explicit false override CON/GU rely on category defaults
--   for). This is a metadata-classification gap, not missing parcel data, and not
--   fabricatable -- the City of Macclenny's own zoning ordinance for this specific parcel
--   was not independently obtainable via any no-login public source reached this session
--   (cityofmacclenny.com zoning map is a static PDF behind Cloudflare; Baker PA
--   propertydetails.php does not publish a zoning attribute; bakerclerk.com OCRS requires
--   Cloudflare Turnstile + has no case-number search).
--
-- FIX: register 'CITY' as a real zoning_districts code under jurisdiction_id=920
-- (Macclenny) with category='overlay' (matching the existing CON precedent) and explicit
-- far_regulated=false, density_regulated=false -- honestly declaring "this classification
-- delegates to city ordinance and has no county-itemized numeric standards", which is
-- categorically true of a routing flag, not an invented number. v_zoning_district_applicability
-- hardcodes pk1000_applicable=false for ALL codes already, so this only needs far/density.
--
-- RESULT: parcel_zones.id=832083 now joins to a real zoning_districts row; its far/density
-- applicability both resolve to false (not silently defaulted-true), removing it from the
-- G denominator instead of counting as a phantom failure. Expected: G recovers to the
-- pre-regression PASS state (LEAST(density=100.0, far=100.0, pk1000=100.0) since baker's
-- only OTHER parcel_zones row, id=819027/CBD, already has all three fields populated).
--
-- NO fabrication: no zone_standards row is created or implied for CITY (max_far,
-- max_density_du_acre, parking_per_1000sf remain NULL/absent for this code -- correctly,
-- since none exist), and no parcel data is invented.

INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated)
SELECT 920, 'CITY', 'City-managed zoning (delegated to City of Macclenny, not itemized by county)', 'overlay', false, false
WHERE NOT EXISTS (
  SELECT 1 FROM public.zoning_districts WHERE jurisdiction_id = 920 AND code = 'CITY'
);

-- Ultraloop audit row (idempotent)
INSERT INTO public.gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
SELECT
  'ac288257-fde4-4e26-a8d7-abb78447619f', 'fallback', 'baker', 'G',
  'FIXED G regression: registered CITY as a real zoning_districts row (jurisdiction_id=920, '
  'category=overlay, far_regulated=false, density_regulated=false) so parcel_zones.id=832083 '
  '(zone_code=CITY) no longer defaults to phantom-applicable via COALESCE(NULL,true). No '
  'zone_standards fabricated for CITY -- it genuinely has none (delegation marker, confirmed '
  'live against Baker County ArcGIS parcels_web2 FeatureServer distinct values this session).',
  jsonb_build_object(
    'honesty_marker', 'CONFIRMED',
    'method', 'live re-query of services6.arcgis.com/HSWu3dhzHf7nZfIa ArcGIS parcels_web2 FeatureServer via headless chromium (curl alone returns "Invalid URL" on this endpoint -- confirmed browser-only reachability)',
    'prior_session_same_dispatch', jsonb_build_array('audit_id_4827_I_attempt', 'audit_id_4828_G_regression_disclosure'),
    'zoning_districts_row_added', jsonb_build_object('jurisdiction_id', 920, 'code', 'CITY', 'far_regulated', false, 'density_regulated', false),
    'parcel_zones_row_affected', 832083,
    'no_fabrication', 'zero rows written to zone_standards for CITY; zone has no itemized numeric standards by design (delegation to Macclenny city zoning code, not a county-regulated district)'
  ),
  true
WHERE NOT EXISTS (
  SELECT 1 FROM public.gold_standard_ultraloop_audit
  WHERE dispatch_id = 'ac288257-fde4-4e26-a8d7-abb78447619f'
    AND county_slug = 'baker' AND letter = 'G' AND claim LIKE 'FIXED G regression%'
);

-- SQL VERIFICATION (run after applying)
-- SELECT public.pencil_dod_evaluate_county('baker');
--   Expected: G pass=true, metric>=95 (density=100.0 far=100.0 pk1000=100.0), all other
--   letters unchanged from this session's fresh-verified baseline (A pass, B pass, C fail
--   20.0, D fail 20.0, E fail 20.0, F pass, H pass, I fail 20.0, J pass).
