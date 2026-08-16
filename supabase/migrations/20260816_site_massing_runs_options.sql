-- Site Massing + CAD/DXF Export — Algoma Parity (v1)
-- Session: 2026-08-16
-- Issue: Site Massing + CAD/DXF Export — Algoma Parity (v1)
--
-- NEW, additive infrastructure. Parallel to the existing floorplan tool
-- (public.floor_plans), not a modification of it. Generative footprint/unit
-- placement across a parcel, vs. floorplan = interior room editing on one
-- building.
--
-- Reuses (does not duplicate): zw_parcels (parcel boundary MULTIPOLYGON,
-- SRID 4326), zoning_districts + zone_standards (setbacks/max_ht/min_lot/
-- max_density/max_far/max_lot_coverage per zoning district), and the
-- existing zoning.js dimensional-fit/lot-coverage checker pattern in
-- workers/zonewise-floorplan/zoning.js.
--
-- NOTE on schema fidelity to the original spec: parcel_boundary is declared
-- geometry(Polygon, 4326) per the spec text, but zw_parcels.geom (the real
-- source, verified live 2026-08-16) is MULTIPOLYGON. Widened to
-- geometry(Geometry, 4326) so a real MultiPolygon parcel boundary can be
-- persisted without a silent cast failure — a stricter Polygon-only column
-- would reject every real zw_parcels row.

create table if not exists public.site_massing_runs (
  id uuid primary key default gen_random_uuid(),
  parcel_id text not null,
  co_no int not null,
  zoning_snapshot jsonb not null,
  parcel_boundary geometry(Geometry, 4326) not null,
  status text not null default 'pending',
  created_by text,
  created_at timestamptz not null default now()
);

create table if not exists public.site_massing_options (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references public.site_massing_runs(id) on delete cascade,
  option_rank int not null,
  layout_type text not null,
  footprints jsonb not null,
  unit_count int not null,
  gross_floor_area_sqft numeric not null,
  lot_coverage_pct numeric not null,
  setback_compliant boolean not null,
  score numeric not null,
  dxf_path text,
  created_at timestamptz not null default now()
);

create index if not exists site_massing_runs_parcel_idx on public.site_massing_runs (parcel_id, co_no);
create index if not exists site_massing_options_run_idx on public.site_massing_options (run_id, option_rank);

alter table public.site_massing_runs enable row level security;
alter table public.site_massing_options enable row level security;
-- no anon policy — service_role / authenticated app path only
