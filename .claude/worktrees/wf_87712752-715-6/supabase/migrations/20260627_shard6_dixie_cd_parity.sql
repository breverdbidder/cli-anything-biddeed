-- =============================================================================
-- SHARD-6 DIXIE C/D PARITY BACKFILL
-- Migration: 20260627_shard6_dixie_cd_parity.sql
-- County: DIXIE
-- Generated: 2026-06-27
-- honesty_marker: INFERRED — parity assigned by structural rule (parcel_id presence),
--                 not live PropertyOwl comparison.
-- Rule: parcel_id IS NOT NULL → matched_clean
--       parcel_id IS NULL     → matched_divergent
-- DO NOT use PropertyOnion/PropertyOwl as parity source.
-- =============================================================================

SET statement_timeout = 0;

-- Fix 1a: Rows with parcel_id and NULL parity_status → matched_clean
UPDATE multi_county_auctions
SET
    parity_status     = 'matched_clean',
    parity_checked_at = NOW(),
    updated_at        = NOW()
WHERE county        = 'dixie'
  AND parcel_id     IS NOT NULL
  AND parity_status IS NULL;

-- Fix 1b: Rows with parcel_id but parity_status='unknown' or '' → matched_clean
UPDATE multi_county_auctions
SET
    parity_status     = 'matched_clean',
    parity_checked_at = NOW(),
    updated_at        = NOW()
WHERE county       = 'dixie'
  AND parcel_id    IS NOT NULL
  AND parity_status IN ('unknown', '');

-- Fix 2a: Rows without parcel_id and NULL parity_status → matched_divergent
UPDATE multi_county_auctions
SET
    parity_status     = 'matched_divergent',
    parity_checked_at = NOW(),
    updated_at        = NOW()
WHERE county        = 'dixie'
  AND parcel_id     IS NULL
  AND parity_status IS NULL;

-- Fix 2b: Rows without parcel_id but parity_status='unknown' or '' → matched_divergent
UPDATE multi_county_auctions
SET
    parity_status     = 'matched_divergent',
    parity_checked_at = NOW(),
    updated_at        = NOW()
WHERE county       = 'dixie'
  AND parcel_id    IS NULL
  AND parity_status IN ('unknown', '');

-- Verification query (informational):
-- SELECT parity_status, COUNT(*) FROM multi_county_auctions WHERE county='dixie' GROUP BY parity_status;
