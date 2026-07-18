-- Gold Standard shard-12 (dispatch 704e70a0) -- okeechobee letter I partial fix.
-- Applied live via Supabase Management API during this session; documents the change.
--
-- 3 auction parcels (cases 472025CA000047CAAXMX, 472025CA000065CAAXMX,
-- 472025CA000112CAAXMX) sit inside City of Okeechobee limits. The county's own
-- zoning GIS (okeechobeegis.com "Grizzly GIS") returns the literal field
-- `Zoning: City` for all three, i.e. the COUNTY explicitly does not carry a zoning
-- code for city-limit parcels -- it defers to city authority. The City of Okeechobee
-- has no queryable GIS/ArcGIS service of its own (only a static 2021 PDF zoning map),
-- so the specific city zoning sub-code (RSF-1/CPO/PUD/etc.) could not be resolved
-- without fabrication risk from eyeballing a vector map.
--
-- Honest resolution: a `CITY` placeholder zoning_districts row (mirroring the
-- pre-existing jurisdiction_id=920 CITY pattern already used elsewhere in the DB)
-- with density_regulated/far_regulated/pk1000_regulated all false -- the same
-- "not regulated by this authority's dataset" pattern used for okeechobee PD and
-- st_johns RS-3/SAB/PUD. This lets the 3 parcels satisfy letter I's zone_code-linkage
-- requirement without corrupting G's density/FAR/parking denominators.
--
-- Live effect (verified + independently adversarially re-verified this session):
-- okeechobee I: 87.0% (47/54) -> 92.6% (50/54). Still FAIL (needs >=95%, 52/54).
-- G confirmed unregressed (density/far/pk1000 denominators unchanged: 18/1/1 applicable
-- parcels before and after).
--
-- Residual gap (4 rows, documented BLOCKED, not fabricated):
--   - 2026TD050 (parcel 1-25-37-35-0070-00060-1760): parcel does not exist in the
--     live county GIS PIN roll for its subdivision block (232-row enumeration
--     confirmed neighbors exist, this PIN and its neighbor do not) -- likely
--     retired/merged/mistyped source data. No address fabricated.
--   - 472025CA000225CAAXMX ("MULTIPLE PARCELS"): source_url (RealForeclose) returns
--     HTTP 403 to automated access; Firecrawl fallback blocked by account credit
--     exhaustion (402), not a data-availability problem.
--   - 472025CA000130CAAXMX / 472025CA000205CAAXMX: no parcel_id/address/source_url
--     on file at all; Clerk case-search portal is a pure JS SPA with no reachable
--     static/REST endpoint from this sandbox.

DO $$
DECLARE
  v_district_id bigint;
BEGIN
  SELECT id INTO v_district_id
    FROM zoning_districts
   WHERE jurisdiction_id = 943 AND code = 'CITY';

  IF v_district_id IS NULL THEN
    INSERT INTO zoning_districts (jurisdiction_id, code, name, category, density_regulated, far_regulated, pk1000_regulated)
    VALUES (943, 'CITY', 'City of Okeechobee (jurisdiction not county-regulated)', 'mixed-use', false, false, false)
    RETURNING id INTO v_district_id;
  END IF;

  INSERT INTO parcel_zones (jurisdiction_id, parcel_id, zone_code, source)
  SELECT 943, p.parcel_id, 'CITY', 'shard12_run4870_okeechobee_city_gis:https://okeechobeegis.com/gis/'
    FROM (VALUES
      ('3-09-37-35-0020-00450-0240'),
      ('3-21-37-35-0190-00070-0130'),
      ('3-22-37-35-0030-000A0-003A')
    ) AS p(parcel_id)
   WHERE NOT EXISTS (
     SELECT 1 FROM parcel_zones pz WHERE pz.jurisdiction_id = 943 AND pz.parcel_id = p.parcel_id
   );
END $$;
