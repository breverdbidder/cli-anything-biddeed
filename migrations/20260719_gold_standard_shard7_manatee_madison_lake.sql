-- SHARD-7 run5153 (dispatch bc399d3b-f50e-406a-a0f1-66d8f4f5d9d7)
-- Counties: manatee, madison, lake
-- Date: 2026-07-19

-- =============================================================================
-- MANATEE G FIX: Ensure parcel_zones coverage for new auction rows
-- =============================================================================
-- New auction rows (fc=81 vs 69 in Jul10) lack parcel_zones entries.
-- Without a parcel_zones row, v_zoning_district_applicability defaults
-- pk1000_applicable=true via COALESCE(a.pk1000_applicable, true), and since
-- parking_per_1000sf is NULL in zone_standards, these parcels count as
-- "pk1000 applicable but missing" -> pk1000=0.0% -> G metric = min()=0.0.
-- Fix: run shard7_manatee_g_pk1000_fix.py to add parcel_zones for new parcels
-- via ArcGIS ZONEOFFICIAL point-in-polygon query.
-- This migration documents the idempotent safety of that script.

-- Verify: no duplicate parcel_zones for manatee jurisdiction
-- SELECT COUNT(*), jurisdiction_id FROM parcel_zones
-- WHERE jurisdiction_id = 1257
-- GROUP BY jurisdiction_id;

-- =============================================================================
-- LAKE J FIX: Backfill bid_decisions for new auction rows
-- =============================================================================
-- auctions_total grew from 98 (Jul11) to 111 (Jul19), causing J to drop from
-- 100% to 84.7%. run shard7_lake_j_backfill_run5153.py (idempotent merge-duplicates).

-- =============================================================================
-- LAKE G/I FIX: Extend parcel_zones for uncovered lake parcels
-- =============================================================================
-- New auctions may lack parcel_zones entries for jurisdiction 835.
-- run shard7_lake_g_i_extend_run5153.py to add via ArcGIS MapServer/50.

-- =============================================================================
-- MADISON: Diagnostic only this session (platform probe)
-- =============================================================================
-- madison A=0: all 5 auctions are foreclosures (td=0)
-- madison B/F: no closed auctions (earliest was 2026-07-14, may have closed)
-- Platform: NOT realauction/realtaxdeed (302 redirect confirmed in SHARD4 report)
-- run shard7_madison_bf_probe_run5153.py to find the real platform

-- No DDL changes in this migration; all changes are DML via the scripts above.
-- Each script includes its own SQL VERIFICATION block.

-- Ultraloop audit rows (from scripts):
-- Claim 1: manatee G PASS after parcel_zones extension
-- Claim 2: lake J >=95% after bid_decisions backfill
-- Claim 3: lake G/I improved after ArcGIS extension
SELECT 'shard7_run5153_migration_loaded' AS status, now() AS loaded_at;
