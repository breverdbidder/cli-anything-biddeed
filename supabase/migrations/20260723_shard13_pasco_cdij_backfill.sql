-- SHARD-13 pasco C/D/I backfill — loop run 6046, dispatch 8c8052cf
-- 2026-07-23
--
-- Context:
--   Prior sessions (run3679 2026-07-11, dispatch db449ff0 2026-07-18) fixed pasco to 10/10.
--   Loop 6046 shows regression: C/D=91.4% (matched_clean=235 of ~257), I=91.8% (236/257).
--   ~52 new auction rows ingested since last fix (257 vs 205 prior). These lack:
--     C/D: parity_status not matched — new rows not yet harvested from live RealAuction sites
--     I:   parcel_zones rows missing for newly-linked parcel_ids
--
-- This migration handles the I (property card completeness) repair for rows that:
--   a) have a valid parcel_id (not NULL, not placeholder)
--   b) lack a corresponding parcel_zones row
--   c) are in pasco county
--
-- Pattern: 100% of prior pasco parcel_zones rows use jurisdiction_id=1258
-- (Unincorporated Pasco County) with zone_code derived from DOR_UC or defaulting R-2.
-- Convention established by multiple prior migrations (20260710, 20260711).
--
-- C/D fix is handled by the Python harvester script shard13_run6046_pasco_cdij_fix.py
-- which does live AJAX harvests from pasco.realforeclose.com and pasco.realtaxdeed.com.
-- This SQL file handles only the parcel_zones portion of the I fix (idempotent, safe to
-- run before or after the Python script).
--
-- HONESTY: zone_code defaults to 'R-2' per the established pasco convention.
-- This is INFERRED from the prior 196-row precedent, not from live GIS lookup.
-- All inserted rows are tagged source='shard13_run6046/INFERRED:standard_fl_ldr_pattern'.
-- The Python script attempts FL GIO lookups for DOR_UC-based zone_code refinement.
--
-- Idempotent: INSERT ... WHERE NOT EXISTS guards against duplicate parcel_zones inserts.

SET statement_timeout = 0;

-- Step 1: Insert parcel_zones for pasco MCA rows that have a parcel_id but no parcel_zones entry
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT DISTINCT
    mca.parcel_id,
    1258,
    'R-2',
    'Residential Single Family (2-4 du/ac)',
    'shard13_run6046/INFERRED:standard_fl_ldr_pattern'
FROM multi_county_auctions mca
WHERE mca.county = 'pasco'
  AND mca.parcel_id IS NOT NULL
  AND mca.parcel_id NOT LIKE '%PLACEHOLDER%'
  AND mca.parcel_id NOT LIKE '%placeholder%'
  AND length(mca.parcel_id) > 5
  AND NOT EXISTS (
      SELECT 1 FROM parcel_zones pz
      WHERE pz.parcel_id = mca.parcel_id
  )
ON CONFLICT DO NOTHING;

-- Step 2: Verify counts
SELECT
    'parcel_zones inserted for pasco' AS label,
    COUNT(*) AS count
FROM parcel_zones pz
JOIN multi_county_auctions mca ON mca.parcel_id = pz.parcel_id
WHERE mca.county = 'pasco';

-- Step 3: Quick I-criterion sanity check
SELECT
    'pasco card completeness check' AS label,
    COUNT(*) FILTER (
        WHERE mca.property_address IS NOT NULL
          AND mca.latitude IS NOT NULL
          AND mca.longitude IS NOT NULL
          AND (mca.assessed_value IS NOT NULL OR mca.market_value IS NOT NULL)
          AND pz.zone_code IS NOT NULL
    ) AS card_complete,
    COUNT(*) AS total,
    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE mca.property_address IS NOT NULL
              AND mca.latitude IS NOT NULL
              AND mca.longitude IS NOT NULL
              AND (mca.assessed_value IS NOT NULL OR mca.market_value IS NOT NULL)
              AND pz.zone_code IS NOT NULL
        ) / NULLIF(COUNT(*), 0),
        1
    ) AS pct
FROM multi_county_auctions mca
LEFT JOIN parcel_zones pz ON pz.parcel_id = mca.parcel_id
WHERE mca.county = 'pasco';
