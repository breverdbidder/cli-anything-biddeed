# ZoneWise Zoning-Assignment Coverage Mission

**Companion mission to ZONEWISE_GIS_MISSION.md — read that one too, same pattern, different gap.**

## What this mission is NOT
This is not a zoning-ordinance research project. The ordinance-level data (zoning_districts / zone_standards / permitted_uses) already covers all 67 counties, 357 jurisdictions, 7,945 district definitions — verified Aug 15 2026. Do not re-scrape or re-parse municipal zoning codes.

## What this mission IS
Connecting each real parcel (public.fl_parcels, statewide, all 67 counties) to the zoning-district data that already exists for its jurisdiction, via public.zoning_assignments. Today that table has assignments for exactly 21 jurisdictions, all Brevard County.

## Infrastructure
- Table: public.zoning_assignment_mission_state (singleton, id=1, target_pct default 80.0 — deliberately lower than the GIS mission's 99%, because source-data depth per county is uneven and a lower honest target avoids a mission that can never legitimately report complete)
- Function: public.zoning_assignment_completion_tick() (SECURITY DEFINER) — computes live per-county gap (% of a county's fl_parcels rows with a matching zoning_assignments row), auto-creates a GitHub issue + dispatches cc-runner-ghonly.yml via gha_create_issue/fire_workflow_dispatch if gap_count > 0 and >=7h since last dispatch
- Cron: pg_cron job "zonewise-zoning-assignment-tick" (jobid 11082), schedule 0 3,9,15,21 * * * (offset 3h from the GIS geometry mission's 0 */6 schedule so the two never dispatch in the same instant)

## Per-county method (pick ONE county per session, same discipline as the GIS mission)
(a) Check if the county Property Appraiser's own parcel export already publishes a zoning field directly — often the cheapest path
(b) Spatial point-in-polygon join of parcel centroids (via zw_parcels.geom / centroid_lat/centroid_lng, populated by the GIS geometry mission) against that county's official zoning-district GIS layer, where publicly published (ArcGIS REST/Hub — same discovery method already proven for parcel geometry)
(c) If neither exists for a county today, its real ceiling may be 0% — report honestly, never fabricate a zone_code

Upsert into zoning_assignments (parcel_id, zone_code, jurisdiction, county, co_no, zone_source, zone_confidence, centroid_lat, centroid_lon). Populate zone_source/zone_confidence honestly (e.g. zone_source='county_gis_zoning_layer', zone_confidence='high'/'medium'/'low' based on verified match quality — mirror the confirmed_co_no is_confirmed bar used elsewhere: >=90% agreement, real sample size, never hand-flipped).

## Non-goals
Do not re-parse zoning ordinance text. Do not touch gold_standard_*, insights, or SPD/ZOD (separate repo, separate mission — see ZONEWISE_MCP_TESTFIT_PARITY_METAPROMPT.md §8.3). Do not fabricate coverage numbers.

## Definition of mission-complete
zoning_assignment_completion_tick() finds 0 counties below target_pct on a live query, sets status='complete'. Cron keeps running as a harmless no-op after that unless target_pct is raised.

## First dispatch
Issue #19093, fired manually Aug 15 2026 to confirm the function works end-to-end before trusting the cron — gap_count=67 (every county, since target is measured as % of a county's OWN parcels assigned, and even Brevard's 21-jurisdiction coverage doesn't yet reach 80% of Brevard's total parcel count).
