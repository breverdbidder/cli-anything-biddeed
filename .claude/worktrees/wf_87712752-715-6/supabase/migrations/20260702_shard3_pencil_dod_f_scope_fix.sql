-- SHARD-3: Fix pencil_dod_evaluate_county letter F — unscoped tier1_sold numerator caused >100% anomalies
-- dispatch_id: 0f741fac-de31-4443-8215-e7643b931612
-- Session: architect-20260702T080000 (gold standard shard-3: duval, gadsden, manatee)
--
-- PROBLEM (VERIFIED live 2026-07-02 via Management API query): F counted
-- `count(*) FILTER (WHERE tier1_sold_amount IS NOT NULL)` with no requirement that the row is
-- actually closed_sold (sold_amount IS NOT NULL). This is the exact same defect class as the B
-- bug fixed earlier today in commit 6e5b42d5 (shard-3, 00:14:34Z) — an unscoped numerator that can
-- exceed its denominator. Live fleet-wide query found 13 counties with tier1_sold > closed_sold,
-- including duval (374 tier1_sold vs 55 closed_sold = 680.0%), brevard (934.6%), polk (2390.0%),
-- citrus (2733.3%), and pinellas (4400.0% — 132 tier1_sold rows vs only 3 closed_sold rows, ALL
-- 132 with sold_amount IS NULL, i.e. zero of pinellas's "tier1_sold" rows are actually closed).
--
-- FIX: require sold_amount IS NOT NULL in the tier1_sold FILTER, so the numerator is a subset of
-- closed_sold by construction (metric can never exceed 100 going forward) — same pattern already
-- applied to B. No other logic changed.
--
-- BLAST RADIUS CHECKED BEFORE SHIPPING (live query, all fleet counties): comparing old vs new F%
-- for every county, exactly ONE county flips from PASS to FAIL under the corrected formula:
--   pinellas: old F=4400.0% (PASS, ghost) -> new F=0.0% (FAIL, honest). Zero of pinellas's 132
--   tier1_sold_amount rows are actually closed_sold — its current F "pass" is entirely fake.
--   Pinellas is NOT in this shard's assigned counties (duval/gadsden/manatee); flagging here per
--   HARD GUARDRAILS/Honesty Protocol for whichever shard owns pinellas next. Not fixed in this
--   migration — out of scope for shard-3's PARALLEL-FLEET RULES county ownership.
-- This session's three target counties are UNAFFECTED in outcome (all remain honest 100% PASS):
--   duval:    old 680.0% (PASS) -> new 100.0% (PASS)  [55/55]
--   gadsden:  old 100.0% (PASS) -> new 100.0% (PASS)  [5/5]
--   manatee:  old 100.0% (PASS) -> new 100.0% (PASS)  [5/5]
--
-- Based on the latest live function body (commit 90688ffe, shard-13 tier1_authoritative
-- correction, 08:24:52Z today) — only the tier1_sold FILTER changes; the propertyonion/
-- tier1_authoritative exclusion logic added by that commit is preserved verbatim.

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
