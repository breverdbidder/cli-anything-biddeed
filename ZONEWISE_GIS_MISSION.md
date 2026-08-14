# ZoneWise GIS 100% Coverage Mission (standing goal, zero-HITL)

## Goal
Every parcel in public.zw_parcels (Supabase mocerqjnksmhcjzxrewo), all 67 FL counties,
carries a real GIS boundary polygon (geom column). Operational target per county: >= 99%
(true 100% is not realistic — some source records are retired/merged/malformed even in
authoritative county data; document any genuine residual gap rather than fabricate coverage).

## Status model
public.zonewise_gis_mission_state (single row, id=1) tracks target_pct, last_dispatched_at,
last_dispatched_issue, status (in_progress | complete). public.zonewise_gis_completion_tick()
is a SECURITY DEFINER function: computes live gap across all 67 counties, and if status is
not complete and >=7h have passed since the last dispatch (session ceiling, avoids
overlapping/duplicate runs), auto-creates a continuation GitHub issue + dispatches
cc-runner-ghonly.yml (workflow 297104962) with zero human involvement. Scheduled via
pg_cron jobid 11045, every 6 hours (`0 */6 * * *`). Ariel/Claude never need to manually
re-trigger this — it is self-sustaining until zw_parcels clears the bar statewide.

## Primary data source
FDOR Statewide Cadastral FeatureServer (FloridaGIO, free, public, updated Aug 2025):
https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/Florida_Statewide_Cadastral/FeatureServer/0
- Fields CO_NO (double) and PARCEL_ID (string) match the same FDOR NAL lineage already
  used in fl_parcels / fl_parcels_stage / fl_county_codes — high join-key compatibility,
  but ALWAYS sample-verify PARCEL_ID against zw_parcels.pin before a bulk write; a prior
  join in this same project silently zero-matched on a format mismatch once already.
- spatialReference wkid 3086 (Florida State Plane) — NOT 4326. Confirm zw_parcels.geom
  SRID live via Find_SRID before any UPDATE, transform accordingly.
- Pagination cap 2000 records/request (resultOffset + resultRecordCount).
- geometryType esriGeometryPolygon.

## Fallback source (only if FDOR FeatureServer has a genuine gap for a county)
Individual county Property Appraiser GIS portals (ArcGIS REST/Hub, mostly free/public,
listed per-county in the FDOR item description). Scope any fallback pull ONLY to the
still-missing parcel_ids for that county — do not re-pull a whole county twice.

## History
- Prior session (chat, 2026-08-14): brought parcel ATTRIBUTE-row parity (owner, value,
  sale, zoning, etc — everything except geom) to ~100%% across all 67 counties using
  fl_parcels + fl_parcels_stage. That work is DONE and should not be repeated.
- Prior session (chat, 2026-08-14): identified 24 counties below the 95%% geometry bar
  (17 with zero geometry, 7 partial) and dispatched issue #19078 as Phase 1, targeting
  95%%+ using the FDOR FeatureServer above.
- This mission doc + the auto-tick cron were created immediately after #19078 to make
  the goal self-sustaining past 95%% toward the true target of 99%%+ statewide, without
  requiring a human or a chat session to keep re-dispatching manually.

## Non-goals (every session on this mission)
- Do not touch attribute columns (already correct).
- Do not touch gold_standard_*, insights, or unrelated tables.
- Do not touch the known 82-row co_no=5 mislabeled-Bay-County anomaly (separate task).
- Do not fabricate or round up a coverage number — report the real ceiling if a county
  genuinely cannot reach target from available sources.

## Definition of mission-complete
zonewise_gis_completion_tick() finds 0 counties below target_pct on a live query and
sets zonewise_gis_mission_state.status = 'complete'. At that point the cron keeps
running harmlessly (no-op on every future tick) unless someone raises target_pct further
or new counties/parcels are added to the base tables.
