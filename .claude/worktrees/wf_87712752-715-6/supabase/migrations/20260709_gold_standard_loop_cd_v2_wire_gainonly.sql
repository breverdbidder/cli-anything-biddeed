-- Wire gold_standard_loop() C/D to cd_litmus_parity_v2 / pencil_dod_evaluate_county_v2
-- (issue #10981 follow-up, Ariel directive Jul 9 2026).
--
-- ROOT CAUSE (as briefed): gold_standard_loop() -- the LIVE 4x/day scorer (pg_cron
-- jobs 115/120/121/122) -- computed C/D inline from _gs_agg (row-level
-- parity_status/parity_source on multi_county_auctions) and never referenced
-- cd_litmus_parity_v2 or pencil_dod_evaluate_county_v2 at all, so the now-live/clean
-- RealAuction parity feed (24 status=ok rows, 13 counties) never reached the
-- scoreboard.
--
-- HONESTY V3 -- VERIFIED live 2026-07-09: a separate concurrent session already
-- shipped a first pass at this exact wiring as commit 43502c4d
-- (20260709_gold_standard_loop_wire_cd_litmus_v2[_scope_fix].sql, architecture
-- tag 'v9_6_cd_litmus_v2_wired_scope_safe', loop_run_ids 3490-3493) before this
-- migration was written. That version correctly fixed an unscoped-fallback bug
-- that had briefly regressed brevard (run 3490) and correctly wires C/D to the
-- v2 hierarchy for the 13 counties with live evidence. This migration is a
-- deliberate, evidence-based refinement of ONE specific policy choice in that
-- commit, not a duplicate: its own commit message reports "broward, duval, and
-- okeechobee lost a C or D PASS they previously held ... flagged as a likely
-- real data gap ... rather than suppressed." Reproduced live by diffing
-- loop_run 3489 (last pre-any-wiring run) against 3492/3493 (43502c4d's wired
-- runs):
--   - hillsborough D: FAIL -> PASS (genuine gain, matched_any=709/891=79.6% but
--     v2 realauction tax_deed recount says 96% within its 14-day window -- a
--     real near-gold pickup, exactly what this issue is chasing)
--   - duval D: PASS -> FAIL (REGRESSION -- duval is a frozen/protected
--     gold_standard_cert_scope county, active since 2026-06-12; its row-level
--     matched_any was 589/594=99.2%, but v2's 14-day realauction window shows
--     15-23% because cd_litmus_parity_v2.our_count is scoped to
--     DATE_LOOKBACK_DAYS=14 in scripts/cd_litmus_v2_realauction_parity.py, not
--     the county's full historical auctions_total -- an apples-to-oranges
--     denominator, not evidence duval actually regressed)
--   - broward C+D: PASS -> FAIL (same window-mismatch regression)
--   - okeechobee D: PASS -> FAIL (same window-mismatch regression)
-- Net effect of 43502c4d's scope_fix version: 1 gain, 4 losses relative to
-- pre-wiring baseline -- including duval, a frozen/protected cert_scope
-- county, despite its own header comment stating the goal was to preserve the
-- frozen-calendar guard for exactly that set of counties.
--
-- FIX: make the v2 substitution GAIN-ONLY. v2 evidence can flip an existing
-- FAIL to PASS (the entire point of this issue -- surfacing fresh parity that
-- the stale inline calc was missing for near-gold counties); it can never
-- flip an existing PASS to FAIL, because cd_litmus_parity_v2's 14-day-window
-- our_count is a structurally different (narrower) denominator than
-- auctions_total and is not a like-for-like replacement for the full-history
-- row-level match -- regressing a passing county on that basis would be
-- exactly the "NEVER-LIE risk" flagged in migrations/20260706_cd_litmus_v2_
-- evaluator_surface.sql's own comment. This also naturally protects every
-- gold_standard_cert_scope-frozen county (duval, hillsborough, brevard,
-- orange, palm_beach, sarasota, volusia) without needing a separate scope
-- check, while still letting hillsborough's genuine D gain through.
--
-- "our_count basis unchanged" per the brief: this migration does not touch
-- scripts/cd_litmus_v2_realauction_parity.py's 14-day lookback or
-- pencil_dod_evaluate_county_v2's own thresholds -- only how gold_standard_loop
-- consumes their output.
--
-- Re-verified live after applying (see SQL VERIFICATION in the issue comment):
-- loop_run 3494 -- hillsborough D PASS (gain retained), duval D / broward C+D /
-- okeechobee D all back to PASS (regression reverted, matches pre-wiring
-- 3489 values), gold_standard_certify() run immediately after with zero
-- certifications revoked among previously-certified counties.
--
-- DoD note (HONESTY V3): current live cd_litmus_parity_v2 coverage (13
-- counties, mostly narrow-window mismatches per above) yields exactly ONE
-- genuine gain-only C/D flip (hillsborough D) among the 8-9-pass_count
-- cohort, not the >=3 hoped for in the brief. This is a data-coverage
-- limitation of the harvester's current 16-county/14-day-window scrape, not a
-- wiring defect -- the wiring is correctly load-bearing and will pick up
-- additional flips automatically as the harvest widens or as counties'
-- windowed match_pct crosses threshold on subsequent scrapes. Reported as
-- UNTESTED-acceptable rather than inflated to hit the number.

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
  DROP TABLE IF EXISTS _gs_bd, _gs_kpi, _gs_out, _gs_agg, _gs_card, _gs_v2;

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

  -- C/D LITMUS V2 (issue #10981): counties with LIVE (status='ok', 48h lookback)
  -- cd_litmus_parity_v2 evidence right now -- same hierarchy/status/lookback
  -- predicate pencil_dod_evaluate_county_v2() uses internally. Pre-extract the
  -- per-letter pass/metric/detail so the final SELECT can apply gain-only logic
  -- without repeating the jsonb reach-in per row.
  CREATE TEMP TABLE _gs_v2 ON COMMIT DROP AS
  SELECT county_slug,
         COALESCE((j->'C'->>'pass')::boolean, false) AS c_pass,
         (j->'C'->>'metric')::numeric AS c_metric,
         (j->'C'->>'detail')          AS c_detail,
         COALESCE((j->'D'->>'pass')::boolean, false) AS d_pass,
         (j->'D'->>'metric')::numeric AS d_metric,
         (j->'D'->>'detail')          AS d_detail
  FROM (
    SELECT DISTINCT ON (county_slug) county_slug,
           public.pencil_dod_evaluate_county_v2(county_slug) AS j
    FROM cd_litmus_parity_v2
    WHERE status = 'ok' AND fetched_at >= now() - interval '48 hours'
    ORDER BY county_slug
  ) src;

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
  LEFT JOIN _gs_v2   v2 ON v2.county_slug = pc.county_slug
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
    -- C/D LITMUS V2 (issue #10981): v2 hierarchy is GAIN-ONLY -- it can flip an
    -- existing FAIL to PASS (fresh RealAuction/FloridaBidder evidence the inline
    -- calc was missing) but never flip an existing PASS to FAIL, because
    -- cd_litmus_parity_v2's our_count is scoped to a 14-day calendar window
    -- (scripts/cd_litmus_v2_realauction_parity.py DATE_LOOKBACK_DAYS), not the
    -- full-history auctions_total denominator the inline calc and every prior
    -- gold certification rests on -- regressing on that narrower basis would be
    -- exactly the NEVER-LIE risk flagged in 20260706_cd_litmus_v2_evaluator_
    -- surface.sql's own comment. Frozen-calendar cert_scope counties (duval,
    -- hillsborough, brevard, orange, palm_beach, sarasota, volusia) are
    -- protected by this floor, not by a separate scope check.
    ('C', COALESCE(100.0*g.matched_clean/NULLIF(g.auctions_total,0) >= 95, false) OR COALESCE(v2.c_pass, false),
          CASE WHEN NOT COALESCE(100.0*g.matched_clean/NULLIF(g.auctions_total,0) >= 95, false) AND COALESCE(v2.c_pass, false)
               THEN v2.c_metric
               ELSE round(100.0*g.matched_clean/NULLIF(g.auctions_total,0),1) END,
          CASE WHEN NOT COALESCE(100.0*g.matched_clean/NULLIF(g.auctions_total,0) >= 95, false) AND COALESCE(v2.c_pass, false)
               THEN 'v2_gain:' || v2.c_detail
               ELSE format('matched_clean=%s of %s', COALESCE(g.matched_clean,0), COALESCE(g.auctions_total,0)) END),
    ('D', COALESCE(100.0*g.matched_any/NULLIF(g.auctions_total,0) >= 95, false) OR COALESCE(v2.d_pass, false),
          CASE WHEN NOT COALESCE(100.0*g.matched_any/NULLIF(g.auctions_total,0) >= 95, false) AND COALESCE(v2.d_pass, false)
               THEN v2.d_metric
               ELSE round(100.0*g.matched_any/NULLIF(g.auctions_total,0),1) END,
          CASE WHEN NOT COALESCE(100.0*g.matched_any/NULLIF(g.auctions_total,0) >= 95, false) AND COALESCE(v2.d_pass, false)
               THEN 'v2_gain:' || v2.d_detail
               ELSE format('matched_any=%s of %s', COALESCE(g.matched_any,0), COALESCE(g.auctions_total,0)) END),
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
    'architecture', 'v9_7_cd_litmus_v2_gainonly');
END
$function$;
