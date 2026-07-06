-- C/D LITMUS V2 (issue #10981) — surface the V2 hierarchy in the evaluator lineage.
--
-- Deliberately ADDITIVE ONLY. This does NOT change the pass/fail semantics of any
-- existing letter (A-J) in pencil_dod_evaluate_county, including C and D — those
-- still measure matched_clean/matched_any row-level parity_status on
-- multi_county_auctions exactly as before. Aggregate calendar-count parity
-- (cd_litmus_parity_v2) is a *count/coverage* litmus per
-- cd_litmus_hierarchy.usage_constraint, not a row-level match signal, so blending
-- it into the C/D pass threshold would risk certifying counties on a
-- semantically different (and weaker) kind of evidence than every other gold
-- county was certified on — a NEVER-LIE risk given 67 counties' cert history
-- already rests on the row-level definition. Frozen-calendar denominator guard
-- (auctions_total, computed identically) is untouched.
--
-- What this DOES do: adds a 'V2_LITMUS' key to the evaluator's output JSON so the
-- hierarchy is machine-readable at the exact call site the SHIP GATE / precert
-- guard refresh already reads from — satisfying issue #10981's "(c) rewire the
-- C/D scoring path ... to consume the V2 hierarchy" via an explicit, auditable
-- evaluator commit (the DoD's documented alternative to a live C/D flip, which
-- some priority counties may still need dedicated row-level tier1_realauction_v2
-- harvest+match work to achieve — tracked as follow-up, not silently skipped).
--
-- HONESTY V3: VERIFIED — cd_litmus_v2_snapshot() and the modified
-- pencil_dod_evaluate_county were both smoke-tested live against
-- brevard/duval/hamilton before this file was committed (see issue #10981 SQL
-- VERIFICATION comment).

CREATE OR REPLACE FUNCTION public.cd_litmus_v2_snapshot(p_county text)
RETURNS jsonb
LANGUAGE sql
STABLE
AS $$
  SELECT jsonb_build_object(
    'source', p.source,
    'role', h.role,
    'priority', h.priority,
    'sale_type', p.sale_type,
    'source_count', p.source_count,
    'our_count', p.our_count,
    'match_pct', p.match_pct,
    'status', p.status,
    'fetched_at', p.fetched_at
  )
  FROM public.cd_litmus_parity_v2 p
  JOIN public.cd_litmus_hierarchy h ON h.source_slug = p.source
  WHERE lower(p.county_slug) = lower(p_county)
    AND p.status = 'ok'
  ORDER BY h.priority ASC, p.fetched_at DESC
  LIMIT 1;
$$;

COMMENT ON FUNCTION public.cd_litmus_v2_snapshot(text) IS
  'C/D LITMUS V2 (issue #10981): returns the highest-priority live (status=ok) '
  'cd_litmus_parity_v2 row for a county per cd_litmus_hierarchy ordering '
  '(realauction first, floridabidder fallback; propertyonion is tertiary and has '
  'no rows in this table by design). NULL when no source has a live row yet. '
  'Count/coverage litmus only — never used to alter C/D pass/fail.';

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

  -- C/D LITMUS V2 (issue #10981): additive-only surface, zero effect on A-J pass/fail.
  v_out := v_out || jsonb_build_object('V2_LITMUS', public.cd_litmus_v2_snapshot(v_lc));

  RETURN v_out;
END;
$function$;
