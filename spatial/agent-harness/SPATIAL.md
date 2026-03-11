# SPATIAL.md — Spatial Conquest Agent SOP

## Architecture
Download GIS zone polygons → Build Shapely STRtree → Download parcel centroids → Point-in-polygon match → Upsert to Supabase.

## Pattern: Download once, index once, match everything locally
Never query GIS per-parcel. Always bulk download + local spatial join.

## Known Endpoints
- Brevard: gis.brevardfl.gov (10,096 polygons, 56 districts)

## Safeguard: 85% minimum coverage before marking complete
