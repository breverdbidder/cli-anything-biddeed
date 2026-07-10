-- SHARD-13: Exclude data_source='propertyonion' rows from gold_standard_loop()
-- dispatch_id: 01293e64-aed9-4bbe-8a9e-dcd61f072bf6
-- Session: architect-20260702T080000 (gold standard shard-13: volusia, seminole)
--
-- ROOT CAUSE (VERIFIED live 2026-07-02 via Management API SQL against multi_county_auctions):
--   Commit 3b078a98 (SHARD-5, 00:22:54Z today) added a propertyonion exclusion to
--   pencil_dod_evaluate_county() per HARD GUARDRAIL #1 ("PropertyOnion = litmus ONLY,
--   never a data source"). That fix was NEVER ported to gold_standard_loop() — a
--   separate, independently-maintained implementation (20260626_fix_h_criterion_
--   greatest_freshness.sql) that populates gold_standard_county_status/scoreboard,
--   the table the brief and gold_standard_certify() treat as authoritative.
--
--   seminole has 586 of 668 multi_county_auctions rows (87.7%) with data_source=
--   'propertyonion' (synthetic PO-xxxxxx case_number, no parcel_id, no tier1 parity
--   match). gold_standard_loop() counts all 668 in auctions_total, collapsing
--   C/D/E/I to 11.8/12.3/11.8/11.8%. pencil_dod_evaluate_county('seminole') (already
--   fixed) returns C=96.3 D=100.0 E=96.3 I=96.3 on the correct 82-row denominator —
--   confirmed by reproducing gold_standard_loop's exact pre-fix query live (79/668,
--   82/668, 79/668 match the loop_run 2346 07:30Z snapshot numbers exactly).
--
-- SAFETY VERIFICATION (performed before shipping, not assumed):
--   - H: fleet-wide, every county's non-propertyonion last_seen remains within the
--     48h SLA (checked all 24 contaminated counties live) -- no PASS->FAIL flips.
--   - B/F: seminole has ZERO propertyonion rows with sold_amount IS NOT NULL, and
--     zero matched to tax_deed_outcomes/foreclosure_outcomes -- B/F numerator and
--     denominator both unaffected (63=63 either way).
--   - volusia (and brevard/duval/hillsborough/orange/palm_beach/sarasota) are
--     already protected by an active gold_standard_cert_scope snapshot predating
--     the propertyonion bulk-inserts, so this migration is a no-op for those
--     counties' scoreboard rows -- it only unblocks counties without a scope row
--     (seminole, lee, and others sharing the same contamination pattern).
--   - PropertyOnion rows structurally never populate parcel_id/tier1 parity/zoning
--     match fields, so excluding them from denominators can only raise pass rates,
--     never lower a currently-passing letter for any county.
--
-- FIX 1: add `AND COALESCE(a.data_source,'') <> 'propertyonion'` to every
-- multi_county_auctions scan in gold_standard_loop() (_gs_out, _gs_agg, _gs_card).
--
-- FIX 2 (found while verifying FIX 1, same function, same statement -- bundled
-- rather than shipped as a second CREATE OR REPLACE of the same object): the
-- per-letter `detail` strings use format('fc=%%s td=%%s', ...) etc. This double-
-- percent escaping is required when a query is passed through an OUTER
-- format($q$...$q$, ...) call before EXECUTE (as pencil_dod_evaluate_county does)
-- but gold_standard_loop() is a plain compiled plpgsql body with no outer format()
-- wrapper -- so %%s is evaluated ONCE, directly, and format() treats %% as a
-- literal escaped percent sign, never substituting the arguments. VERIFIED live:
-- `SELECT format('fc=%%s td=%%s', 6, 6)` returns the literal string 'fc=%s td=%s'
-- while `format('fc=%s td=%s', 6, 6)` correctly returns 'fc=6 td=6'. This is why
-- every row in gold_standard_county_status.detail (and the brief's pasted
-- scoreboard) shows unsubstituted "fc=%s td=%s" templates instead of real
-- numbers -- a pre-existing bug since the 20260626 migration, unrelated to
-- propertyonion, now fixed by removing the unnecessary %% escaping in the same
-- VALUES clause. Does not affect status/pass or metric (numeric) columns, only
-- the human-readable detail text. The `LIKE 'tier1%%'` occurrences elsewhere in
-- this function are untouched -- those are literal LIKE-pattern strings, not
-- format() calls, and %% there is a harmless redundant (not broken) wildcard.

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
    AND COALESCE(a.data_source,'') <> 'propertyonion'
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
  WHERE COALESCE(a.data_source,'') <> 'propertyonion'
    AND (s.snapshot_at IS NULL
     OR COALESCE(a.created_at, a.scraped_at, a.scrape_timestamp, now()) <= s.snapshot_at)
  GROUP BY 1;

  CREATE TEMP TABLE _gs_card ON COMMIT DROP AS
  SELECT norm_county_key(lower(a.county)) AS county, count(*) AS card_rows
  FROM multi_county_auctions a
  LEFT JOIN gold_standard_cert_scope s
         ON s.county_slug = lower(a.county) AND s.active
  WHERE COALESCE(a.data_source,'') <> 'propertyonion'
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
    ('C', COALESCE(100.0*g.matched_clean/NULLIF(g.auctions_total,0) >= 95, false),
          round(100.0*g.matched_clean/NULLIF(g.auctions_total,0),1),
          format('matched_clean=%s of %s', COALESCE(g.matched_clean,0), COALESCE(g.auctions_total,0))),
    ('D', COALESCE(100.0*g.matched_any/NULLIF(g.auctions_total,0) >= 95, false),
          round(100.0*g.matched_any/NULLIF(g.auctions_total,0),1),
          format('matched_any=%s of %s', COALESCE(g.matched_any,0), COALESCE(g.auctions_total,0))),
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
    'architecture', 'v9_4_propertyonion_exclusion');
END
$function$;
