-- Repair: zw_parcels geometry corrupted by wrong SRID assumption in
-- scripts/backfill_geom_fdor.py (prior sessions on the ZoneWise GIS 100% mission).
--
-- Root cause: FDOR Statewide Cadastral FeatureServer's f=geojson responses are
-- always WGS84/EPSG:4326 (RFC 7946 / Esri spec), regardless of the layer's native
-- storage SRID (3086, Florida GDL Albers meters). The buggy script wrapped the
-- already-4326 GeoJSON in ST_SetSRID(...,3086) before ST_Transform(...,4326),
-- which silently collapsed every written geometry to a near-zero-area point next
-- to the 3086 projection origin (~23.94N,-87.93W -- open Gulf water, not Florida).
--
-- Detection: real FL parcels never have a centroid there, and every corrupted row
-- has ST_Area(geom::geography) on the order of 1e-6 to 1e-4 m^2 (vs 1,000+ m^2 for
-- real parcels). Confirmed live 2026-08-16 via raw FeatureServer fetch (returned
-- real lon/lat) + Find_SRID('public','zw_parcels','geom') = 4326 + spot-checks
-- (Columbia flagged rows: 1e-6-2e-4 m^2; Wakulla control rows: 1,000-2,600,000 m^2).
--
-- Scope (live count, 2026-08-16): 182,726 rows across 11 counties. This NULLs the
-- corrupted geom/centroid so the fixed script (SetSRID(...,4326), no transform) can
-- correctly re-backfill them. Non-corrupted rows in the same counties (e.g. Pasco's
-- other 268,064 has_geom rows) are untouched -- the WHERE clause is the same tight
-- degenerate-cluster bounding box used to identify the corruption, not a per-county
-- blanket wipe.

UPDATE public.zw_parcels
SET geom = NULL, centroid_lat = NULL, centroid_lon = NULL
WHERE geom IS NOT NULL
  AND centroid_lat BETWEEN 23.0 AND 24.5
  AND centroid_lon BETWEEN -88.5 AND -87.0;
