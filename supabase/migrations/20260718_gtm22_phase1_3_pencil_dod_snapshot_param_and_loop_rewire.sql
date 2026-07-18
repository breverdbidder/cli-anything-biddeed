-- GTM-22 Phase 1.3: certify-path vs pencil_dod_evaluate_county divergence fix
-- Architect Decision #1 (issue #12745): pencil_dod_evaluate_county /
-- pencil_dod_evaluate_county_rows becomes the SOLE A-J source for both
-- gold_standard_loop() and gold_standard_certify(). gold_standard_certify()
-- already only reads gold_standard_county_status (populated by loop()), so
-- rewiring loop() to consume the RPC is sufficient to align both surfaces.
--
-- Root cause (confirmed live, 2026-07-18): gold_standard_loop() computed A-J
-- inline via its own temp-table formulas. Two independent divergences from
-- the authoritative pencil_dod_evaluate_county():
--   1. snapshot_at (gold_standard_cert_scope frozen-calendar) was applied in
--      loop()'s inline CTEs but pencil_dod_evaluate_county() has no snapshot
--      parameter at all -- always live. Confirmed disagreement: brevard C,
--      orange I, sarasota C/D/I/J -- all 3 are the counties currently under
--      an active gold_standard_cert_scope freeze.
--   2. I-letter formula shape differs even on identical (live, unscoped)
--      data: loop divided card-complete by auctions_total; pencil divides
--      card-complete by the zoning-linked-only subset. Confirmed on
--      sarasota: 58.6% (loop shape) vs 99.5% (pencil shape) on the same
--      live rows.
--
-- Fix: (a) add p_snapshot_at timestamptz DEFAULT NULL to
-- pencil_dod_evaluate_county/_rows, replicating loop()'s exact snapshot
-- row-inclusion filter (created_at/scraped_at/scrape_timestamp gate; H stays
-- live per existing Ariel-authorized policy in gold_standard_cert_scope).
-- This is additive/backward-compatible -- every existing caller (certify
-- router, MCP tools, backtest.py) calls with 1 arg and is unaffected.
-- (b) rewrite gold_standard_loop() to call the RPC per county instead of
-- duplicating the formula, eliminating divergence class 2 entirely and
-- inheriting snapshot handling for class 1.
--
-- IMPORTANT (learned applying this live): CREATE OR REPLACE FUNCTION with a
-- new parameter list does NOT replace a same-named function of a different
-- arity/signature -- Postgres creates a second overload. Applying just the
-- CREATE OR REPLACE below against a database that still has the old 1-arg
-- pencil_dod_evaluate_county(text) / pencil_dod_evaluate_county_rows(text)
-- makes every existing 1-arg call site (certify_router.py, MCP tools)
-- immediately ambiguous and broken. The DROPs below are mandatory and must
-- run before the CREATE OR REPLACE statements, not just once as a manual fix.

DROP FUNCTION IF EXISTS public.pencil_dod_evaluate_county(text);
DROP FUNCTION IF EXISTS public.pencil_dod_evaluate_county_rows(text);

CREATE OR REPLACE FUNCTION public.pencil_dod_evaluate_county(p_county text, p_snapshot_at timestamptz DEFAULT NULL)
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO 'public', 'pipeline', 'pg_catalog'
AS $function$
DECLARE
  v_lc text := lower(p_county);
  v_out jsonb;
