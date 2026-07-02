-- SHARD-1: Fix pencil_dod_evaluate_county letters C/D — missing tier1 parity_source filter
-- dispatch_id: 2c84de43-6561-42d3-b75d-ddbc4b04c305
-- Session: architect-20260702T080000 (gold standard shard-1: bradford, citrus, escambia)
--
-- PROBLEM (VERIFIED live 2026-07-02 via Management API): pencil_dod_evaluate_county's C/D
-- FILTER clauses counted `parity_status IN ('matched_clean','matched_divergent')` with no
-- requirement that the match came from an independent tier1 source. gold_standard_loop() (the
-- canonical scorer that feeds gold_standard_county_status/certification) already requires
-- `parity_source LIKE 'tier1%' in addition to parity_status — this divergence is the same
-- unscoped-numerator defect class already fixed for B (commit 6e5b42d5) and F (commits
-- d4dfc12c, dd92d641) today, just never applied to C/D.
--
-- This caused the per-county verification RPC (the tool sessions are instructed to use per
-- PARALLEL-FLEET RULES: "Do not run gold_standard_loop() mid-session... use
-- pencil_dod_evaluate_county per county") to ghost-pass C/D for counties whose parity_status
-- was set by non-independent processes (e.g. parcel-ID linkage scripts) rather than genuine
-- comparison against an independent litmus source. Two shard sessions today (7498c45a "citrus
-- I fix... bradford+escambia already 10/10", and the shard-10 escambia PropertyOnion cleanup
-- migration's own before/after note) both cited this RPC and both falsely reported escambia
-- C/D as 98.5%/98.5% PASS. The canonical gold_standard_county_status table shows escambia C/D
-- at a literal 0.0% FAIL continuously since at least 2026-07-01T10:21Z (loop_run 2210) through
-- the present (loop_run 2417, 2026-07-02T11:00Z) — escambia's 262 "matched_clean" rows all
-- carry parity_source='official_parcel_linkage_shard2' (E-criterion parcel linkage, not a real
-- C/D litmus comparison), so they were never real matches under canon.
--
-- BLAST RADIUS CHECKED BEFORE SHIPPING (live query, whole fleet, old vs new C/D pass/fail):
-- exactly 6 counties flip from ghost-PASS to honest-FAIL under the corrected formula:
--   escambia:    C/D 98.5%/98.5% (PASS) -> 0.0%/0.0%   (FAIL) -- matched_clean was all E-linkage, not litmus
--   hernando:    C/D 100.0%/100.0% (PASS) -> 0.0%/0.0% (FAIL)
--   lee:         C/D 100.0%/100.0% (PASS) -> 2.0%/2.0% (FAIL)
--   palm_beach:  C/D 99.1%/99.1% (PASS) -> 92.8%/92.8% (FAIL, just under threshold)
--   pinellas:    C/D 98.9%/99.2% (PASS) -> 0.0%/0.0%   (FAIL)
--   volusia:     C/D 98.9%/98.9% (PASS) -> 78.2%/78.2% (FAIL)
-- None of these are this shard's assigned counties (bradford/citrus/escambia) except escambia,
-- whose real state this migration surfaces honestly rather than fixes -- real C/D work
-- (an independent litmus comparison, none currently exists for escambia) remains open.
-- bradford (100.0/100.0) and citrus (97.1/97.1) are UNCHANGED and remain honest PASS -- both
-- already carry genuine tier1_-prefixed parity_source values.
--
-- FIX: add `AND parity_source LIKE 'tier1%%'` to the matched_clean/matched_any FILTER clauses,
-- verbatim match to gold_standard_loop()'s existing C/D logic. No other logic changed.

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
  RETURN v_out;
END;
$function$
