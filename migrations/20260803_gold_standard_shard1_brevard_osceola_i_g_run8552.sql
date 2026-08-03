-- GOLD STANDARD SHARD-1 (brevard+osceola) — run 8552, 2026-08-03
-- dispatch_id: 1f5f4ede-c466-4c43-a9ec-e6ce1d02c1e5
--
-- BREVARD I (84.3% failing → target ≥95%):
--   Root cause (VERIFIED across prior sessions a42bf937/09F985FC/08-01):
--   - ~1124 rows missing property_address: ~98% genuinely no-situs vacant
--     land per gis.brevardfl.gov Parcel_New MapServer/5 (not a scraper gap).
--   - ~56 rows with address+geo but no parcel_zones: sit in Brevard's
--     municipalities (Melbourne, Titusville, Palm Bay, Cocoa, Rockledge, etc.)
--     which maintain separate ArcGIS zoning GIS systems.
--   Fix: scripts/shard1_brevard_osceola_i_fix_run8552.py queries each
--   municipal ArcGIS point-in-polygon endpoint for these parcels' zone codes.
--
-- OSCEOLA G (78.6% failing — pk1000 binding):
--   Root cause (VERIFIED, ac5f5206 + 091fb9f9 sessions):
--   - density: 97.6% (PASSES — T3/T5-M fix from 091fb9f9 2nd firing)
--   - far: ~0% (RS-2 anomaly parcel, jurisdiction mismatch suspected)
--   - pk1000: 78.6% binding (LDC Table 4.7.8 is use-keyed not zone-keyed)
--   Fix: scripts/shard1_osceola_g_pk1000_fix_run8552.py maps DOR_UC →
--   Table 4.7.8 ratio per parcel for commercial-use applicable parcels.
--
-- OSCEOLA I (92.7% failing — 127/137):
--   Residual ~10 rows: placeholder-address rows + OSC- synthetic-id rows.
--   Fix: shard1_brevard_osceola_i_fix_run8552.py FL GIO address matching.
--
-- All writes applied LIVE via GHA runner with SUPABASE_KEY.
-- This file documents the schema context. Writes done by Python scripts.
-- See: .github/workflows/gold-standard-shard1-brevard-osceola-run8552.yml

SET statement_timeout = 0;

-- Diagnostic: current osceola parcel_zones coverage by jurisdiction
SELECT
    j.name as jurisdiction,
    j.id as jurisdiction_id,
    COUNT(DISTINCT pz.parcel_id) as parcel_count,
    COUNT(DISTINCT pz.zone_code) as distinct_zones
FROM parcel_zones pz
JOIN jurisdictions j ON pz.jurisdiction_id = j.id
WHERE lower(j.county) = 'osceola'
GROUP BY j.name, j.id
ORDER BY parcel_count DESC;

-- Diagnostic: Brevard parcels with address+geo but no parcel_zones row
SELECT COUNT(*) as brevard_zoneless_with_address_geo
FROM multi_county_auctions mca
WHERE lower(mca.county) = 'brevard'
  AND mca.property_address IS NOT NULL
  AND mca.latitude IS NOT NULL
  AND mca.longitude IS NOT NULL
  AND mca.parcel_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM parcel_zones pz
      WHERE pz.parcel_id = mca.parcel_id
  );

-- Diagnostic: Osceola incomplete card rows
SELECT COUNT(*) as osceola_card_incomplete
FROM multi_county_auctions mca
WHERE lower(mca.county) = 'osceola'
  AND NOT (
      mca.property_address IS NOT NULL
      AND mca.latitude IS NOT NULL
      AND mca.longitude IS NOT NULL
      AND (mca.assessed_value IS NOT NULL OR mca.market_value IS NOT NULL)
  );

-- Current osceola G sub-metrics from KPI view
SELECT
    county_slug,
    density_pct,
    far_pct,
    pk1000_pct,
    LEAST(density_pct, COALESCE(far_pct, 100), COALESCE(pk1000_pct, 100)) as g_metric
FROM v_zoning_gold_standard_kpi_v3
WHERE county_slug = 'osceola';

-- Verify current evaluator state for both counties
SELECT 'brevard' as county, * FROM public.pencil_dod_evaluate_county('brevard')
UNION ALL
SELECT 'osceola' as county, * FROM public.pencil_dod_evaluate_county('osceola');
