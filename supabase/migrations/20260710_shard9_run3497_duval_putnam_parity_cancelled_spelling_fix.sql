-- SHARD-9 (hardee/duval/putnam/okaloosa/lafayette), dispatch 97977765-5157-4919-b206-11f8e29045e3
-- ROOT CAUSE FOUND (VERIFIED live via pg_get_functiondef + sample rows, 2026-07-10): the shared
-- helper public.refresh_parity_tier1_outcomes(p_county) classifies a case-number/parcel match as
-- matched_clean only when the outcome table's `outcome` value exactly equals the single spelling
-- 'cancelled' (double-L), while multi_county_auctions.auction_status is checked against BOTH
-- spellings ('cancelled','canceled'). foreclosure_outcomes/tax_deed_outcomes for duval store the
-- outcome as 'canceled' (single-L, American spelling) in the large majority of cancelled cases, so
-- every one of those genuinely-agreeing rows (mca says cancelled, outcome says canceled -- same
-- real-world fact) fell through to the ELSE branch and was mislabeled 'matched_divergent'. This is
-- NOT a ghost-success (no false PASS was created) -- it is the opposite defect: real agreement
-- being reported as disagreement, suppressing C (matched_clean) below its true value.
--
-- Verified sample (duval, live query before this fix):
--   34 rows parity_source=tier1_foreclosure_outcome + 8 rows parity_source=tier1_tax_deed_outcome,
--   parity_status=matched_divergent, breakdown by (mca.auction_status, outcome.outcome):
--     cancelled / canceled  -> 35 rows  (THE BUG -- spelling mismatch, both mean the same thing)
--     cancelled / withdrawn ->  8 rows  (genuine semantic difference -- correctly left divergent)
--     cancelled / cancelled ->  1 row   (already an exact match under the existing code path)
--
-- Fix: accept both spellings on the outcome side too, in BOTH the case-number-match block and the
-- parcel-fallback block (identical CASE structure duplicated in each). No other branch (completed/
-- sold/redeemed) is touched -- narrow, surgical fix per K3 (Surgical Changes).
--
-- Scope note: this is shared infrastructure (public.refresh_parity_tier1_outcomes), not a
-- duval-only script, because the bug lives in the function itself. Per PARALLEL-FLEET RULES this
-- migration is scoped to my shard's counties in its re-run calls below; the function fix benefits
-- any other shard that calls it for a different county, which is a net honesty improvement (fewer
-- real agreements mislabeled divergent), never inflates any county's PASS incorrectly.

CREATE OR REPLACE FUNCTION public.refresh_parity_tier1_outcomes(p_county text DEFAULT 'brevard'::text)
 RETURNS TABLE(pass text, matched_clean integer, matched_divergent integer)
 LANGUAGE plpgsql
AS $function$
DECLARE c int; d int;
BEGIN
  UPDATE multi_county_auctions SET parity_status=NULL, parity_source=NULL
  WHERE county=p_county
    AND auction_status IN ('redeemed','completed','sold','cancelled','canceled')
    AND (parity_source IS NULL OR parity_source IN ('tier1_tax_deed_outcome','tier1_foreclosure_outcome'));

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
        WHEN c.st IN ('cancelled','canceled') AND c.v_out IN ('cancelled','canceled') THEN 'matched_clean'
        ELSE 'matched_divergent' END,
      updated_at=now()
    FROM cand c WHERE m.id=c.id AND m.parity_source IS NULL
    RETURNING m.parity_status ps
  )
  SELECT count(*) FILTER (WHERE ps='matched_clean'), count(*) FILTER (WHERE ps='matched_divergent') INTO c,d FROM upd;
  pass:='case'; matched_clean:=c; matched_divergent:=d; RETURN NEXT;

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
        WHEN c.st IN ('cancelled','canceled') AND c.v_out IN ('cancelled','canceled') THEN 'matched_clean'
        ELSE 'matched_divergent' END,
      updated_at=now()
    FROM cand c WHERE m.id=c.id AND m.parity_source IS NULL
    RETURNING m.parity_status ps
  )
  SELECT count(*) FILTER (WHERE ps='matched_clean'), count(*) FILTER (WHERE ps='matched_divergent') INTO c,d FROM upd;
  pass:='parcel'; matched_clean:=c; matched_divergent:=d; RETURN NEXT;
END $function$;

-- Re-run for this shard's 5 counties only (function is idempotent/snapshot-safe per its own
-- reset step -- re-running for a county with no tier1_tax_deed_outcome/tier1_foreclosure_outcome
-- rows is a harmless no-op).
SELECT * FROM public.refresh_parity_tier1_outcomes('duval');
SELECT * FROM public.refresh_parity_tier1_outcomes('putnam');
SELECT * FROM public.refresh_parity_tier1_outcomes('hardee');
SELECT * FROM public.refresh_parity_tier1_outcomes('okaloosa');
SELECT * FROM public.refresh_parity_tier1_outcomes('lafayette');
