-- GOLD STANDARD SHARD-1 (duval/gadsden/okeechobee/columbia) — dispatch a1f33d10, 3rd firing
-- Purge dead fabricated zoning_districts row for Columbia (jurisdiction_id=974 "Lake City").
--
-- zoning_districts.id=10717, code='R-1', name='Single Family Residential (Shard7 Synthetic)'
-- was left behind after a prior session purged the 6 SYN-COL-* parcel_zones ghost rows that
-- referenced it (see GOLD_STANDARD_SHARD1_DUVAL_GADSDEN_OKEECHOBEE_COLUMBIA_DISPATCH_A1F33D10_SESSION_REPORT.md,
-- "Columbia G ghost-success purge"). It had zero parcel_zones references (verified live,
-- ref_count=0) but still carried a zone_standards child row with unsourced values
-- (max_far=0.35, max_density_du_acre=4.00, no source_url, no ordinance_section) — a landmine
-- that could silently reintroduce fabricated G/I data if a future write ever reused code 'R-1'
-- for jurisdiction 974 without checking. Deleted both rows. No live metric depended on it
-- (parcel_zones for jurisdiction 974 was already empty before this migration).

BEGIN;

DELETE FROM zone_standards WHERE zoning_district_id = 10717;
DELETE FROM zoning_districts WHERE id = 10717 AND jurisdiction_id = 974 AND code = 'R-1' AND name ILIKE '%synthetic%';

COMMIT;
