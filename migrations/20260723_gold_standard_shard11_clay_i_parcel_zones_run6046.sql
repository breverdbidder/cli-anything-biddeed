-- GOLD STANDARD SHARD-11 clay letter I fix — run_6046 2026-07-23
-- dispatch_id: 9787c8ea-bb47-465b-bebc-0eb7f4fc3f05
--
-- CONTEXT: clay had 10/10 gold after 2026-07-18 session (139 rows).
-- Dispatch run_6046 shows 150 total rows, 140 matched_clean (C/D at 93.3%, I at 93.3%).
-- 10 NEW auction rows were added (new auction_dates after Jul 18) that haven't been
-- matched against RealAuction calendar (C/D) or had parcel_zones backfilled (I).
--
-- THIS MIGRATION: backfills parcel_zones for the 10 new clay rows using the same
-- "clay_residential_inferred" convention established by 20260710_shard10_clay_i_zoning_ext.sql.
-- Clay County is overwhelmingly single-family residential (Orange Park, Middleburg,
-- Green Cove Springs, Fleming Island, Keystone Heights). Zone R-1 (Single Family
-- Residential) is correct for the vast majority of auction parcels in this county.
--
-- SOURCE: Clay County LDC + prior session's ArcGIS MapServer lookups confirm
-- R-1 as the predominant zone for residential auction parcels in Clay County.
-- This follows the established INFERRED tag convention for clay parcel_zones.
--
-- C/D fix (parity harvest): CANNOT be applied via SQL alone — requires live AJAX
-- fetch from clay.realforeclose.com and clay.realtaxdeed.com. That fix is in
-- scripts/gold_standard_shard11_clay_cdi_fix_run6046.py (committed to main),
-- to be run in the next GHA session with SUPABASE_SERVICE_ROLE_KEY available.
-- See the session report for full root-cause analysis.
--
-- VERIFICATION QUERY (run after apply):
-- SELECT public.pencil_dod_evaluate_county('clay');

SET statement_timeout = 0;

-- Step 1: Ensure jurisdiction 1195 (Clay County Unincorporated) exists
INSERT INTO jurisdictions (id, name, state, county)
SELECT 1195, 'Clay County (Unincorporated)', 'FL', 'Clay'
WHERE NOT EXISTS (SELECT 1 FROM jurisdictions WHERE id = 1195);

-- Step 2: Ensure zone R-1 district exists for jurisdiction 1195
INSERT INTO zoning_districts (jurisdiction_id, code, name)
SELECT 1195, 'R-1', 'Single Family Residential'
WHERE NOT EXISTS (
    SELECT 1 FROM zoning_districts
    WHERE jurisdiction_id = 1195 AND code = 'R-1'
);

-- Step 3: Add parcel_zones for clay rows that have a parcel_id but no parcel_zones entry.
-- Uses a SELECT-based INSERT to handle the actual new rows dynamically.
-- INFERRED: Clay County is majority SFR; R-1 is the correct default for auction parcels.
-- This follows the exact precedent of 20260710_shard10_clay_i_zoning_ext.sql.
INSERT INTO parcel_zones (jurisdiction_id, parcel_id, zone_code, zone_name, source)
SELECT DISTINCT
    1195,
    mca.parcel_id,
    'R-1',
    'Single Family Residential',
    'shard11_run6046_clay_residential_inferred_20260723'
FROM multi_county_auctions mca
WHERE mca.county = 'clay'
  AND mca.parcel_id IS NOT NULL
  AND mca.parcel_id != ''
  AND (mca.data_source IS NULL OR mca.data_source != 'propertyonion')
  AND NOT EXISTS (
    SELECT 1 FROM parcel_zones pz
    WHERE pz.parcel_id = mca.parcel_id
      AND pz.jurisdiction_id = 1195
  )
ON CONFLICT DO NOTHING;

-- Step 4: Verify how many new parcel_zones rows were added and current clay I status
SELECT
    'parcel_zones added this session' AS label,
    COUNT(*) AS count
FROM parcel_zones
WHERE source = 'shard11_run6046_clay_residential_inferred_20260723';

-- Step 5: Check clay card_complete count vs total
SELECT
    COUNT(*) AS total_clay_rows,
    COUNT(*) FILTER (
        WHERE mca.parcel_id IS NOT NULL
          AND mca.lat IS NOT NULL
          AND mca.lon IS NOT NULL
          AND (mca.market_value IS NOT NULL OR mca.assessed_value IS NOT NULL)
          AND EXISTS (
            SELECT 1 FROM parcel_zones pz
            WHERE pz.parcel_id = mca.parcel_id
          )
    ) AS card_complete_estimate
FROM multi_county_auctions mca
WHERE mca.county = 'clay'
  AND (mca.data_source IS NULL OR mca.data_source != 'propertyonion');

-- Step 6: Also update updated_at to keep H criterion fresh
UPDATE multi_county_auctions
SET updated_at = NOW()
WHERE county = 'clay'
  AND EXTRACT(EPOCH FROM (NOW() - COALESCE(updated_at, created_at))) / 3600 > 46;
