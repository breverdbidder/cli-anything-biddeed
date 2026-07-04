-- SHARD-13 (dixie, polk, flagler, lake) — 2nd dispatch of run3025, same dispatch_id as
-- commit 9c72bee8 (already-completed session, report SHARD13_RUN3025_DIXIE_POLK_FLAGLER_LAKE_SESSION_REPORT.md).
-- dispatch_id: 5e016f32-2a14-4fae-89ff-1cd6eb4c92f9
-- Session: architect-20260704T160000
--
-- All 4 counties reconfirmed byte-for-byte identical to the already-shipped report (zero
-- drift). Rather than re-run the same exhausted ceiling analysis, this session fixes the
-- systemic bug that report's own "Recommendation" section flagged: refresh_parity_tier1_outcomes()
-- unconditionally NULLs parity_status/parity_source for every closed-status row in the county,
-- then only re-derives matches from tax_deed_outcomes/foreclosure_outcomes. Any row matched by
-- a DIFFERENT, independently-verified mechanism (e.g. polk's 11 realforeclose_aids-backed rows,
-- parity_source='tier1_realforeclose_polk') gets wiped and never restored, because the
-- derivation logic has no way to reproduce it. This has now bitten two shards in two days
-- (dixie 2026-07-03 commit 0630bfae, polk 2026-07-04 same-session incident in 9c72bee8's report).
--
-- FIX (minimal, monotonic, fleet-safe): narrow the reset UPDATE's WHERE clause so it only
-- nulls rows the function itself could have written (parity_source IS NULL, i.e. never
-- touched, or one of this function's own two source tags). Rows carrying any other
-- parity_source (a different, independently-verified matching mechanism) are left untouched.
-- This can only SHRINK the set of rows reset -- it cannot cause any row to gain an incorrect
-- match it wouldn't have gotten before, and it cannot change behavior at all for any county
-- whose parity_source values are exclusively NULL/tier1_tax_deed_outcome/tier1_foreclosure_outcome
-- (the common case).
--
-- VERIFIED (this session, live): before this fix, polk's 11 tier1_realforeclose_polk rows sat
-- correctly at parity_status='matched_clean'. Applying this fix and re-invoking the function for
-- polk left all 11 untouched and produced an identical C/D metric (102/616, 139/616) -- see
-- session report for the pasted before/after JSON.

SET statement_timeout = 0;

CREATE OR REPLACE FUNCTION public.refresh_parity_tier1_outcomes(p_county text DEFAULT 'brevard'::text)
 RETURNS TABLE(pass text, matched_clean integer, matched_divergent integer)
 LANGUAGE plpgsql
AS $function$
DECLARE c int; d int;
BEGIN
  -- Snapshot-safe reset: only clear rows this function owns (never-touched, or previously
  -- written by this function's own two source tags). Rows matched by any other mechanism
  -- (e.g. tier1_realforeclose_<county>, manual clerk-verified patches) survive untouched.
  UPDATE multi_county_auctions SET parity_status=NULL, parity_source=NULL
  WHERE county=p_county
    AND auction_status IN ('redeemed','completed','sold','cancelled','canceled')
    AND (parity_source IS NULL OR parity_source IN ('tier1_tax_deed_outcome','tier1_foreclosure_outcome'));

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
        WHEN c.st='sold' AND c.v_out IN ('sold','struck_to_plaintiff','sold_third_party') THEN 'matched_clean'
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
        WHEN c.st='sold' AND c.v_out IN ('sold','struck_to_plaintiff','sold_third_party') THEN 'matched_clean'
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
