-- GOLD STANDARD shard11, county=leon, letter I fix (run3645 continuation, 2026-07-11)
-- Adds the missing "Unincorporated Leon County" jurisdiction row so real zoning
-- codes fetched live from Tallahassee-Leon County GIS
-- (https://intervector.leoncountyfl.gov/intervector/rest/services/MapServices/TLC_OverlayZoning_D_WM/MapServer/0,
-- JURISDICTION field = 'County' or 'Multiple') can be linked via parcel_zones.jurisdiction_id.
-- Data rows themselves are inserted directly via Management API in this session
-- (per campaign convention -- INSERT/UPDATE data does not require a migration file,
-- but this new jurisdiction row is a schema-adjacent seed needed before those inserts).

INSERT INTO jurisdictions (name, county, state, co_no, active, data_source)
SELECT 'Unincorporated Leon County', 'Leon', 'FL', 37, true,
       'tlcgis_intervector_zoning_layer:2026-07-11'
WHERE NOT EXISTS (
    SELECT 1 FROM jurisdictions
    WHERE county = 'Leon' AND name = 'Unincorporated Leon County'
);
