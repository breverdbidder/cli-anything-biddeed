-- CORRECTION to #19128/#19129: SSOT registration for social_banner_history.
--
-- The table public.social_banner_history (county, property_id, posted_date,
-- created_at) already exists live in this project -- created by an earlier,
-- uncommitted attempt at #19128's "exclude counties posted in the last 7
-- days" rotation tracker -- but has zero rows and no code reference anywhere
-- in this repo (the shipped generator, scripts/generate_property_spotlight_
-- content.py, dedupes via content_hash per (platform, county, parcel_id)
-- instead, which does not need this table). Per the SSOT-check-first rule
-- (BIDDEED_SSOT.md / ssot_registry_components precedence), a live table in
-- this domain must not stay unregistered even if this session didn't create
-- it. Registered honestly as 'unused' -- do not read this row as evidence
-- the rotation feature is implemented; it is not.
INSERT INTO public.ssot_registry_components
  (project_key, layer, domain, component_name, source_catalog, source_ref, governance_tier, status, honesty_marker, notes)
SELECT 'biddeed_ai', 'table', 'social', 'social_banner_history', 'internal_table', 'public.social_banner_history', 'reference', 'unused', 'VERIFIED',
   'Table exists live (county, property_id, posted_date, created_at), 0 rows, no migration file, no code reference as of 2026-08-15. Originally proposed in issue #19128 for a 7-day county-rotation dedup; the shipped generator (scripts/generate_property_spotlight_content.py) dedupes via social_content_queue.content_hash per (platform, county, parcel_id) instead and does not write to this table. Registered per SSOT-check-first rule so it is not an orphaned/unregistered table; wire it in or drop it in a future session, do not assume it is live.'
WHERE NOT EXISTS (
  SELECT 1 FROM public.ssot_registry_components
  WHERE project_key = 'biddeed_ai' AND component_name = 'social_banner_history'
);
