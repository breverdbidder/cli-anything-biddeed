-- shard5 (architect-20260703T000000, dispatch 8cc7b73b): fix a real cross-linking bug in
-- refresh_parity_tier1_outcomes() found while investigating indian_river's C/D regression
-- (flagged but not fixed in commit 5c8958cb).
--
-- BUG (VERIFIED live against indian_river data): the function ran its PARCEL-ONLY join
-- (o.parcel_id = a.parcel_id, no case_number check) BEFORE its CASE-NUMBER join. When a
-- single parcel has multiple distinct case outcomes on file (e.g. two separate tax deed
-- sales on the same parcel in different years — confirmed on indian_river parcels
-- 313700000090 [cases 2025-0029TD / 2025-0036TD], 313918000014, 313929000005), the
-- parcel-only pass can claim a multi_county_auctions row using the WRONG case's outcome,
-- picked only by nearest auction_date, before the correct case-number match ever runs.
--
-- FIX: run the case-number match first (case_number equality is an unambiguous signal and
-- must win), then run the parcel-only fallback only for rows the case-number pass could not
-- resolve, and only against parcel_ids that have exactly one distinct case_number in the
-- outcome tables (added ambiguity guard) — an ambiguous parcel with multiple distinct cases
-- is no longer guessed at all by nearest-date heuristic.
--
-- IMPACT: re-ran for indian_river/palm_beach/monroe (this shard's counties with data) live.
-- matched_clean totals did not change in aggregate for any of the three (indian_river stayed
-- 46/77, palm_beach 510/688 [scoped total differs from raw due to legacy manual-fix rows
-- outside the tier1_tax_deed/foreclosure_outcome source pattern], monroe 3/25) — confirming
-- the residual C/D gap for all three is a genuine outcome-data coverage shortfall, not this
-- matching bug. This fix is shipped regardless because it prevents real case/outcome
-- mis-attribution (a correctness and honesty issue, not just a scoring one) for any county
-- with multiple distinct case outcomes sharing a parcel_id, fleet-wide, on every future call.
-- No other shard's already-stored parity_status values are touched by replacing this
-- function definition (values are only recomputed when the function is next invoked for a
-- given county).

CREATE OR REPLACE FUNCTION public.refresh_parity_tier1_outcomes(p_county text DEFAULT 'brevard'::text)
 RETURNS TABLE(pass text, matched_clean integer, matched_divergent integer)
 LANGUAGE plpgsql
AS $function$
DECLARE c int; d int;
BEGIN
  UPDATE multi_county_auctions SET parity_status=NULL, parity_source=NULL
  WHERE county=p_county
    AND auction_status IN ('redeemed','completed','sold','cancelled','canceled');

  -- CASE-NUMBER MATCH FIRST: unambiguous signal (case_number equality), must win
  -- over parcel-only matching. Otherwise a parcel with multiple distinct case
  -- outcomes (e.g. two separate tax deed sales on the same parcel in different
  -- years) lets the parcel-only pass cross-link a row to the WRONG case's
  -- outcome by nearest-date heuristic before the correct case-number match runs.
  WITH outc AS (
    SELECT 'tier1_tax_deed_outcome' src, case_number, lower(outcome) outcome, auction_date::date ad
      FROM tax_deed_outcomes WHERE lower(county)=p_county AND case_number IS NOT NULL
    UNION ALL
    SELECT 'tier1_foreclosure_outcome', case_number, lower(outcome), auction_date::date
      FROM foreclosure_outcomes WHERE lower(county)=p_county AND case_number IS NOT NULL
  ),
  cand AS (
    SELECT DISTINCT ON (a.id) a.id, a.auction_status st, o.outcome v_out, o.src
    FROM multi_county_auctions a
    JOIN outc o ON normalize_case_number(o.case_number)=normalize_case_number(a.case_number)
    WHERE a.county=p_county AND a.parity_source IS NULL
      AND a.auction_status IN ('redeemed','completed','sold','cancelled','canceled')
    ORDER BY a.id, abs((a.auction_date::date - o.ad)) NULLS LAST
  ),
  upd AS (
    UPDATE multi_county_auctions m SET parity_source=c.src,
      parity_status = CASE
        WHEN c.st='completed' THEN 'matched_clean'
        WHEN c.st='sold' AND c.v_out IN ('sold','struck_to_plaintiff') THEN 'matched_clean'
        WHEN c.st='redeemed' AND c.v_out='redeemed' THEN 'matched_clean'
        WHEN c.st IN ('cancelled','canceled') AND c.v_out='cancelled' THEN 'matched_clean'
        ELSE 'matched_divergent' END,
      updated_at=now()
    FROM cand c WHERE m.id=c.id AND m.parity_source IS NULL
    RETURNING m.parity_status ps
  )
  SELECT count(*) FILTER (WHERE ps='matched_clean'), count(*) FILTER (WHERE ps='matched_divergent') INTO c,d FROM upd;
  pass:='case'; matched_clean:=c; matched_divergent:=d; RETURN NEXT;

  -- PARCEL FALLBACK: only for rows the case-number pass couldn't resolve
  -- (our case_number doesn't normalize-match any outcome row). Ambiguity guard:
  -- skip parcel_ids with more than one distinct case_number in outc, since a
  -- nearest-date guess across genuinely different cases is not reliable enough
  -- to call matched_clean/matched_divergent with confidence.
  WITH outc AS (
    SELECT 'tier1_tax_deed_outcome' src, case_number, parcel_id, lower(outcome) outcome, auction_date::date ad
      FROM tax_deed_outcomes WHERE lower(county)=p_county AND parcel_id IS NOT NULL
    UNION ALL
    SELECT 'tier1_foreclosure_outcome', case_number, parcel_id, lower(outcome), auction_date::date
      FROM foreclosure_outcomes WHERE lower(county)=p_county AND parcel_id IS NOT NULL
  ),
  unambiguous_parcels AS (
    SELECT parcel_id FROM outc GROUP BY parcel_id HAVING count(DISTINCT case_number) = 1
  ),
  cand AS (
    SELECT DISTINCT ON (a.id) a.id, a.auction_status st, o.outcome v_out, o.src
    FROM multi_county_auctions a
    JOIN outc o ON o.parcel_id=a.parcel_id
    JOIN unambiguous_parcels up ON up.parcel_id = o.parcel_id
    WHERE a.county=p_county AND a.parity_source IS NULL
      AND a.auction_status IN ('redeemed','completed','sold','cancelled','canceled')
    ORDER BY a.id, abs((a.auction_date::date - o.ad)) NULLS LAST
  ),
  upd AS (
    UPDATE multi_county_auctions m SET parity_source=c.src,
      parity_status = CASE
        WHEN c.st='completed' THEN 'matched_clean'
        WHEN c.st='sold' AND c.v_out IN ('sold','struck_to_plaintiff') THEN 'matched_clean'
        WHEN c.st='redeemed' AND c.v_out='redeemed' THEN 'matched_clean'
        WHEN c.st IN ('cancelled','canceled') AND c.v_out='cancelled' THEN 'matched_clean'
        ELSE 'matched_divergent' END,
      updated_at=now()
    FROM cand c WHERE m.id=c.id AND m.parity_source IS NULL
    RETURNING m.parity_status ps
  )
  SELECT count(*) FILTER (WHERE ps='matched_clean'), count(*) FILTER (WHERE ps='matched_divergent') INTO c,d FROM upd;
  pass:='parcel'; matched_clean:=c; matched_divergent:=d; RETURN NEXT;
END $function$;
