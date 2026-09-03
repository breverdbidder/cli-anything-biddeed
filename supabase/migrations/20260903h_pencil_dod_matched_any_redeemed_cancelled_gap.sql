-- ARCHITECT TRIAGE (issue #19798, diagnosing blocked #19773): pencil_dod_evaluate_county
-- letter D missing REALTDM_REDEEMED / REALTDM_CANCELLED from the matched_any allow-list.
-- dispatch_id: c95b007e-1258-4f82-9c9b-a3cc51fdec7c
--
-- PROBLEM (VERIFIED live 2026-09-03 via Management API): the issue #19773 shard session
-- (run 33731083915, docs/spec/19773.md) found seminole D stuck at 79.6% with 10 rows carrying
-- parity_status='REALTDM_REDEEMED' counted against it, and explicitly flagged this as "an
-- evaluator gap, not a data gap" requiring an architect-level function change, out of scope for
-- a per-county data-fix session. Independently confirmed: the matched_any FILTER already
-- accepts CLERK_SSOT_CANCELLED (a clerk-side confirmed-cancelled sale — no parity data is
-- possible because the sale never happened, so canon treats it as an accepted terminal state
-- for D, same as it already excludes cancelled sales from the stricter C bar). REALTDM_REDEEMED
-- (RealTaxDeed-platform redemption: certificate holder paid off before the sale proceeded) and
-- REALTDM_CANCELLED are the exact same terminal-state class from the RealTaxDeed lane, just
-- never wired into the allow-list -- an omission, not an intentional exclusion (confirmed by
-- grepping the live function body: zero occurrences of either string before this migration).
--
-- FIX: add REALTDM_REDEEMED and REALTDM_CANCELLED to the matched_any allow-list only. C
-- (matched_clean) is intentionally left untouched -- a redeemed/cancelled sale still can never
-- be a genuine litmus match, exactly as already established for CLERK_SSOT_CANCELLED. No other
-- logic changed (verbatim copy of the live function otherwise).
--
-- BLAST RADIUS CHECKED BEFORE SHIPPING (live query, whole fleet, old vs new D):
--   brevard:    94.7% FAIL -> 95.4% PASS  (flips)      -- 49 REALTDM_REDEEMED rows
--   lee:        72.8% FAIL -> 91.0% FAIL  (no flip)    -- 124 REALTDM_REDEEMED rows (this shard)
--   santa_rosa: 35.8% FAIL -> 46.3% FAIL  (no flip)    -- 28 REALTDM_REDEEMED rows
--   sarasota:   68.5% FAIL -> 90.4% FAIL  (no flip)    -- 84 REALTDM_REDEEMED + 3 REALTDM_CANCELLED
--   seminole:   79.6% FAIL -> 84.7% FAIL  (no flip)    -- 10 REALTDM_REDEEMED rows (this shard)
-- All 5 affected counties' rows verified sold_amount IS NULL and tier1_sold_amount effectively
-- NULL for these statuses (0/295 REALTDM_REDEEMED and 0/3 REALTDM_CANCELLED rows carry
-- sold_amount) -- B and F are structurally unaffected, C is unchanged by design. No county
-- outside this list is touched. brevard is not in this shard but its flip is an honest
-- correction (real evaluator bug fixed), not a ghost-success -- same class as the 20260702
-- shard-1 C/D tier1-filter migration which also surfaced/flipped counties outside its shard.

CREATE OR REPLACE FUNCTION public.pencil_dod_evaluate_county(p_county text, p_snapshot_at timestamp with time zone DEFAULT NULL::timestamp with time zone)
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public', 'biddeed', 'graphql', 'extensions', 'vault', 'cron', 'net', 'http', 'storage', 'auth'
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
         count(*) FILTER (WHERE (parity_status='matched_clean' AND parity_source LIKE 'tier1%%')
                             OR parity_status IN ('PARITY_OK','CLERK_VERIFIED')) AS matched_clean,
         count(*) FILTER (WHERE (parity_status IN ('matched_clean','matched_divergent') AND parity_source LIKE 'tier1%%')
                             OR parity_status IN ('PARITY_OK','CLERK_VERIFIED','CLERK_SSOT_CANCELLED','REALTDM_REDEEMED','REALTDM_CANCELLED')) AS matched_any,
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
    AND (%2$L::timestamptz IS NULL
         OR COALESCE(created_at, scraped_at, scrape_timestamp, now()) <= %2$L::timestamptz)
), o AS (
  SELECT count(*) AS verified_outcomes
  FROM multi_county_auctions a3
  WHERE lower(a3.county) = %1$L AND (COALESCE(a3.data_source,'') <> 'propertyonion' OR COALESCE(a3.tier1_authoritative,false) = true)
    AND a3.sold_amount IS NOT NULL
    AND (%2$L::timestamptz IS NULL
         OR COALESCE(a3.created_at, a3.scraped_at, a3.scrape_timestamp, now()) <= %2$L::timestamptz)
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
    AND (%2$L::timestamptz IS NULL
         OR COALESCE(a2.created_at, a2.scraped_at, a2.scrape_timestamp, now()) <= %2$L::timestamptz)
), d AS (
  SELECT count(*) FILTER (WHERE EXISTS (
           SELECT 1 FROM bid_decisions bd
            WHERE bd.case_number=mca.case_number AND bd.arv IS NOT NULL AND bd.max_bid IS NOT NULL
              AND bd.ml_score IS NOT NULL
              AND bd.factors ? 'distress_location' AND bd.factors ? 'distress_property' AND bd.factors ? 'distress_owner'
              AND bd.factors ? 'cma_distressed' AND bd.factors ? 'cma_resale')) AS deal_complete
  FROM multi_county_auctions mca
  WHERE lower(mca.county) = %1$L AND (COALESCE(mca.data_source,'') <> 'propertyonion' OR COALESCE(mca.tier1_authoritative,false) = true)
    AND (%2$L::timestamptz IS NULL
         OR COALESCE(mca.created_at, mca.scraped_at, mca.scrape_timestamp, now()) <= %2$L::timestamptz)
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
$q$, v_lc, p_snapshot_at) INTO v_out;

  -- C/D LITMUS V2 (issue #10981): additive-only surface, zero effect on A-J pass/fail.
  v_out := v_out || jsonb_build_object('V2_LITMUS', public.cd_litmus_v2_snapshot(v_lc));

  RETURN v_out;
END;
$function$;
