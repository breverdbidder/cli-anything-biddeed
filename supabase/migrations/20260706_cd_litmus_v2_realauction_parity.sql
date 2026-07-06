-- C/D LITMUS V2 — RealAuction source parity (primary) + FloridaBidder fallback
-- ARIEL DIRECTIVE Jul 6 2026: hierarchy = (1) realauction {county}.realforeclose.com /
-- {county}.realtaxdeed.com (source-of-truth recount vs OUR frozen calendar),
-- (2) floridabidder.com fallback, (3) propertyonion tertiary cross-check only
-- (never blocks C/D — fixes structural gaps like hamilton = zero PO rows).
--
-- This migration is idempotent and captures state already applied ad-hoc via
-- the Management API earlier in this session (cd_litmus_hierarchy existed with
-- created_at=2026-07-06 16:23:59 before this file was written — recorded here
-- so the hierarchy declaration is tracked in git, not just live in Postgres).

CREATE TABLE IF NOT EXISTS cd_litmus_hierarchy (
  priority          integer PRIMARY KEY,
  source_slug       text NOT NULL,
  role              text NOT NULL,
  fc_url_template   text,
  td_url_template   text,
  usage_constraint  text,
  constitutional    boolean DEFAULT true,
  directive         text,
  created_at        timestamptz DEFAULT now()
);

INSERT INTO cd_litmus_hierarchy (priority, source_slug, role, fc_url_template, td_url_template, usage_constraint, constitutional, directive)
VALUES
  (1, 'realauction', 'primary',
   'https://{county}.realforeclose.com', 'https://{county}.realtaxdeed.com (or realtdm.com)',
   'Official platform source-of-truth re-count vs OUR frozen calendar. Count/coverage litmus only.',
   true, 'Ariel Shapira, 2026-07-06'),
  (2, 'floridabidder', 'fallback',
   'https://floridabidder.com', 'https://floridabidder.com',
   'Fallback when RealAuction fetch fails or county is off-platform. Count/coverage litmus only.',
   true, 'Ariel Shapira, 2026-07-06'),
  (3, 'propertyonion', 'tertiary_crosscheck',
   NULL, NULL,
   'Tertiary cross-check ONLY. Structural gaps (e.g. hamilton zero rows) NEVER block C/D. NEVER resolution/enrichment/underwriting.',
   true, 'Ariel Shapira, 2026-07-06')
ON CONFLICT (priority) DO NOTHING;

-- V2 parity results table: one row per (county, source, sale_type, window) fetch.
CREATE TABLE IF NOT EXISTS cd_litmus_parity_v2 (
  id            bigserial PRIMARY KEY,
  county_slug   text NOT NULL,
  source        text NOT NULL CHECK (source IN ('realauction','floridabidder','propertyonion')),
  sale_type     text NOT NULL CHECK (sale_type IN ('foreclosure','tax_deed')),
  window_start  date,
  window_end    date,
  source_count  integer,
  our_count     integer,
  match_pct     numeric,
  fetched_at    timestamptz NOT NULL DEFAULT now(),
  status        text NOT NULL DEFAULT 'ok' CHECK (status IN ('ok','unreachable','no_platform','error')),
  notes         text
);

CREATE INDEX IF NOT EXISTS idx_cd_litmus_parity_v2_county ON cd_litmus_parity_v2 (county_slug, source, sale_type, fetched_at DESC);

-- V2 evaluator: layers the V2 hierarchy on top of the existing
-- pencil_dod_evaluate_county() without modifying it (zero blast radius on
-- existing dashboards/callers). Reads the MOST RECENT parity row per
-- (county, sale_type) within the lookback window, aggregates across sale
-- types present, and uses realauction first, floridabidder fallback. Falls
-- back to the original propertyonion-based C/D computation only when no V2
-- row exists at all for the county (tertiary cross-check, per directive).
CREATE OR REPLACE FUNCTION public.pencil_dod_evaluate_county_v2(p_county text, p_lookback_hours integer DEFAULT 48)
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO 'public', 'pipeline', 'pg_catalog'
AS $function$
DECLARE
  v_lc text := lower(p_county);
  v_source text;
  v_rows jsonb;
  v_source_total integer;
  v_our_total integer;
  v_metric numeric;
  v_out jsonb;
BEGIN
  -- Prefer realauction, then floridabidder, whichever has a fresher row in the lookback window.
  SELECT source INTO v_source
  FROM cd_litmus_parity_v2
  WHERE county_slug = v_lc
    AND status = 'ok'
    AND fetched_at >= now() - make_interval(hours => p_lookback_hours)
  ORDER BY CASE source WHEN 'realauction' THEN 1 WHEN 'floridabidder' THEN 2 ELSE 3 END, fetched_at DESC
  LIMIT 1;

  IF v_source IS NULL THEN
    -- No V2 evidence at all: fall back to tertiary (existing propertyonion-based logic), unchanged.
    v_out := pencil_dod_evaluate_county(p_county);
    RETURN v_out || jsonb_build_object('v2_hierarchy_source', 'propertyonion_tertiary_fallback');
  END IF;

  SELECT jsonb_agg(jsonb_build_object('sale_type', sale_type, 'source_count', source_count, 'our_count', our_count, 'match_pct', match_pct, 'fetched_at', fetched_at)),
         sum(source_count), sum(our_count)
    INTO v_rows, v_source_total, v_our_total
  FROM (
    SELECT DISTINCT ON (sale_type) sale_type, source_count, our_count, match_pct, fetched_at
    FROM cd_litmus_parity_v2
    WHERE county_slug = v_lc AND source = v_source AND status = 'ok'
      AND fetched_at >= now() - make_interval(hours => p_lookback_hours)
    ORDER BY sale_type, fetched_at DESC
  ) latest;

  v_metric := round(100.0 * LEAST(COALESCE(v_source_total,0), COALESCE(v_our_total,0))
              / NULLIF(GREATEST(COALESCE(v_source_total,0), COALESCE(v_our_total,0)), 0), 1);

  v_out := jsonb_build_object(
    'county', v_lc,
    'v2_hierarchy_source', v_source,
    'v2_rows', v_rows,
    'C', jsonb_build_object('pass', COALESCE(v_metric >= 99, false), 'metric', v_metric, 'detail', format('%s recount vs frozen calendar, exact-count tolerance', v_source)),
    'D', jsonb_build_object('pass', COALESCE(v_metric >= 95, false), 'metric', v_metric, 'detail', format('%s recount vs frozen calendar, >=95%% tolerance', v_source))
  );
  RETURN v_out;
END;
$function$;
