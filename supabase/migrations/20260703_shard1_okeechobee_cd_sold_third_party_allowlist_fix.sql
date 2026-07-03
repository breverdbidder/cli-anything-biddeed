-- SHARD-1 (brevard, flagler, okeechobee, miami_dade, gadsden): okeechobee C/D matcher-wiring fix
-- dispatch_id: 9dd1b96a-d052-4242-a4f2-b8012ce8e25c
-- Session: architect-20260703T080000
--
-- ROOT CAUSE (CONFIRMED live, adversarially verified via ultraloop diagnose+refute fan-out):
-- okeechobee cases 2026TD020/2026TD028/2026TD029 have real, already-ingested independent
-- clerk data in tax_deed_outcomes (data_source='okeechobee_taxsmartweb:SHARD4-OKEE-TD-V2',
-- outcome='sold_third_party', winning_bid EXACTLY equal to our own sold_amount: 23000/4500/5000).
-- A prior migration (20260702_shard4_okeechobee_taxsmartweb_bf_backfill.sql) intended to
-- correct these 3 rows' auction_status from the scraper's stale 'cancelled' label to 'sold'
-- but that UPDATE never actually executed against live data (auction_status is still
-- 'cancelled' today, confirmed via live query).
--
-- Applying just that status correction is NOT sufficient: refresh_parity_tier1_outcomes()'s
-- sold-branch CASE WHEN only treats v_out IN ('sold','struck_to_plaintiff') as matched_clean
-- for st='sold' -- it never absorbed 'sold_third_party' as a sold-equivalent outcome value,
-- even though 6 OTHER migrations in this repo already establish 'sold_third_party'/'third_party'
-- as sold-equivalent (20260619_shard7_seminole_gold_standard.sql, 20260623_duval_b_sold_amount_fix.sql,
-- 20260623_duval_b_f_outcome_pipeline.sql, 20260625_shard4_run581_gold_standard_v2.sql,
-- 20260702_shard4_okeechobee_taxsmartweb_bf_backfill.sql). This is a genuine, narrow wiring gap
-- in the canonical matcher, not a data problem -- confirmed by an independent adversarial
-- refuter agent that traced the exact missing allowlist value before this fix was written.
--
-- FIX (minimal, monotonic, fleet-safe): add 'sold_third_party' to the existing sold-branch
-- allowlist in BOTH the case-match and parcel-match passes of refresh_parity_tier1_outcomes.
-- This can only ADD matches (loosens a false->true condition for one specific outcome value);
-- it cannot downgrade any row that is currently matched_clean/matched_divergent for any county.
-- Then correct auction_status for the 3 okeechobee rows (documented-but-never-executed prior
-- intent) using only already-ingested data (no new/invented values), and re-run the matcher.
--
-- EXPECTED: okeechobee C 46.7% (14/30) -> 56.7% (17/30). STILL FAIL (needs >=95%). This closes
-- 3 of 16 gap rows; the remaining 13 (10 CA/CC civil cases with zero foreclosure_outcomes
-- coverage, blocked on a Civitek OCRS Cloudflare-Turnstile scraper build + 3 genuine
-- matched_divergent price-premium cases) require new data acquisition, not a SQL fix, and are
-- NOT attempted here (would repeat the ghost-success pattern already reverted twice for this
-- county per 20260702_shard4_okeechobee_bf_fabrication_revert.sql).

SET statement_timeout = 0;

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

-- Complete the auction_status correction that 20260702_shard4_okeechobee_taxsmartweb_bf_backfill.sql
-- already documented and intended but never executed (verified live: still 'cancelled' today).
-- Uses only already-ingested tax_deed_outcomes data (outcome='sold_third_party', winning_bid
-- exactly matching our own sold_amount) -- no new scrape, no invented values.
UPDATE multi_county_auctions
SET auction_status = 'sold',
    updated_at = now()
WHERE lower(county) = 'okeechobee'
  AND case_number IN ('2026TD020','2026TD028','2026TD029')
  AND auction_status = 'cancelled'
  AND sold_amount IS NOT NULL
  AND sold_amount_source = 'tax_deed_outcomes_sync';

-- Re-run the (now-fixed) matcher for okeechobee to reclassify the 3 rows.
SELECT * FROM public.refresh_parity_tier1_outcomes('okeechobee');

-- Verification
SELECT public.pencil_dod_evaluate_county('okeechobee');
