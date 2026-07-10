-- Fix for 20260709_gold_standard_loop_wire_cd_litmus_v2.sql (same-day follow-up,
-- caught before this ever reached the 4x/day cron -- run 3490 was a manual test run).
--
-- Bug (VERIFIED live, run 3490, 2026-07-09T18:26Z): the first cut of the C/D wiring
-- delegated unconditionally to pencil_dod_evaluate_county_v2(), whose own internal
-- fallback (when a county has NO live cd_litmus_parity_v2 evidence) calls
-- pencil_dod_evaluate_county() -- which computes matched_clean/matched_any over ALL
-- of multi_county_auctions with NO gold_standard_cert_scope.snapshot_at filtering.
-- gold_standard_loop's original inline C/D calc DID respect that snapshot (the
-- frozen-calendar denominator guard for the 7 actively-scoped counties: brevard,
-- duval, hillsborough, orange, palm_beach, sarasota, volusia). Delegating blindly
-- let post-snapshot rows leak into the denominator for those counties, diluting the
-- match rate. Live proof: brevard C went 96.1% PASS -> 95.0% FAIL in run 3490,
-- and gold_standard_certify() revoked brevard's certification as a direct result --
-- a violation of this issue's explicit "keep frozen-calendar denominator guard
-- intact (our_count basis unchanged)" requirement, not real fresh-parity signal
-- (brevard has zero cd_litmus_parity_v2 rows, live or otherwise -- this was 100%
-- the unscoped-fallback bug, not new evidence).
--
-- Fix: only use pencil_dod_evaluate_county_v2()'s C/D when the county actually HAS
-- live (status='ok', 48h lookback) cd_litmus_parity_v2 evidence -- checked directly
-- against cd_litmus_hierarchy the same way pencil_dod_evaluate_county_v2 does
-- internally. When no live evidence exists, C/D fall back to the ORIGINAL scoped
-- _gs_agg calc byte-for-byte (same formula gold_standard_loop used before this
-- feature), not to pencil_dod_evaluate_county_v2's own unscoped fallback. This
-- preserves the frozen-calendar guard for all 7 scoped counties while still
-- surfacing live RealAuction recount parity for the 13 counties that have it.

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

  -- C/D LITMUS V2 (issue #10981): which counties have LIVE (status='ok', 48h
  -- lookback) cd_litmus_parity_v2 evidence right now -- same hierarchy/status/
  -- lookback predicate pencil_dod_evaluate_county_v2() uses internally. Only
  -- these counties get their C/D wired to the v2 recount; every other county
  -- keeps the original scoped _gs_agg-based calc untouched.
  CREATE TEMP TABLE _gs_v2 ON COMMIT DROP AS
  SELECT DISTINCT ON (county_slug) county_slug,
         public.pencil_dod_evaluate_county_v2(county_slug) AS j
  FROM cd_litmus_parity_v2
  WHERE status = 'ok' AND fetched_at >= now() - interval '48 hours'
  ORDER BY county_slug;

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
    -- C/D LITMUS V2 (issue #10981): use pencil_dod_evaluate_county_v2's C/D when
    -- the county has live cd_litmus_parity_v2 evidence (_gs_v2 populated);
    -- otherwise keep the original scoped inline calc (frozen-calendar guard
    -- preserved for brevard/duval/hillsborough/orange/palm_beach/sarasota/volusia).
    ('C', CASE WHEN v2.j IS NOT NULL THEN COALESCE((v2.j->'C'->>'pass')::boolean, false)
               ELSE COALESCE(100.0*g.matched_clean/NULLIF(g.auctions_total,0) >= 95, false) END,
          CASE WHEN v2.j IS NOT NULL THEN (v2.j->'C'->>'metric')::numeric
               ELSE round(100.0*g.matched_clean/NULLIF(g.auctions_total,0),1) END,
          CASE WHEN v2.j IS NOT NULL THEN 'v2:' || (v2.j->'C'->>'detail')
               ELSE format('matched_clean=%s of %s', COALESCE(g.matched_clean,0), COALESCE(g.auctions_total,0)) END),
    ('D', CASE WHEN v2.j IS NOT NULL THEN COALESCE((v2.j->'D'->>'pass')::boolean, false)
               ELSE COALESCE(100.0*g.matched_any/NULLIF(g.auctions_total,0) >= 95, false) END,
          CASE WHEN v2.j IS NOT NULL THEN (v2.j->'D'->>'metric')::numeric
               ELSE round(100.0*g.matched_any/NULLIF(g.auctions_total,0),1) END,
          CASE WHEN v2.j IS NOT NULL THEN 'v2:' || (v2.j->'D'->>'detail')
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
    'architecture', 'v9_6_cd_litmus_v2_wired_scope_safe');
END
$function$;
