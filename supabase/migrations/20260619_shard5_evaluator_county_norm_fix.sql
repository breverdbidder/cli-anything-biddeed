-- SHARD-5 Evaluator Fix: pencil_dod_evaluate_county norm_county_key normalization
-- Session: architect-20260619T160001 / dispatch 3539afa8-7060-4672-b44f-efc496fd0b62
--
-- ROOT CAUSE (CONFIRMED 2026-06-19):
--   norm_county_key() translates underscores to spaces (translate('_','  ')).
--   So norm_county_key('santa_rosa') = 'santa rosa' (space, not underscore).
--   v_zoning_gold_standard_card and v_zoning_gold_standard_kpi_v3 use
--   norm_county_key() on jurisdiction.county_name, returning 'santa rosa'.
--   The evaluator uses `lower(county) = 'santa_rosa'` (slug with underscore).
--   Result: G and I always returned 0 for multi-word county slugs like
--   santa_rosa, palm_beach, miami_dade, etc.
--
-- FIX:
--   z  CTE: WHERE lower(county) = norm_county_key(%1$L)   [was: = %1$L]
--   zc CTE: WHERE lower(county) = norm_county_key(%1$L)   [was: = %1$L]
--
-- BACKWARD-COMPATIBLE CHECK:
--   Single-word slugs (brevard, duval, gilchrist, gulf) → norm_county_key returns same
--   Multi-word slugs (santa_rosa, palm_beach) → now match card/kpi_v3 'santa rosa' output
--
-- VERIFIED: gilchrist G=100% I=100%, santa_rosa G=100% I=100%, palm_beach G=100% I=99.2%
--           Brevard sanity check: G/I same as before (unaffected).
--
-- HONESTY: This fix does NOT change what data is in the DB. It only fixes the county
-- key normalization so that the evaluator correctly finds existing parcel_zones data.

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
         max(COALESCE(last_changed_at,last_seen_at,scraped_at,scrape_timestamp,created_at)) AS last_seen
  FROM multi_county_auctions WHERE lower(county) = %1$L
), o AS (
  SELECT (SELECT count(*) FROM tax_deed_outcomes
           WHERE lower(county) = %1$L AND COALESCE(data_source,'') NOT ILIKE '%%promote%%')
       + (SELECT count(*) FROM foreclosure_outcomes
           WHERE lower(county) = %1$L AND COALESCE(data_source,'') NOT ILIKE '%%promote%%') AS verified_outcomes
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
  FROM multi_county_auctions a2 WHERE lower(a2.county) = %1$L
), d AS (
  SELECT count(*) FILTER (WHERE EXISTS (
           SELECT 1 FROM bid_decisions bd
            WHERE bd.case_number=mca.case_number AND bd.arv IS NOT NULL AND bd.max_bid IS NOT NULL
              AND bd.ml_score IS NOT NULL
              AND bd.factors ? 'distress_location' AND bd.factors ? 'distress_property' AND bd.factors ? 'distress_owner'
              AND bd.factors ? 'cma_distressed' AND bd.factors ? 'cma_resale')) AS deal_complete
  FROM multi_county_auctions mca WHERE lower(mca.county) = %1$L
)
SELECT jsonb_build_object(
  'county', %1$L,
  'auctions_total', a.auctions_total,
  'A', jsonb_build_object('pass', COALESCE(a.foreclosure>0 AND a.tax_deed>0,false),
        'metric', LEAST(a.foreclosure,a.tax_deed),
        'detail', format('fc=%%s td=%%s', a.foreclosure, a.tax_deed)),
  'B', jsonb_build_object('pass', COALESCE(100.0*o.verified_outcomes/NULLIF(a.closed_sold,0) >= 95,false),
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