BEGIN
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
  WHERE lower(county) = %1$L AND (COALESCE(data_source,'') <> 'propertyonion' OR COALESCE(tier1_authoritative,false) = true)
    AND (%2$L::timestamptz IS NULL
         OR COALESCE(created_at, scraped_at, scrape_timestamp, now()) <= %2$L::timestamptz)
), o AS (
  SELECT count(*) AS verified_outcomes
  FROM multi_county_auctions a3
  WHERE lower(a3.county) = %1$L AND (COALESCE(a3.data_source,'') <> 'propertyonion' OR COALESCE(a3.tier1_authoritative,false) = true)
    AND a3.sold_amount IS NOT NULL
    AND (%2$L::timestamptz IS NULL
         OR COALESCE(a3.created_at, a3.scraped_at, a3.scrape_timestamp, now()) <= %2$L::timestamptz)
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
  WHERE lower(a2.county) = %1$L AND (COALESCE(a2.data_source,'') <> 'propertyonion' OR COALESCE(a2.tier1_authoritative,false) = true)
    AND (%2$L::timestamptz IS NULL
         OR COALESCE(a2.created_at, a2.scraped_at, a2.scrape_timestamp, now()) <= %2$L::timestamptz)
), d AS (
  SELECT count(*) FILTER (WHERE EXISTS (
           SELECT 1 FROM bid_decisions bd
            WHERE bd.case_number=mca.case_number AND bd.arv IS NOT NULL AND bd.max_bid IS NOT NULL
              AND bd.ml_score IS NOT NULL
              AND bd.factors ? 'distress_location' AND bd.factors ? 'distress_property' AND bd.factors ? 'distress_owner'
              AND bd.factors ? 'cma_distressed' AND bd.factors ? 'cma_resale')) AS deal_complete
  FROM multi_county_auctions mca
  WHERE lower(mca.county) = %1$L AND (COALESCE(mca.data_source,'') <> 'propertyonion' OR COALESCE(mca.tier1_authoritative,false) = true)
    AND (%2$L::timestamptz IS NULL
         OR COALESCE(mca.created_at, mca.scraped_at, mca.scrape_timestamp, now()) <= %2$L::timestamptz)
)
SELECT jsonb_build_object(
  'county', %1$L,
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
$q$, v_lc, p_snapshot_at) INTO v_out;

  -- C/D LITMUS V2 (issue #10981): additive-only surface, zero effect on A-J pass/fail.
  v_out := v_out || jsonb_build_object('V2_LITMUS', public.cd_litmus_v2_snapshot(v_lc));

  RETURN v_out;
END;
$function$;

CREATE OR REPLACE FUNCTION public.pencil_dod_evaluate_county_rows(county_slug_arg text, p_snapshot_at timestamptz DEFAULT NULL)
 RETURNS TABLE(letter text, pass boolean, metric numeric, detail text)
 LANGUAGE plpgsql
 STABLE
AS $function$
DECLARE
  v_out jsonb;
  v_letter text;
BEGIN
  v_out := public.pencil_dod_evaluate_county(county_slug_arg, p_snapshot_at);

  IF v_out IS NULL THEN
    letter := 'ERROR';
    pass := false;
    metric := NULL;
    detail := 'pencil_dod_evaluate_county returned NULL for ' || county_slug_arg;
    RETURN NEXT;
    RETURN;
  END IF;

  FOREACH v_letter IN ARRAY ARRAY['A','B','C','D','E','F','G','H','I','J']
  LOOP
    letter := v_letter;
    pass   := COALESCE((v_out->v_letter->>'pass')::boolean, false);
    metric := NULLIF(v_out->v_letter->>'metric','')::numeric;
    detail := v_out->v_letter->>'detail';
    RETURN NEXT;
  END LOOP;
  RETURN;
END;
$function$;

-- gold_standard_loop(): now consumes pencil_dod_evaluate_county_rows as the
-- SOLE A-J source (Decision #1), passing each county's active
-- gold_standard_cert_scope.snapshot_at through. All inline A-J temp-table
-- computation removed -- this is the single point of formula truth from
-- here on, eliminating divergence class 2 (I-formula shape) entirely and
-- correctly inheriting class 1 (snapshot scoping) instead of duplicating it.
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
  SELECT coalesce(array_agg(county_slug), ARRAY[]::text[]) INTO v_scoped
  FROM gold_standard_cert_scope WHERE active;

  INSERT INTO public.gold_standard_county_status
        (loop_run_id, county_slug, letter, status, metric, detail, evaluated_at)
  SELECT v_run, pc.county_slug, rows.letter,
         CASE WHEN rows.pass THEN 'PASS' ELSE 'FAIL' END,
         rows.metric, rows.detail, now()
  FROM pipeline.counties pc
  LEFT JOIN gold_standard_cert_scope s ON s.county_slug = pc.county_slug AND s.active
  CROSS JOIN LATERAL public.pencil_dod_evaluate_county_rows(pc.county_slug, s.snapshot_at) rows;

  GET DIAGNOSTICS v_rows = ROW_COUNT;
  SELECT count(DISTINCT county_slug) INTO v_counties
    FROM public.gold_standard_county_status WHERE loop_run_id = v_run;

  RETURN jsonb_build_object(
    'loop_run_id', v_run,
    'counties', v_counties,
    'rows', v_rows,
    'scoped_counties', v_scoped,
    'elapsed_s', round(extract(epoch from clock_timestamp()-v_t0)::numeric,1),
    'architecture', 'v10_0_sole_rpc_source_pencil_dod_evaluate_county_rows');
END
$function$;
