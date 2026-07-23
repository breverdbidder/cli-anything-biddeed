-- Gold Standard: pasco criterion G regression fix (self-caught via adversarial
-- verification of the batch4 I-fix, same session, dispatch 8c8052cf-60cc-40f8-
-- b049-64523016bdcd).
--
-- Root cause: the pasco-I batch4 migration (20260723163800) inserted a
-- parcel_zones row (parcel_id 18-26-16-0380-30820-00A0, DOR_UC 004 MFR-CONDO)
-- tagged zone_code='RMF' with no corresponding zoning_districts row for
-- jurisdiction 1258. Per v_zoning_gold_standard_kpi_v3's LEFT JOIN +
-- COALESCE(..., true) default, an unmatched zone_code counts as
-- "applicable" for far/pk1000 with no value ever satisfying it -- this is
-- the IDENTICAL failure mode already documented and fixed once before in
-- 20260718220500_pasco_g_regression_fix_batch3_orphaned_districts.sql (same
-- RMF label, same root cause). Dragged G from PASS(100.0) to FAIL(66.7)
-- (far/pk1000 denominator picked up this 1 orphaned parcel).
--
-- Fix: reuse the SAME remediation already established for RMF in the batch3
-- fix -- reclassify onto R-4 (Residential High Density, 7 du/ac), which is
-- density-regulated only (far_regulated/parking not applicable), reusing
-- the real, already-sourced standard rather than inventing a new
-- commercial-shaped FAR/parking number for condo/multi-family residential.
-- No new numeric density/FAR/parking values invented.

SET statement_timeout = 0;

UPDATE parcel_zones
SET zone_code = 'R-4',
    zone_name = 'Residential High Density (7 du/ac)',
    source = source || '|reclassified_shard_pasco_g_regression_fix_batch4/INFERRED:mfr_condo_reuses_existing_r4'
WHERE jurisdiction_id = 1258 AND zone_code = 'RMF';

-- Verification
SELECT * FROM v_zoning_gold_standard_kpi_v3 WHERE county = 'pasco';
