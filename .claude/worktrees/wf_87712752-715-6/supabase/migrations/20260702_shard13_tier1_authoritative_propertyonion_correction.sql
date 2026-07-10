-- SHARD-13 URGENT CORRECTION: refine the propertyonion exclusion to preserve
-- tier1-verified rows, in BOTH pencil_dod_evaluate_county() and gold_standard_loop()
-- dispatch_id: 01293e64-aed9-4bbe-8a9e-dcd61f072bf6
-- Session: architect-20260702T080000 (gold standard shard-13: volusia, seminole)
--
-- WHAT HAPPENED: this session shipped
-- 20260702_shard13_gold_standard_loop_propertyonion_exclusion.sql minutes ago,
-- adding `AND COALESCE(data_source,'') <> 'propertyonion'` to gold_standard_loop(),
-- mirroring the fix commit 3b078a98 (shard-5, 00:22:54Z today) already shipped to
-- pencil_dod_evaluate_county(). Both were blanket exclusions on `data_source` alone.
--
-- An adversarial ULTRALOOP verification agent (workflow wf_f8f2178a-493, spawned
-- before shipping per the ULTRALOOP protocol, but which finished AFTER the ship
-- decision was made) found and this session independently CONFIRMED live: 5 rows
-- across charlotte (4) and st_johns (1) carry `data_source='propertyonion'` AND
-- `provenance='po_only_2026_05_13_backfill'` (i.e. they originated as PropertyOnion
-- backfills) BUT were subsequently independently re-verified via a DIFFERENT
-- platform (source_platform='realforeclose') and stamped `tier1_authoritative=true`,
-- `parity_status='matched_clean'`. `tier1_authoritative` is the established,
-- widely-used flag across dozens of prior shard sessions (grep confirms usage in
-- shard3_jefferson_bootstrap.py, shard5_run1524_suwannee_bootstrap.py,
-- shard9_run757_*.py, etc.) for "this row has been independently verified, trust
-- it" -- distinct from data_source ORIGIN. A blanket `data_source='propertyonion'`
-- filter conflates "PropertyOnion litmus-only, never independently verified" (the
-- thing HARD GUARDRAIL #1 exists to prevent) with "PropertyOnion-originated but
-- subsequently tier1-verified" (legitimate, already-certified data). The blanket
-- filter would have silently dropped charlotte/st_johns from 43->41 fleet-wide
-- gold_standard=true counties -- a real regression, not the "ghost success
-- correction" this session's report initially characterized it as.
--
-- VERIFIED (live, this session, before writing this fix): fleet-wide, 11 counties
-- have propertyonion-originated rows with tier1_authoritative=true (broward=4,
-- charlotte=5, citrus=1, duval=5, hillsborough=1, indian_river=3, manatee=5,
-- palm_beach=18, pinellas=3, st_johns=1, volusia=8) that must be PRESERVED, not
-- excluded. seminole (this shard's actual target) has ZERO propertyonion rows with
-- tier1_authoritative=true (0 of 586) -- the refined filter still correctly
-- excludes all 586 contaminated seminole rows; seminole's C/D/E/I fix is unaffected
-- by this correction.
--
-- FIX: change the exclusion condition everywhere from
--   COALESCE(data_source,'') <> 'propertyonion'
-- to
--   (COALESCE(data_source,'') <> 'propertyonion' OR COALESCE(tier1_authoritative,false) = true)
-- in both pencil_dod_evaluate_county() and gold_standard_loop(). No other logic
-- changed in either function.

-- ============================================================
-- 1) pencil_dod_evaluate_county() -- correct commit 3b078a98's blanket filter
-- ============================================================
CREATE OR REPLACE FUNCTION public.pencil_dod_evaluate_county(p_county text)
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
         count(*) FILTER (WHERE parity_status='matched_clean') AS matched_clean,
         count(*) FILTER (WHERE parity_status IN ('matched_clean','matched_divergent')) AS matched_any,
         count(*) FILTER (WHERE tier1_sold_amount IS NOT NULL) AS tier1_sold,
         max(GREATEST(
           COALESCE(last_changed_at, '-infinity'::timestamptz),
           COALESCE(last_seen_at,    '-infinity'::timestamptz),
           COALESCE(scraped_at,      '-infinity'::timestamptz),
           COALESCE(scrape_timestamp,'-infinity'::timestamptz),
           COALESCE(created_at,      '-infinity'::timestamptz)
         )) AS last_seen
  FROM multi_county_auctions
  WHERE lower(county) = %1$L AND (COALESCE(data_source,'') <> 'propertyonion' OR COALESCE(tier1_authoritative,false) = true)
), o AS (
  SELECT count(*) AS verified_outcomes
  FROM multi_county_auctions a3
  WHERE lower(a3.county) = %1$L AND (COALESCE(a3.data_source,'') <> 'propertyonion' OR COALESCE(a3.tier1_authoritative,false) = true)
    AND a3.sold_amount IS NOT NULL
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
  SELECT DISTINCT parcel_id
  FROM v_zoning_gold_standard_card
  WHERE lower(county) = norm_county_key(%1$L) AND zone_code IS NOT NULL
), c AS (
  SELECT count(*) AS card_rows,
         count(*) FILTER (WHERE a2.property_address IS NOT NULL
            AND COALESCE(a2.latitude, a2.po_latitude::double precision) IS NOT NULL
            AND COALESCE(a2.longitude, a2.po_longitude::double precision) IS NOT NULL
            AND COALESCE(a2.assessed_value, a2.market_value) IS NOT NULL
            AND a2.parcel_id IN (SELECT parcel_id FROM zc)) AS card_complete
  FROM multi_county_auctions a2
  WHERE lower(a2.county) = %1$L AND (COALESCE(a2.data_source,'') <> 'propertyonion' OR COALESCE(a2.tier1_authoritative,false) = true)
), d AS (
  SELECT count(*) FILTER (WHERE EXISTS (
           SELECT 1 FROM bid_decisions bd
            WHERE bd.case_number=mca.case_number AND bd.arv IS NOT NULL AND bd.max_bid IS NOT NULL
              AND bd.ml_score IS NOT NULL
              AND bd.factors ? 'distress_location' AND bd.factors ? 'distress_property' AND bd.factors ? 'distress_owner'
              AND bd.factors ? 'cma_distressed' AND bd.factors ? 'cma_resale')) AS deal_complete
  FROM multi_county_auctions mca
  WHERE lower(mca.county) = %1$L AND (COALESCE(mca.data_source,'') <> 'propertyonion' OR COALESCE(mca.tier1_authoritative,false) = true)
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
$q$, v_lc) INTO v_out;
  RETURN v_out;
END;
$function$;

-- ============================================================
-- 2) gold_standard_loop() -- correct this session's own blanket filter
-- ============================================================
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
    'architecture', 'v9_5_tier1_authoritative_preserved');
END
$function$;
