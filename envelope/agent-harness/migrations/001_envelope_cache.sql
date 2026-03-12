-- ============================================================================
-- MIGRATION: envelope_cache table
-- Part of: 3D Building Envelope Analyzer
-- Products: BidDeed.AI + ZoneWise.AI (shared)
-- ============================================================================

-- Create the envelope_cache table
CREATE TABLE IF NOT EXISTS public.envelope_cache (
  parcel_id         TEXT PRIMARY KEY,
  zone_code         TEXT NOT NULL,
  front_setback_ft  NUMERIC,
  side_setback_ft   NUMERIC,
  rear_setback_ft   NUMERIC,
  max_height_ft     NUMERIC,
  max_lot_coverage  NUMERIC,
  far               NUMERIC,
  lot_width_ft      NUMERIC,
  lot_depth_ft      NUMERIC,
  buildable_gfa_sf  NUMERIC,
  envelope_height_ft NUMERIC,
  effective_floors  INTEGER,
  computed_at       TIMESTAMPTZ DEFAULT NOW(),
  source_municipality TEXT NOT NULL,
  created_at        TIMESTAMPTZ DEFAULT NOW(),
  updated_at        TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_envelope_municipality 
  ON public.envelope_cache(source_municipality);

CREATE INDEX IF NOT EXISTS idx_envelope_zone_code 
  ON public.envelope_cache(zone_code);

CREATE INDEX IF NOT EXISTS idx_envelope_gfa 
  ON public.envelope_cache(buildable_gfa_sf DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_envelope_computed 
  ON public.envelope_cache(computed_at);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_envelope_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_envelope_updated ON public.envelope_cache;
CREATE TRIGGER trg_envelope_updated
  BEFORE UPDATE ON public.envelope_cache
  FOR EACH ROW
  EXECUTE FUNCTION update_envelope_timestamp();

-- RLS Policies
ALTER TABLE public.envelope_cache ENABLE ROW LEVEL SECURITY;

-- Free tier: read basic fields only (zone_code, dimensions, GFA)
CREATE POLICY "envelope_free_read" ON public.envelope_cache
  FOR SELECT
  TO anon
  USING (true);

-- Authenticated: full read
CREATE POLICY "envelope_auth_read" ON public.envelope_cache
  FOR SELECT
  TO authenticated
  USING (true);

-- Service role: full CRUD
CREATE POLICY "envelope_service_all" ON public.envelope_cache
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- View for free tier (limited columns)
CREATE OR REPLACE VIEW public.envelope_free AS
  SELECT 
    parcel_id,
    zone_code,
    lot_width_ft,
    lot_depth_ft,
    buildable_gfa_sf,
    effective_floors,
    source_municipality
  FROM public.envelope_cache;

-- View for pro tier (full columns + computed metrics)
CREATE OR REPLACE VIEW public.envelope_pro AS
  SELECT 
    *,
    CASE WHEN (lot_width_ft * lot_depth_ft) > 0 
      THEN ROUND(buildable_gfa_sf / (lot_width_ft * lot_depth_ft)::numeric, 2) 
      ELSE 0 
    END AS actual_far,
    CASE WHEN (lot_width_ft * lot_depth_ft) > 0 
      THEN ROUND(
        ((lot_width_ft - side_setback_ft * 2) * (lot_depth_ft - front_setback_ft - rear_setback_ft)) 
        / (lot_width_ft * lot_depth_ft)::numeric * 100, 1
      )
      ELSE 0 
    END AS buildable_coverage_pct
  FROM public.envelope_cache;

-- Invalidation function (called by ZoneWise webhook on rezoning)
CREATE OR REPLACE FUNCTION invalidate_envelope(p_parcel_id TEXT)
RETURNS void AS $$
BEGIN
  DELETE FROM public.envelope_cache WHERE parcel_id = p_parcel_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Batch invalidation by municipality
CREATE OR REPLACE FUNCTION invalidate_envelope_batch(p_municipality TEXT)
RETURNS INTEGER AS $$
DECLARE
  deleted_count INTEGER;
BEGIN
  DELETE FROM public.envelope_cache 
  WHERE source_municipality = p_municipality;
  GET DIAGNOSTICS deleted_count = ROW_COUNT;
  RETURN deleted_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Stats function for health checks
CREATE OR REPLACE FUNCTION envelope_stats()
RETURNS TABLE(
  municipality TEXT,
  parcel_count BIGINT,
  avg_gfa NUMERIC,
  avg_floors NUMERIC,
  oldest_compute TIMESTAMPTZ,
  newest_compute TIMESTAMPTZ
) AS $$
  SELECT 
    source_municipality,
    COUNT(*),
    ROUND(AVG(buildable_gfa_sf), 0),
    ROUND(AVG(effective_floors), 1),
    MIN(computed_at),
    MAX(computed_at)
  FROM public.envelope_cache
  GROUP BY source_municipality
  ORDER BY COUNT(*) DESC;
$$ LANGUAGE sql SECURITY DEFINER;
