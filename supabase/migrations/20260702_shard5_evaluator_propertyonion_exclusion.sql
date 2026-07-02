-- SHARD-5: Exclude data_source='propertyonion' rows from pencil_dod_evaluate_county
-- dispatch_id: a93a3cc9-e924-47bf-a82b-5f9a4d0afde9
-- Session: architect-20260702T000000 (gold standard shard-5: hillsborough, jackson, lee)
--
-- ROOT CAUSE (VERIFIED live 2026-07-02 via REST queries against multi_county_auctions):
--   HARD GUARDRAIL #1 states "PropertyOnion = litmus ONLY. Never ingest as a data source."
--   Despite this, 63,463 of 79,406 fleet-wide multi_county_auctions rows (80%) carry
--   data_source='propertyonion' with synthetic case_number ('PO-xxxxxx'), no parcel_id,
--   is_operational=false, parity_scope='archive_no_source_truth'. pencil_dod_evaluate_county
--   never filtered these out — every denominator (auctions_total, card_rows) counts them.
--
--   hillsborough: 5,182 propertyonion rows bulk-inserted 2026-07-01 (created_at), AFTER its
--   gold_standard_cert_scope certification snapshot (2026-06-24). This blew auctions_total
--   from ~555 (real) to 6,091, collapsing C/D/E/I/J from a passing state to ~14-15%.
--   lee: 2,818 propertyonion rows, same pattern (273 real vs 3,070 total).
--   jackson: 0 propertyonion rows — unaffected, evaluator numbers already accurate.
--
-- RACE CONDITION NOTE: this function was applied live once already (~00:16Z), verified,
-- then a CONCURRENT shard session overwrote it with a B-criterion reconciliation fix
-- (bridges verified_outcomes to actual multi_county_auctions rows by case_number + sold_amount
-- IS NOT NULL, and caps B's pass condition to the 95-105% band per EVALUATOR V6 RULES) before
-- this migration could be committed. This version MERGES both fixes: the concurrent
-- session's bridged/banded B logic (o CTE) is preserved verbatim, plus the propertyonion
-- exclusion is added to CTEs a/c/d (and o, for consistency, though propertyonion rows never
-- carry sold_amount so it is a no-op there — verified: duval=1, brevard=0 of thousands).
--
-- FIX: add `AND COALESCE(data_source,'') <> 'propertyonion'` to every multi_county_auctions
-- scan. All other logic (H GREATEST fix, I card-completeness definition, county-key
-- normalization, and the concurrent session's B bridge/band) preserved verbatim.

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
  WHERE lower(county) = %1$L AND COALESCE(data_source,'') <> 'propertyonion'
), o AS (
  SELECT count(*) AS verified_outcomes
  FROM multi_county_auctions a3
  WHERE lower(a3.county) = %1$L AND COALESCE(a3.data_source,'') <> 'propertyonion'
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
  WHERE lower(a2.county) = %1$L AND COALESCE(a2.data_source,'') <> 'propertyonion'
), d AS (
  SELECT count(*) FILTER (WHERE EXISTS (
           SELECT 1 FROM bid_decisions bd
            WHERE bd.case_number=mca.case_number AND bd.arv IS NOT NULL AND bd.max_bid IS NOT NULL
              AND bd.ml_score IS NOT NULL
              AND bd.factors ? 'distress_location' AND bd.factors ? 'distress_property' AND bd.factors ? 'distress_owner'
              AND bd.factors ? 'cma_distressed' AND bd.factors ? 'cma_resale')) AS deal_complete
  FROM multi_county_auctions mca
  WHERE lower(mca.county) = %1$L AND COALESCE(mca.data_source,'') <> 'propertyonion'
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
