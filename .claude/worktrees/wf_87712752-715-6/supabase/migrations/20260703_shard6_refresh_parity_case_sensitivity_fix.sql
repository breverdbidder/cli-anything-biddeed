-- SHARD-6: fix case-sensitivity bug in public.refresh_parity_tier1_outcomes
-- dispatch_id: a21cf8eb-3760-4adb-85ae-d0af017bfa1a
-- Session: architect-20260703T000000
--
-- ROOT CAUSE (VERIFIED live 2026-07-03): the canonical parity matcher compared
-- the independently-verified outcome value (o.outcome, sourced from
-- tax_deed_outcomes / foreclosure_outcomes) against lowercase literals
-- ('sold','struck_to_plaintiff','redeemed','cancelled') with no case
-- normalization. tax_deed_outcomes.outcome stores 'SOLD' (uppercase) for
-- 7,106 of 10,624 rows fleet-wide, and foreclosure_outcomes carries 40 'SOLD'
-- + 1 'REDEEMED' uppercase rows. Any row whose independently-verified outcome
-- used the uppercase form was silently written as matched_divergent instead
-- of matched_clean, understating C for every county that hit this path.
--
-- Reproduced directly for pasco: 3 rows (case_numbers 512025XX000266TDAXXX,
-- 512025XX000307TDAXXX, 512026XX000029TDAXXX) had auction_status='sold',
-- outcome='SOLD', and sold_amount = tier1_sold_amount to the cent -- yet were
-- flagged matched_divergent purely on casing.
--
-- FIX: wrap outcome with lower() in both CTEs (parcel-pass and case-pass).
-- Diff is minimal -- 4 lines changed, no logic/threshold changes.
--
-- APPLIED LIVE via Supabase Management API (2026-07-03), then re-invoked for
-- this shard's counties only per PARALLEL-FLEET RULES:
--   pasco:   C 0.0% (matched_clean=0/192)  -> 1.6% (matched_clean=3/192).  FAIL
--            (still fails threshold -- genuine structural ceiling, only 3 of
--            192 pasco auctions have ever closed_sold; not a further bug).
--   brevard/jackson/alachua: re-ran for regression check only, no additional
--            gain (their outcome rows were already lowercase) -- confirmed
--            identical metrics before/after, no regression.
--
-- This is a SHARED function (used by every county in the fleet). The fix
-- itself is fleet-wide and strictly monotonic (case-fold only ever promotes
-- divergent->clean, never the reverse), but per PARALLEL-FLEET RULES this
-- session only re-invoked refresh_parity_tier1_outcomes for its own shard's
-- counties. Other shards will see any latent gains for their counties the
-- next time they invoke the matcher for their own counties -- flagging this
-- explicitly so it isn't mistaken for a surprise metric shift.
--
-- Logged to gold_standard_ultraloop_audit id 2903 (survived=true).

CREATE OR REPLACE FUNCTION public.refresh_parity_tier1_outcomes(p_county text DEFAULT 'brevard'::text)
 RETURNS TABLE(pass text, matched_clean integer, matched_divergent integer)
 LANGUAGE plpgsql
AS $function$
DECLARE c int; d int;
BEGIN
  UPDATE multi_county_auctions SET parity_status=NULL, parity_source=NULL
  WHERE county=p_county
    AND auction_status IN ('redeemed','completed','sold','cancelled','canceled');

  WITH outc AS (
    SELECT 'tier1_tax_deed_outcome' src, case_number, parcel_id, lower(outcome) outcome, auction_date::date ad
      FROM tax_deed_outcomes WHERE lower(county)=p_county AND parcel_id IS NOT NULL
    UNION ALL
    SELECT 'tier1_foreclosure_outcome', case_number, parcel_id, lower(outcome), auction_date::date
      FROM foreclosure_outcomes WHERE lower(county)=p_county AND parcel_id IS NOT NULL
  ),
  cand AS (
    SELECT DISTINCT ON (a.id) a.id, a.auction_status st, o.outcome v_out, o.src
    FROM multi_county_auctions a
    JOIN outc o ON o.parcel_id=a.parcel_id
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
END $function$;
