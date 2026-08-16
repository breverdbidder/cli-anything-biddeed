-- Migration: 20260816_zw_building_footprints.sql
-- Purpose: Microsoft GlobalMLBuildingFootprints (CDLA-Permissive-2.0) for Florida,
--          joined to zw_parcels for existing-structure detection / massing inputs.
-- Source: https://bfppub.blob.core.windows.net/$web/2026-07-24/dataset-links.csv
-- License: CDLA Permissive 2.0 (NOT the ODbL microsoft/USBuildingFootprints repo)

CREATE TABLE IF NOT EXISTS public.zw_building_footprints (
  id            BIGSERIAL PRIMARY KEY,
  geom          GEOMETRY(Polygon, 4326) NOT NULL,
  height_m      DOUBLE PRECISION,
  confidence    DOUBLE PRECISION,
  quadkey       TEXT,
  source        TEXT DEFAULT 'microsoft_globalml',
  source_url    TEXT,
  license       TEXT DEFAULT 'CDLA-Permissive-2.0',
  ingested_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_zw_bf_quadkey ON public.zw_building_footprints(quadkey);

ALTER TABLE public.zw_building_footprints ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role full access" ON public.zw_building_footprints
  FOR ALL USING (auth.role() = 'service_role');

-- Additive columns on zw_parcels (ARCH-001 SSOT table) — massing inputs
ALTER TABLE public.zw_parcels ADD COLUMN IF NOT EXISTS building_count INTEGER;
ALTER TABLE public.zw_parcels ADD COLUMN IF NOT EXISTS building_footprint_sqft DOUBLE PRECISION;
ALTER TABLE public.zw_parcels ADD COLUMN IF NOT EXISTS max_building_height_m DOUBLE PRECISION;

-- GiST index built CONCURRENTLY after bulk load (see session report for
-- indisvalid verification — a failed CONCURRENTLY build leaves an invalid
-- index that is silently skipped by the planner).
