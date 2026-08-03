-- GOLD STANDARD shard-1 (brevard/osceola), dispatch 1f5f4ede-c466-4c43-a9ec-e6ce1d02c1e5
-- Brevard letter I (property card completeness): real, sourced zone-link backfill.
--
-- Diagnosis (live-verified 2026-08-03): I was failing at card_complete=6075/7238 (83.9%).
-- Decomposed the 1163-row gap via direct SQL: 1106 missing property_address (known ~98%
-- genuine no-situs vacant/tax-deed land per the 2026-08-02 session's live GIS check --
-- not re-verified row-by-row again this session, no new information), 13 missing geo,
-- 3 missing value, 41 with address+geo+value present but no parcel_zones row.
--
-- Of the 41 zone-link-only gaps, ran a live point-in-polygon query for every row's lat/lon
-- against Brevard's own authoritative unincorporated zoning GIS
-- (gis.brevardfl.gov/gissrv/rest/services/Planning_Development/Zoning_WKID2881/MapServer/0,
-- field ZONING). 12 of 41 fell inside the unincorporated-county layer's coverage and
-- returned a real, unambiguous zone code. The remaining 29 fell outside this layer's
-- coverage (inside one of Brevard's ~13 incorporated municipalities, e.g. Palm Bay,
-- Cocoa proper, Rockledge -- confirmed by street-suffix/city pattern), which run separate
-- zoning GIS systems not yet integrated into this pipeline. Consistent with the
-- 2026-08-02 session's documented structural ceiling -- not re-litigated, no new
-- municipal GIS integrated this session.
--
-- Applied live via Supabase Management API. card_complete 6075 -> 6087 of 7238 (83.9% -> 84.1%).
-- Still FAILing (<95%) -- confirmed data-availability ceiling, not a scraper/matcher bug.

INSERT INTO parcel_zones (jurisdiction_id, parcel_id, tax_account, zone_code, source) VALUES
  (13, '3004753', '3004753', 'TRC-1', 'gis_brevardfl_gov_spatial_point_query'),
  (13, '3004993', '3004993', 'TRC-1', 'gis_brevardfl_gov_spatial_point_query'),
  (13, '2612405', '2612405', 'TR-1-A', 'gis_brevardfl_gov_spatial_point_query'),
  (13, '2612407', '2612407', 'RU-1-11', 'gis_brevardfl_gov_spatial_point_query'),
  (13, '24 3606-78-F-13', NULL, 'RU-1-7', 'gis_brevardfl_gov_spatial_point_query'),
  (13, '24 3630-54-A-6', NULL, 'RU-2-10', 'gis_brevardfl_gov_spatial_point_query'),
  (13, '24 3525-75-A-2', NULL, 'RU-1-9', 'gis_brevardfl_gov_spatial_point_query'),
  (13, '23 3618-BH-106.6-14', NULL, 'RU-2-15', 'gis_brevardfl_gov_spatial_point_query'),
  (13, '21 3507-75-7-10', NULL, 'RU-1-13', 'gis_brevardfl_gov_spatial_point_query'),
  (13, '24 3536-27-4-18', NULL, 'RU-1-9', 'gis_brevardfl_gov_spatial_point_query'),
  (13, '23 3536-25-3-1', NULL, 'RRMH-1', 'gis_brevardfl_gov_spatial_point_query'),
  (13, '24 3536-56-F-24', NULL, 'RU-1-11', 'gis_brevardfl_gov_spatial_point_query')
ON CONFLICT DO NOTHING;
