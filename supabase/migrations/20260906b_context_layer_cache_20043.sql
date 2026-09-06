-- Issue #20043 item 4 — 30-day cache for the sections 11-14 context layers
-- (FEMA NFHL flood zone, Census ACS neighborhood scores), keyed by ZIP so a
-- report re-run for the same ZIP doesn't re-hit the upstream public API.
-- Read/write path: packages/biddeed-mcp/src/report/context-layers.js.
--
-- New table per M2 — RLS enabled, no anon policy (service_role only, same
-- pattern as every other report-engine cache table in this repo).

CREATE TABLE IF NOT EXISTS public.context_layer_cache (
  id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  zip        text NOT NULL,
  layer      text NOT NULL CHECK (layer IN ('fema', 'acs')),
  payload    jsonb NOT NULL,
  fetched_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_context_layer_cache_zip_layer_fetched_at
  ON public.context_layer_cache (zip, layer, fetched_at DESC);

ALTER TABLE public.context_layer_cache ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS context_layer_cache_service_role_only ON public.context_layer_cache;
CREATE POLICY context_layer_cache_service_role_only
  ON public.context_layer_cache
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);
