-- Gold Standard shard-9 (dispatch 255f0be0): highlands-I ULTRALOOP fix
--
-- 45 highlands auction parcels (property-card-completeness gap, letter I)
-- were mailing-addressed to Sebring/Lake Placid but a live spatial
-- point-in-polygon check against Highlands County's own Municipal_Boundary
-- ArcGIS layer confirmed they are all actually in UNINCORPORATED Highlands
-- County. No jurisdiction row existed for that. This migration documents
-- the jurisdiction insert already applied live this session (id=1654);
-- re-running is idempotent via the WHERE NOT EXISTS guard.

INSERT INTO jurisdictions (name, county, county_name, state, data_source, active)
SELECT 'Highlands County', 'Highlands', 'Highlands', 'FL',
       'shard9_255f0be0_unincorporated_jurisdiction_setup', true
WHERE NOT EXISTS (
  SELECT 1 FROM jurisdictions
  WHERE name = 'Highlands County' AND lower(COALESCE(county_name, county)) = 'highlands'
);
