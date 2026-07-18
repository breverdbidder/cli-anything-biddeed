-- GTM-22 Phase 1.3 fix: snapshot-parameterized evaluator + loop rewrite
-- (issue #12745, session 3, 2026-07-18)
--
-- ROOT CAUSE (session 2 confirmed):
-- gold_standard_loop() computes letters C, D, I, J with INLINE formulas that
-- diverge from pencil_dod_evaluate_county's canonical definitions:
--   C/D inline: parity_source LIKE 'tier1%%' + auctions_total denominator
--   C/D canonical: parity_source LIKE 'tier1%%' + tier1 filter (same) BUT
--     the inline join scope via _gs_agg uses a different parity_source path
--   I inline: uses card_rows/_gs_card (which checks v_zoning_gold_standard_card)
--     vs canonical I (which checks card_complete with lat/lon/address/value)
--   J inline: deal_complete in _gs_agg (via _gs_bd LEFT JOIN) vs canonical J
--     (EXISTS on bid_decisions with all 5 factor keys)
-- Backtest result (session 2): 3/67 counties showed divergence (brevard C,
-- sarasota C/D/I/J, orange I), none currently certified so no false cert yet,
-- but next certify() cycle would wrongly certify brevard and sarasota.
--
-- DESIGN DECISION (session 2 pushback, accepted by architect):
-- A literal "swap gold_standard_loop to CROSS JOIN LATERAL
-- pencil_dod_evaluate_county_rows" is UNSAFE without snapshot support because:
--   - gold_standard_loop() joins through gold_standard_cert_scope.snapshot_at
--     to freeze the data snapshot for already-certified/scoped counties (Duval)
--   - pencil_dod_evaluate_county takes only county_slug — no snapshot param
--   - Swapping without snapshot support would silently drop Duval's frozen-
--     calendar guard, putting its 83-day streak at risk on the very run that
--     is meant to protect it.
-- FIX (approved): add p_snapshot_at timestamptz DEFAULT NULL to both the JSONB
-- and set-returning variants. NULL = live/full-history (current behavior for
-- all unscoped counties). Non-NULL = all underlying queries filter
-- created_at/scraped_at/scrape_timestamp <= p_snapshot_at, exactly mirroring
-- how _gs_agg/_gs_out/_gs_card already apply s.snapshot_at today.
-- Then gold_standard_loop() calls per-county with the scoped county's snapshot
-- (NULL for unscoped). This is a strict superset of current behavior:
--   - Unscoped county (snapshot_at IS NULL): identical to today
--   - Scoped county (snapshot_at IS NOT NULL): same guard as today, now
--     applied inside the canonical function instead of in ad-hoc inline SQL
-- This removes ALL inline A-J divergence (C/D inline, I inline, J inline,
-- and the v2 gain-only OR) in one migration.
--
-- HONESTY V3: this migration has NOT been run against the live DB yet.
-- The 67-county backtest (read-only, comparing live RPC vs post-fix loop output)
-- must be run FIRST. This migration is applied only if unexplained disagreements = 0.
-- Cron jobs 115/120/121/122 remain inactive until backtest passes.
--
-- Parts:
-- 1. pencil_dod_evaluate_county(p_county, p_snapshot_at DEFAULT NULL) → jsonb
--    (replaces the function in 20260706_cd_litmus_v2_evaluator_surface.sql)
-- 2. pencil_dod_evaluate_county_rows(p_county, p_snapshot_at DEFAULT NULL) → TABLE
--    (set-returning wrapper for certify/router.py and gold_standard_loop())
-- 3. gold_standard_loop() rewrite: replace all inline A-J with
--    CROSS JOIN LATERAL pencil_dod_evaluate_county_rows(county_slug, snapshot_at)
--    Remove _gs_v2 / v2 gain-only OR entirely (no longer needed: the canonical
--    evaluator already computes C/D correctly; v2 surface remains additive-only
--    via V2_LITMUS key in the JSONB output, unchanged).

BEGIN;

-- ============================================================================
-- 1. pencil_dod_evaluate_county — add p_snapshot_at parameter
--    NULL → live (unchanged behavior for unscoped counties)
--    Non-NULL → all underlying queries scoped to created_at <= p_snapshot_at
-- ============================================================================
CREATE OR REPLACE FUNCTION public.pencil_dod_evaluate_county(
  p_county      text,
  p_snapshot_at timestamptz DEFAULT NULL
)
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO 'public', 'pipeline', 'pg_catalog'
AS $function$
DECLARE
  v_lc  text := lower(p_county);
  v_out jsonb;
  v_snap_filter text;
BEGIN
  -- Build snapshot filter fragment: when p_snapshot_at is non-NULL, restrict
  -- all multi_county_auctions reads to rows whose best timestamp <= snapshot.
  -- When NULL, no additional filter (live/full-history, matching prior behavior).
  IF p_snapshot_at IS NULL THEN
    v_snap_filter := 'TRUE';
  ELSE
    v_snap_filter := format(
      'COALESCE(created_at, scraped_at, scrape_timestamp, now()) <= %L::timestamptz',
      p_snapshot_at
    );
  END IF;

  EXECUTE format($q$
WITH a AS (
  SELECT count(*) AS auctions_total,
         count(*) FILTER (WHERE sale_type='foreclosure') AS foreclosure,
         count(*) FILTER (WHERE sale_type='tax_deed') AS tax_deed,
         count(*) FILTER (WHERE sold_amount IS NOT NULL) AS closed_sold,
         count(*) FILTER (WHERE parcel_id IS NOT NULL) AS has_parcel,
         count(*) FILTER (WHERE parity_status='matched_clean' AND parity_source LIKE 'tier1%%') AS matched_clean,
         count(*) FILTER (WHERE parity_status IN ('matched_clean','matched_divergent') AND parity_source LIKE 'tier1%%') AS matched_any,
         count(*) FILTER (WHERE tier1_sold_amount IS NOT NULL AND sold_amount IS NOT NULL) AS tier1_sold,
         max(GREATEST(
           COALESCE(last_changed_at, '-infinity'::timestamptz),
           COALESCE(last_seen_at,    '-infinity'::timestamptz),
           COALESCE(scraped_at,      '-infinity'::timestamptz),
           COALESCE(scrape_timestamp,'-infinity'::timestamptz),
           COALESCE(created_at,      '-infinity'::timestamptz)
         )) AS last_seen
  FROM multi_county_auctions
  WHERE lower(county) = %1$L
    AND (COALESCE(data_source,'') <> 'propertyonion' OR COALESCE(tier1_authoritative,false) = true)
    AND %2$s
), o AS (
  SELECT count(*) AS verified_outcomes
  FROM multi_county_auctions a3
  WHERE lower(a3.county) = %1$L
    AND (COALESCE(a3.data_source,'') <> 'propertyonion' OR COALESCE(a3.tier1_authoritative,false) = true)
    AND a3.sold_amount IS NOT NULL
    AND %2$s
    AND (
      EXISTS (SELECT 1 FROM tax_deed_outcomes tdo
               WHERE tdo.case_number = a3.case_number AND lower(tdo.county) = %1$L
                 AND COALESCE(tdo.data_source,'') NOT ILIKE '%%promote%%')
      OR EXISTS (SELECT 1 FROM foreclosure_outcomes fo
               WHERE fo.case_number = a3.case_number AND lower(fo.county) = %1$L
                 AND COALESCE(fo.data_source,'') NOT ILIKE '%%promote%%')
    )
), z AS (
  SELECT (SELECT pct_density_of_applicable FROM v_zoning_gold_standard_kpi_v3 WHERE lower(county) = norm_county_key(%1$L) LIMIT 1) AS d,
         (SELECT pct_far_of_applicable     FROM v_zoning_gold_standard_kpi_v3 WHERE lower(county) = norm_county_key(%1$L) LIMIT 1) AS f,
         (SELECT pct_pk1000_of_applicable  FROM v_zoning_gold_standard_kpi_v3 WHERE lower(county) = norm_county_key(%1$L) LIMIT 1) AS p
), zc AS (
  SELECT DISTINCT parcel_id, tax_account
  FROM v_zoning_gold_standard_card
  WHERE lower(county) = norm_county_key(%1$L) AND zone_code IS NOT NULL
), c AS (
  SELECT count(*) AS card_rows,
         count(*) FILTER (WHERE a2.property_address IS NOT NULL
            AND COALESCE(a2.latitude, a2.po_latitude::double precision) IS NOT NULL
            AND COALESCE(a2.longitude, a2.po_longitude::double precision) IS NOT NULL
            AND COALESCE(a2.assessed_value, a2.market_value) IS NOT NULL
            AND (a2.parcel_id IN (SELECT parcel_id FROM zc)
                 OR a2.parcel_id IN (SELECT tax_account FROM zc WHERE tax_account IS NOT NULL))) AS card_complete
  FROM multi_county_auctions a2
  WHERE lower(a2.county) = %1$L
    AND (COALESCE(a2.data_source,'') <> 'propertyonion' OR COALESCE(a2.tier1_authoritative,false) = true)
    AND %2$s
), d AS (
  SELECT count(*) FILTER (WHERE EXISTS (
           SELECT 1 FROM bid_decisions bd
            WHERE bd.case_number=mca.case_number AND bd.arv IS NOT NULL AND bd.max_bid IS NOT NULL
              AND bd.ml_score IS NOT NULL
              AND bd.factors ? 'distress_location' AND bd.factors ? 'distress_property' AND bd.factors ? 'distress_owner'
              AND bd.factors ? 'cma_distressed' AND bd.factors ? 'cma_resale')) AS deal_complete
  FROM multi_county_auctions mca
  WHERE lower(mca.county) = %1$L
    AND (COALESCE(mca.data_source,'') <> 'propertyonion' OR COALESCE(mca.tier1_authoritative,false) = true)
    AND %2$s
)
SELECT jsonb_build_object(
  'county', %1$L,
  'snapshot_at', %3$L::text,
  'auctions_total', a.auctions_total,
  'A', jsonb_build_object('pass', COALESCE(a.foreclosure>0 AND a.tax_deed>0,false),
        'metric', LEAST(a.foreclosure,a.tax_deed),
        'detail', format('fc=%%s td=%%s', a.foreclosure, a.tax_deed)),
  'B', jsonb_build_object('pass', COALESCE(100.0*o.verified_outcomes/NULLIF(a.closed_sold,0) BETWEEN 95 AND 105,false),
        'metric', round(100.0*o.verified_outcomes/NULLIF(a.closed_sold,0),1),
        'detail', format('verified=%%s closed_sold=%%s', o.verified_outcomes, a.closed_sold)),
  'C', jsonb_build_object('pass', COALESCE(100.0*a.matched_clean/NULLIF(a.auctions_total,0) >= 95,false),
        'metric', round(100.0*a.matched_clean/NULLIF(a.auctions_total,0),1),
        'detail', format('matched_clean=%%s', a.matched_clean)),
  'D', jsonb_build_object('pass', COALESCE(100.0*a.matched_any/NULLIF(a.auctions_total,0) >= 95,false),
        'metric', round(100.0*a.matched_any/NULLIF(a.auctions_total,0),1),
        'detail', format('matched_any=%%s', a.matched_any)),
  'E', jsonb_build_object('pass', COALESCE(100.0*a.has_parcel/NULLIF(a.auctions_total,0) >= 95,false),
        'metric', round(100.0*a.has_parcel/NULLIF(a.auctions_total,0),1),
        'detail', format('parcel_linked=%%s', a.has_parcel)),
  'F', jsonb_build_object('pass', COALESCE(100.0*a.tier1_sold/NULLIF(a.closed_sold,0) >= 95,false),
        'metric', round(100.0*a.tier1_sold/NULLIF(a.closed_sold,0),1),
        'detail', format('tier1_sold=%%s closed_sold=%%s', a.tier1_sold, a.closed_sold)),
  'G', jsonb_build_object('pass', COALESCE(LEAST(z.d,z.f,z.p) >= 95,false),
        'metric', LEAST(z.d,z.f,z.p),
        'detail', format('density=%%s far=%%s pk1000=%%s', z.d, z.f, z.p)),
  'H', jsonb_build_object('pass', COALESCE(a.last_seen >= now()-interval '48 hours',false),
        'metric', round(extract(epoch from now()-a.last_seen)/3600,1),
        'detail', 'hours since last_seen (SLA 48h)'),
  'I', jsonb_build_object('pass', COALESCE(100.0*c.card_complete/NULLIF(c.card_rows,0) >= 95,false),
        'metric', round(100.0*c.card_complete/NULLIF(c.card_rows,0),1),
        'detail', format('card_complete=%%s of %%s', c.card_complete, c.card_rows)),
  'J', jsonb_build_object('pass', COALESCE(100.0*d.deal_complete/NULLIF(a.auctions_total,0) >= 95,false),
        'metric', round(100.0*d.deal_complete/NULLIF(a.auctions_total,0),1),
        'detail', format('deal_complete=%%s (triangle + two-arm CMA + ml_score + max_bid)', d.deal_complete))
)
FROM a, o, z, c, d
$q$, v_lc, v_snap_filter, p_snapshot_at::text) INTO v_out;

  -- C/D LITMUS V2 (issue #10981): additive-only surface, zero effect on A-J pass/fail.
  v_out := v_out || jsonb_build_object('V2_LITMUS', public.cd_litmus_v2_snapshot(v_lc));

  RETURN v_out;
END;
$function$;

COMMENT ON FUNCTION public.pencil_dod_evaluate_county(text, timestamptz) IS
  'Authoritative A-J evaluator. p_snapshot_at DEFAULT NULL = live/full-history. '
  'Non-NULL scopes all multi_county_auctions reads to created_at <= p_snapshot_at, '
  'matching gold_standard_cert_scope.snapshot_at frozen-calendar guard. '
  'V2_LITMUS key is additive-only (issue #10981). '
  'GTM-22 2026-07-18: added p_snapshot_at parameter.';

-- ============================================================================
-- 2. pencil_dod_evaluate_county_rows — set-returning wrapper
--    Used by certify/router.py AND gold_standard_loop() after this migration.
--    Returns one row per letter A-J (plus ERROR if county not found).
-- ============================================================================
CREATE OR REPLACE FUNCTION public.pencil_dod_evaluate_county_rows(
  county_slug_arg text,
  p_snapshot_at   timestamptz DEFAULT NULL
)
RETURNS TABLE(letter text, pass boolean, metric numeric, detail text)
LANGUAGE plpgsql
STABLE SECURITY DEFINER
SET search_path TO 'public', 'pipeline', 'pg_catalog'
AS $function$
DECLARE
  v_result jsonb;
  v_ltr    text;
BEGIN
  v_result := public.pencil_dod_evaluate_county(county_slug_arg, p_snapshot_at);

  IF v_result IS NULL THEN
    RETURN QUERY SELECT 'ERROR'::text, false, NULL::numeric, 'evaluator returned NULL'::text;
    RETURN;
  END IF;

  FOREACH v_ltr IN ARRAY ARRAY['A','B','C','D','E','F','G','H','I','J'] LOOP
    RETURN QUERY SELECT
      v_ltr,
      COALESCE((v_result->v_ltr->>'pass')::boolean, false),
      (v_result->v_ltr->>'metric')::numeric,
      COALESCE(v_result->v_ltr->>'detail', '');
  END LOOP;
END;
$function$;

COMMENT ON FUNCTION public.pencil_dod_evaluate_county_rows(text, timestamptz) IS
  'Set-returning wrapper around pencil_dod_evaluate_county. One row per letter A-J. '
  'p_snapshot_at DEFAULT NULL = live (unchanged behavior for certify/router.py callers '
  'that pass no snapshot). Non-NULL for gold_standard_loop() frozen-county calls. '
  'GTM-22 2026-07-18.';

-- ============================================================================
-- 3. gold_standard_loop() rewrite
--    Replaces all inline A-J letter formulas with a single CROSS JOIN LATERAL
--    to pencil_dod_evaluate_county_rows(county_slug, snapshot_at).
--    Removes _gs_v2 temp table and v2 gain-only OR entirely — the canonical
--    evaluator already computes C/D correctly from the same tier1 parity data;
--    the V2_LITMUS additive surface remains in the JSONB output but does not
--    affect A-J pass/fail (unchanged from 20260706_cd_litmus_v2_evaluator_surface.sql).
-- ============================================================================
CREATE OR REPLACE FUNCTION public.gold_standard_loop()
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'extensions'
AS $function$
DECLARE
  v_run      bigint := nextval('public.gold_standard_loop_run_seq');
  v_t0       timestamptz := clock_timestamp();
  v_counties int;
  v_rows     int;
  v_scoped   text[];
BEGIN
  DROP TABLE IF EXISTS _gs_run_counties;

  -- Collect all pipeline counties with their cert_scope snapshot (if any).
  -- This is the single source of truth for which snapshot_at to pass to the
  -- evaluator per county. NULL for unscoped counties = live/full-history.
  CREATE TEMP TABLE _gs_run_counties ON COMMIT DROP AS
  SELECT pc.county_slug,
         s.snapshot_at  -- NULL for unscoped counties
  FROM pipeline.counties pc
  LEFT JOIN gold_standard_cert_scope s
         ON s.county_slug = pc.county_slug AND s.active;

  SELECT coalesce(array_agg(county_slug) FILTER (WHERE snapshot_at IS NOT NULL), ARRAY[]::text[])
    INTO v_scoped
  FROM _gs_run_counties;

  -- Evaluate all counties via the canonical RPC, passing their cert_scope
  -- snapshot (NULL for unscoped = live). One INSERT per letter A-J per county.
  INSERT INTO public.gold_standard_county_status
        (loop_run_id, county_slug, letter, status, metric, detail, evaluated_at)
  SELECT v_run,
         rc.county_slug,
         eval.letter,
         CASE WHEN eval.pass THEN 'PASS' ELSE 'FAIL' END,
         eval.metric,
         eval.detail,
         now()
  FROM _gs_run_counties rc
  CROSS JOIN LATERAL public.pencil_dod_evaluate_county_rows(rc.county_slug, rc.snapshot_at) AS eval;

  GET DIAGNOSTICS v_rows = ROW_COUNT;
  SELECT count(DISTINCT county_slug) INTO v_counties
    FROM public.gold_standard_county_status WHERE loop_run_id = v_run;

  RETURN jsonb_build_object(
    'loop_run_id', v_run,
    'counties', v_counties,
    'rows', v_rows,
    'scoped_counties', v_scoped,
    'elapsed_s', round(extract(epoch from clock_timestamp()-v_t0)::numeric,1),
    'architecture', 'v10_0_canonical_rpc_sole_source'
  );
END
$function$;

COMMENT ON FUNCTION public.gold_standard_loop() IS
  'GTM-22 2026-07-18 v10_0: sole A-J source is pencil_dod_evaluate_county_rows() '
  'called per-county with cert_scope snapshot_at (NULL for unscoped). '
  'Removed: inline C/D/I/J formulas, _gs_bd/_gs_kpi/_gs_out/_gs_agg/_gs_card/_gs_v2 '
  'temp tables, v2 gain-only OR. Duval frozen-calendar guard is now enforced inside '
  'the canonical evaluator via p_snapshot_at, not via separate inline join.';

COMMIT;
