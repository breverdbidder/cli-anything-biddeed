-- SHARD-3: Fix pencil_dod_evaluate_county letter B — unscoped outcome counts caused >100% anomalies
-- dispatch_id: 17ba48e3-ee35-4c22-bb16-fcc39c4648a7
-- Session: architect-20260702T000000
--
-- PROBLEM (VERIFIED live 2026-07-02, ULTRALOOP diagnose+adversarial-verify, both SURVIVED):
-- The `o` CTE counted ALL tax_deed_outcomes/foreclosure_outcomes rows for a county with no
-- join back to multi_county_auctions. For duval this summed 7005 tax_deed_outcomes (a bulk
-- historical import, data_source=flynn_winning_bids:SUMMIT-DUVAL-TXD-V1 spanning many years)
-- against closed_sold=55, producing B metric=13120.0% — a structural impossibility, not a
-- data quality issue. Per EVALUATOR V6 RULES ("B passes ONLY at 95-105%"), this also exposed
-- that the live function had no upper bound at all (COALESCE(...>=95,false) only).
--
-- FIX: Bound verified_outcomes to auctions that are actually closed_sold for this county AND
-- have a matching outcome row by case_number (mirrors the pattern already used for A/G's
-- county scoping and for F's closed_sold denominator). This makes the numerator a subset of
-- the denominator by construction, so metric can never exceed 100 going forward. Also adds
-- an explicit <=105 upper bound per ratified anomaly-band policy, as defense in depth.
--
-- Scope note: this is a SHARED evaluator function (affects every county's B letter, not just
-- duval/franklin/broward). Per PARALLEL-FLEET RULES this was rebased against latest main
-- before push. Any other shard relying on the old unscoped B behavior was relying on a bug —
-- CANON requires B to be a genuine independent-outcome verification ratio, not an unbounded
-- historical-import count.

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
  FROM multi_county_auctions WHERE lower(county) = %1$L
), o AS (
  SELECT count(*) AS verified_outcomes
  FROM multi_county_auctions a3
  WHERE lower(a3.county) = %1$L AND a3.sold_amount IS NOT NULL
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
