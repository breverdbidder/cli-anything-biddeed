-- GTM-22J shard3 continuation, county=okaloosa, letter I fix (2026-07-19)
-- Adds the missing "Unincorporated Okaloosa County" jurisdiction row so real
-- zoning codes fetched live from the county's own ArcGIS zoning layer
--   https://okgis.myokaloosa.com/arcgis/rest/services/Planning-Development/
--   Zoning/MapServer/28  (field ZNGPY_ZONE = real zone code, e.g. "R-1")
-- can be linked via parcel_zones.jurisdiction_id.
--
-- Jurisdiction determined per-parcel this session via a live point-in-polygon
-- query against the county's own incorporated-city-limits layer
--   https://okgis.myokaloosa.com/arcgis/rest/services/Admin-Boundaries/
--   Admin_Boundaries/MapServer/99 (field ICLPY_CITY_CODE)
-- Of the 36 okaloosa auction parcels with a real parcel_id + lat/long: 24
-- resolved to ICLPY_CITY_CODE='UNINCORPORATED' (no existing jurisdiction row
-- covers this -- hence this seed), and the remaining 12 fell inside one of
-- the already-present incorporated municipalities (Crestview 5, Fort Walton
-- Beach 3, Niceville 2, Destin 2) which already have jurisdictions rows and
-- need no new seed.
--
-- Zone_code source is NOT one-size-fits-all: confirmed live this session
-- that the County Zoning layer (MapServer/28) returns 0 features for points
-- inside any incorporated city (each municipality is its own zoning
-- authority in Okaloosa), so the 12 in-city parcels were resolved against
-- that city's own zoning GIS layer instead:
--   Crestview       -> services9.arcgis.com/zvdDL6ILvlkPNTg8/.../Zoning_and_FLU/FeatureServer/0 (field ZONE)
--   Fort Walton Beach -> gis.fwb.org/arcgis/rest/services/Maps/Zoning/MapServer/0 (field Zoning)
--   Niceville       -> gis.nicevillefl.gov/server/rest/services/Zoning/MapServer/0 (field Zoning_2015)
--   Destin          -> okgis.myokaloosa.com/arcgis/rest/services/LocalGovernment/Destin_EnerGov/MapServer/6 (field Zone_ABBR)
-- All four discovered live this session (WebSearch + ArcGIS webmap-item
-- resolution for Crestview; direct probe of gis.fwb.org / gis.nicevillefl.gov
-- for the other two) and confirmed to return real zone codes for the exact
-- parcel centroids in question -- see scripts/okaloosa_zoning_substrate_build.py
-- for the per-parcel resolution logic and source-URL constants.
--
-- Unincorporated Okaloosa County falls under the County Zoning layer
-- (MapServer/28) as its zoning authority, and no such jurisdiction row
-- exists yet -- hence this seed, following the same pattern as
-- 20260711_shard11_leon_i_real_zoning_unincorporated_jurisdiction.sql.
--
-- Data rows (parcel_zones) are inserted directly via Management API in this
-- session (per campaign convention -- INSERT/UPDATE data does not require a
-- migration file, but this new jurisdiction row is a schema-adjacent seed
-- needed before those inserts).

INSERT INTO jurisdictions (name, county, state, co_no, active, data_source)
SELECT 'Unincorporated Okaloosa County', 'Okaloosa', 'FL', 46, true,
       'okaloosa_gis_admin_boundaries_citylimit+zoning_layer:2026-07-19'
WHERE NOT EXISTS (
    SELECT 1 FROM jurisdictions
    WHERE county = 'Okaloosa' AND name = 'Unincorporated Okaloosa County'
);
