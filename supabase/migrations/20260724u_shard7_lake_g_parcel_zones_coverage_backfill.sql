-- Lake county letter-G: parcel_zones coverage backfill after letter-E parcel linkage (same session)
--
-- SOURCE: Lake County GIS live zoning polygon layer
--   https://gis.lakecountyfl.gov/lakegis/rest/services/InteractiveMap/MapServer/50/query
--   (fields: Zoning, ZoningDist, ZoningNm, OrdNum, OrdDate) -- unincorporated Lake County only.
--   Cross-checked against Lake County GIS "City Limits In" layer (MapServer/26) to confirm
--   miss points fall genuinely inside incorporated municipalities (Eustis, Clermont,
--   Groveland, Mascotte -- confirmed live, see session report).
--
-- CONTEXT: A separate agent in this session fixed Lake letter-E (parcel linkage), increasing
-- the number of lake auction rows carrying a real parcel_id. Live query showed 41 rows
-- (40 distinct parcel_id) newly linked to real parcel_id + real lat/lon but with ZERO
-- parcel_zones row at all for jurisdiction_id=835 (Lake County) -- a genuine coverage gap,
-- not a standards gap. This migration documents the 2 real live-GIS-verified inserts applied
-- via scripts/shard_lake_g_parcel_zones_coverage_backfill.py (REST POST, not raw SQL -- see
-- script for full method, identical to the prior shard7_run3679_lake_i_real_zoning_backfill.py
-- pattern). The remaining 38 gap parcel_ids returned NO feature from the county GIS layer
-- because they fall inside incorporated municipalities (Eustis, Clermont, Groveland,
-- Mascotte, etc. -- confirmed via City Limits In layer spot-check) which zone their own land;
-- this is an honest structural gap requiring per-municipality zoning layers, NOT a data
-- backfill bug, and is left untouched (no fabrication).
--
-- Equivalent of the 2 live INSERTs actually applied via REST (idempotent re-statement for
-- migration history/audit trail; already live in the DB at time of writing):
--   parcel_id=241825120500010200 -> zone_code=RM  zone_name='Mixed Home Residential'
--   parcel_id=141925044600005400 -> zone_code=R-6 zone_name='Urban Residential'
-- both source='lake_county_gis_zoning_layer_live_g_coverage_backfill', jurisdiction_id=835

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT v.parcel_id, 835, v.zone_code, v.zone_name, 'lake_county_gis_zoning_layer_live_g_coverage_backfill'
FROM (VALUES
  ('241825120500010200', 'RM',  'Mixed Home Residential'),
  ('141925044600005400', 'R-6', 'Urban Residential')
) AS v(parcel_id, zone_code, zone_name)
WHERE NOT EXISTS (
  SELECT 1 FROM parcel_zones pz
  WHERE pz.parcel_id = v.parcel_id AND pz.jurisdiction_id = 835
);

-- EVALUATOR FINDING (documented for closeout, NOT patched here per task instructions):
-- The task brief hypothesized that pk1000_applicable_parcels=0 (all N/A) makes the
-- pct_pk1000_of_applicable NULL, and that this NULL then sinks LEAST(density,far,pk1000)
-- to NULL, failing G even when far=100%. LIVE TEST DISPROVES THIS:
--   SELECT LEAST(75.0::numeric, 100.0::numeric, NULL::numeric);  -- returns 75.0, not NULL
-- Postgres LEAST()/GREATEST() skip NULL arguments (ANSI SQL semantics) unless ALL arguments
-- are NULL. G's pass=false is caused purely by density=75.0 < 95 threshold, not NULL
-- propagation from pk1000. No evaluator bug exists here -- correcting this hypothesis
-- for the record.
--
-- REMAINING DENSITY GAP ROOT CAUSE: exactly the 11 PUD-zoned parcels (33 of 44
-- density-applicable parcels have a real max_density_du_acre -> 33/44 = 75.0%, matches
-- live metric exactly). Lake County's own ordinance (Code of Ordinances Appendix E,
-- Chapter IV Special Districts, Section 4.03.04.A) states PUD residential gross density
-- is determined per-development-agreement (natural features, public facility adequacy,
-- Wekiva point system, etc.), NOT a single county-wide number -- confirmed live via
-- municode API in the prior shard7c_lake_g_zoning_standards_fix.py session. Writing a
-- single max_density_du_acre for PUD would be fabrication per this session's HARD RULES.
-- G's ceiling for Lake County is genuinely 75.0% (density), not reachable to >=95% without
-- fabricating a PUD-wide density number the county's own ordinance says doesn't exist.
