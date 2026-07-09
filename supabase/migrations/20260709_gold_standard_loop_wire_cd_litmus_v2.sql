-- Wire gold_standard_loop C/D to cd_litmus_parity_v2 (issue #10981 follow-up).
--
-- Root cause (Ariel Shapira / AI Architect, verified 2026-07-09): the RealAuction
-- parity feed (cd_litmus_parity_v2) has been live since Jul 6 -- 24 status='ok'
-- rows across 13 counties, deduped via ux_parity_v2_county_src_sale -- and
-- pencil_dod_evaluate_county_v2() already reads it correctly (hierarchy order
-- realauction -> floridabidder -> tertiary fallback, status='ok', 48h lookback).
-- But public.gold_standard_loop -- the LIVE 4x/day scorer (jobs 115/120/121/122)
-- -- never called that evaluator. It computed C (matched_clean) / D (matched_any)
-- inline from _gs_agg, a row-level all-time aggregate over multi_county_auctions.
-- That is a fundamentally different, all-time/no-freshness-window measure than
-- the frozen-calendar recount cd_litmus_parity_v2 was built to provide, so fresh
-- RealAuction parity never reached the scoreboard.
--
-- This migration replaces ONLY the C and D VALUES entries in gold_standard_loop
-- with a LEFT JOIN LATERAL call to public.pencil_dod_evaluate_county_v2(county_slug),
-- which already embeds the full hierarchy+status=ok+lookback logic (falls back to
-- the pre-existing row-level pencil_dod_evaluate_county() calc for any county with
-- no live v2 evidence in the lookback window -- i.e. behavior is unchanged for the
-- 54/67 counties with no cd_litmus_parity_v2 rows yet). Everything else in the loop
-- (A,B,E,F,G,H,I,J, the frozen-calendar auctions_total/our_count basis used by every
-- other letter, gold_standard_cert_scope snapshot scoping, temp table set-up) is
-- byte-for-byte untouched. _gs_agg still computes matched_clean/matched_any (now
-- unused by C/D) -- left in place deliberately, not deleted, since this migration's
-- scope is the C/D wiring only.
--
-- HONESTY V3: this is a semantic change, not just plumbing. For the 13 counties
-- with live v2 evidence, C/D now reflects a live RealAuction recount instead of an
-- all-time historical match -- which can also cause a county to LOSE a C or D PASS
-- it held under the old all-time definition, if the live recount for its current
-- calendar window is weaker than its historical match rate. That is the fresh
-- evidence surfacing as designed (Sentinel-correct-by-default), not a bug -- see
-- the SQL VERIFICATION comment on issue #10981 for the actual post-run deltas
-- (gains and any regressions), reported without suppression.

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
  DROP TABLE IF EXISTS _gs_bd, _gs_kpi, _gs_out, _gs_agg, _gs_card;

  SELECT coalesce(array_agg(county_slug), ARRAY[]::text[]) INTO v_scoped
  FROM gold_standard_cert_scope WHERE active;

  CREATE TEMP TABLE _gs_bd ON COMMIT DROP AS
  SELECT DISTINCT bd.case_number
  FROM bid_decisions bd
  WHERE bd.arv IS NOT NULL AND bd.max_bid IS NOT NULL AND bd.ml_score IS NOT NULL
    AND bd.factors ? 'distress_location' AND bd.factors ? 'distress_property'
    AND bd.factors ? 'distress_owner' AND bd.factors ? 'cma_distressed'
    AND bd.factors ? 'cma_resale';

  CREATE TEMP TABLE _gs_kpi ON COMMIT DROP AS
  SELECT lower(county) AS county,
         LEAST(pct_density_of_applicable, pct_far_of_applicable) AS zoning_min,
         pct_density_of_applicable AS d, pct_far_of_applicable AS f, pct_pk1000_of_applicable AS p
  FROM v_zoning_gold_standard_kpi_v3;

  CREATE TEMP TABLE _gs_out ON COMMIT DROP AS
  SELECT norm_county_key(lower(a.county)) AS county, count(*) AS verified_outcomes
  FROM multi_county_auctions a
  LEFT JOIN gold_standard_cert_scope s
         ON s.county_slug = lower(a.county) AND s.active
  WHERE a.sold_amount IS NOT NULL
    AND (COALESCE(a.data_source,'') <> 'propertyonion' OR COALESCE(a.tier1_authoritative,false) = true)
    AND (s.snapshot_at IS NULL
         OR COALESCE(a.created_at, a.scraped_at, a.scrape_timestamp, now()) <= s.snapshot_at)
    AND (
      EXISTS (SELECT 1 FROM tax_deed_outcomes t
               WHERE lower(t.county) = lower(a.county)
                 AND t.case_number = a.case_number
                 AND COALESCE(t.data_source,'') NOT ILIKE '%promote%')
      OR
      EXISTS (SELECT 1 FROM foreclosure_outcomes f
               WHERE lower(f.county) = lower(a.county)
                 AND f.case_number = a.case_number
                 AND COALESCE(f.data_source,'') NOT ILIKE '%promote%')
    )
  GROUP BY 1;

  CREATE TEMP TABLE _gs_agg ON COMMIT DROP AS
  SELECT norm_county_key(lower(a.county)) AS county,
         count(*)                                                        AS auctions_total,
         count(*) FILTER (WHERE a.sale_type='foreclosure')               AS fc,
         count(*) FILTER (WHERE a.sale_type='tax_deed')                  AS td,
         count(*) FILTER (WHERE a.sold_amount IS NOT NULL)               AS closed_sold,
         count(*) FILTER (WHERE a.sold_amount IS NOT NULL AND a.tier1_sold_amount IS NOT NULL) AS sold_with_tier1,
         count(*) FILTER (WHERE a.parcel_id IS NOT NULL)                 AS has_parcel,
         count(*) FILTER (WHERE a.parity_status='matched_clean' AND a.parity_source LIKE 'tier1%%')         AS matched_clean,
         count(*) FILTER (WHERE a.parity_status IN ('matched_clean','matched_divergent') AND a.parity_source LIKE 'tier1%%') AS matched_any,
         count(*) FILTER (WHERE a.tier1_sold_amount IS NOT NULL)         AS tier1_sold,
         count(*) FILTER (WHERE a.property_address IS NOT NULL
                            AND a.latitude  IS NOT NULL
                            AND a.longitude IS NOT NULL
                            AND COALESCE(a.assessed_value, a.market_value) IS NOT NULL
                            AND a.parcel_id IS NOT NULL)                 AS field_complete,
         count(*) FILTER (WHERE bd.case_number IS NOT NULL)              AS deal_complete,
         max(GREATEST(
           COALESCE(a.last_changed_at, '-infinity'::timestamptz),
           COALESCE(a.last_seen_at,    '-infinity'::timestamptz),
           COALESCE(a.scraped_at,      '-infinity'::timestamptz),
           COALESCE(a.created_at,      '-infinity'::timestamptz)
         )) AS last_seen
  FROM multi_county_auctions a
  LEFT JOIN _gs_bd bd ON bd.case_number = a.case_number
  LEFT JOIN gold_standard_cert_scope s
         ON s.county_slug = lower(a.county) AND s.active
  WHERE (COALESCE(a.data_source,'') <> 'propertyonion' OR COALESCE(a.tier1_authoritative,false) = true)
    AND (s.snapshot_at IS NULL
     OR COALESCE(a.created_at, a.scraped_at, a.scrape_timestamp, now()) <= s.snapshot_at)
  GROUP BY 1;

  CREATE TEMP TABLE _gs_card ON COMMIT DROP AS
  SELECT norm_county_key(lower(a.county)) AS county, count(*) AS card_rows
  FROM multi_county_auctions a
  LEFT JOIN gold_standard_cert_scope s
         ON s.county_slug = lower(a.county) AND s.active
  WHERE (COALESCE(a.data_source,'') <> 'propertyonion' OR COALESCE(a.tier1_authoritative,false) = true)
    AND (s.snapshot_at IS NULL
         OR COALESCE(a.created_at, a.scraped_at, a.scrape_timestamp, now()) <= s.snapshot_at)
    AND a.property_address IS NOT NULL
    AND a.latitude  IS NOT NULL
    AND a.longitude IS NOT NULL
    AND COALESCE(a.assessed_value, a.market_value) IS NOT NULL
    AND a.parcel_id IS NOT NULL
    AND EXISTS (SELECT 1 FROM v_zoning_gold_standard_card vc
                 WHERE (vc.parcel_id = a.parcel_id OR vc.tax_account = a.parcel_id)
                   AND lower(vc.county) = norm_county_key(lower(a.county))
                   AND vc.zone_code IS NOT NULL)
  GROUP BY 1;

  INSERT INTO public.gold_standard_county_status
        (loop_run_id, county_slug, letter, status, metric, detail, evaluated_at)
  SELECT v_run, pc.county_slug, l.letter,
         CASE WHEN l.pass THEN 'PASS' ELSE 'FAIL' END,
         l.metric, l.detail, now()
  FROM pipeline.counties pc
  LEFT JOIN _gs_agg  g  ON g.county  = norm_county_key(pc.county_slug)
  LEFT JOIN _gs_out  o  ON o.county  = norm_county_key(pc.county_slug)
  LEFT JOIN _gs_kpi  z  ON z.county  = norm_county_key(pc.county_slug)
  LEFT JOIN _gs_card cc ON cc.county = norm_county_key(pc.county_slug)
  LEFT JOIN LATERAL (
    SELECT public.pencil_dod_evaluate_county_v2(pc.county_slug) AS j
  ) v2 ON true
  CROSS JOIN LATERAL ( VALUES
    ('A', COALESCE(g.fc>0 AND g.td>0, false),
          LEAST(COALESCE(g.fc,0), COALESCE(g.td,0))::numeric,
          format('fc=%s td=%s', COALESCE(g.fc,0), COALESCE(g.td,0))),
    ('B', COALESCE(100.0*o.verified_outcomes/NULLIF(g.closed_sold,0) >= 95
                AND 100.0*o.verified_outcomes/NULLIF(g.closed_sold,0) <= 105, false),
          round(100.0*o.verified_outcomes/NULLIF(g.closed_sold,0),1),
          format('verified=%s closed_sold=%s%s', COALESCE(o.verified_outcomes,0), COALESCE(g.closed_sold,0),
                 CASE WHEN 100.0*o.verified_outcomes/NULLIF(g.closed_sold,0) > 105
                      THEN ' ANOMALY>105 -- reconcile denominator/double-count before certify' ELSE '' END)),
    -- C/D LITMUS V2 (issue #10981): wired to pencil_dod_evaluate_county_v2, which
    -- reads cd_litmus_parity_v2 in hierarchy order (realauction->floridabidder,
    -- status='ok', 48h lookback) and falls back to the original row-level
    -- pencil_dod_evaluate_county() calc when a county has no live v2 evidence.
    -- Replaces the prior inline matched_clean/matched_any/_gs_agg.auctions_total calc.
    ('C', COALESCE((v2.j->'C'->>'pass')::boolean, false),
          (v2.j->'C'->>'metric')::numeric,
          (v2.j->'C'->>'detail')),
    ('D', COALESCE((v2.j->'D'->>'pass')::boolean, false),
          (v2.j->'D'->>'metric')::numeric,
          (v2.j->'D'->>'detail')),
    ('E', COALESCE(100.0*g.has_parcel/NULLIF(g.auctions_total,0) >= 95, false),
          round(100.0*g.has_parcel/NULLIF(g.auctions_total,0),1),
          format('parcel_linked=%s of %s', COALESCE(g.has_parcel,0), COALESCE(g.auctions_total,0))),
    ('F', COALESCE(100.0*g.sold_with_tier1/NULLIF(g.closed_sold,0) >= 95, false),
          round(100.0*g.sold_with_tier1/NULLIF(g.closed_sold,0),1),
          format('tier1_of_sold=%s closed_sold=%s', COALESCE(g.sold_with_tier1,0), COALESCE(g.closed_sold,0))),
    ('G', COALESCE(z.zoning_min >= 95, false),
          z.zoning_min,
          format('density=%s far=%s pk1000=%s', z.d, z.f, z.p)),
    ('H', COALESCE(g.last_seen >= now()-interval '48 hours', false),
          round(extract(epoch from now()-g.last_seen)/3600,1),
          'hours since last_seen (SLA 48h)'),
    ('I', COALESCE(100.0*cc.card_rows/NULLIF(g.auctions_total,0) >= 95, false),
          round(100.0*cc.card_rows/NULLIF(g.auctions_total,0),1),
          format('card_complete=%s field_complete=%s auctions=%s',
                 COALESCE(cc.card_rows,0), COALESCE(g.field_complete,0), COALESCE(g.auctions_total,0))),
    ('J', COALESCE(100.0*g.deal_complete/NULLIF(g.auctions_total,0) >= 95, false),
          round(100.0*g.deal_complete/NULLIF(g.auctions_total,0),1),
          format('deal_complete=%s of %s (triangle + two-arm CMA + ml_score + max_bid)',
                 COALESCE(g.deal_complete,0), COALESCE(g.auctions_total,0)))
  ) AS l(letter, pass, metric, detail);

  GET DIAGNOSTICS v_rows = ROW_COUNT;
  SELECT count(DISTINCT county_slug) INTO v_counties
    FROM public.gold_standard_county_status WHERE loop_run_id = v_run;

  RETURN jsonb_build_object(
    'loop_run_id', v_run,
    'counties', v_counties,
    'rows', v_rows,
    'scoped_counties', v_scoped,
    'elapsed_s', round(extract(epoch from clock_timestamp()-v_t0)::numeric,1),
    'architecture', 'v9_6_cd_litmus_v2_wired');
END
$function$;
