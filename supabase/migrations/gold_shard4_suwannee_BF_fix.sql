-- GOLD STANDARD shard-4 suwannee-only, keys suwannee-B and suwannee-F.
--
-- ROOT CAUSE (confirmed this session): pencil_dod_evaluate_county's B (verified_outcomes)
-- and F (tier1_sold) metrics both key off multi_county_auctions.sold_amount IS NOT NULL to
-- define "closed_sold" (the denominator). For suwannee, 10 of 35 rows had passed their
-- auction_date and carried a closed auction_status (4 completed: 4712/4710/4784/4711,
-- 6 redeemed: 4709/4666/4667/4713/4706/4707), but ALL 35 rows had sold_amount = NULL,
-- making closed_sold = 0 and both B and F metrics unmeasurable (metric: null, not a real
-- fail-with-signal).
--
-- Of the 10 closed rows, the 4 "completed" tax_deed rows (4712, 4710, 4784, 4711) already
-- carried a real, tier1-verified sale price in tier1_sold_amount ($78,900 / $87,600 /
-- $45,100 / $10,000 respectively) that had simply never been copied to the canonical
-- sold_amount column. The 6 "redeemed" rows have no tier1_sold_amount at all (redemptions
-- don't produce a sale price) and are correctly left untouched.
--
-- FIX SOURCE: no new scraping needed -- this is a same-column promotion using data already
-- ingested and tier1-verified in this DB. Confirmed via cross-county pattern check
-- (levy/wakulla/dixie/gulf, all comparable small tax-deed counties): in every row across
-- those counties where sold_amount IS NOT NULL, it is always exactly equal to
-- tier1_sold_amount (1:1 copy, e.g. gulf 'completed' status = 9/9 rows matching). Suwannee's
-- 4 completed rows are the identical shape (completed status + populated tier1_sold_amount)
-- just missing that copy step, confirming this is a genuine backfill gap, not a fabrication.
--
-- Verified via pencil_dod_evaluate_county('suwannee'):
--   BEFORE: B {pass:false, detail:"verified=0 closed_sold=0", metric:null}
--           F {pass:false, detail:"tier1_sold=0 closed_sold=0", metric:null}
--   AFTER:  B {pass:false, detail:"verified=0 closed_sold=4",  metric:0.0}   -- now measurable, still correctly failing (tax_deed_outcomes/foreclosure_outcomes have 0 rows for suwannee -- out of scope for this fix, needs a verification/backfill pipeline)
--           F {pass:true,  detail:"tier1_sold=4 closed_sold=4", metric:100.0} -- PASS
-- No regression on A/C/D/E/G/H/I/J (unchanged before/after).

UPDATE public.multi_county_auctions
SET sold_amount = tier1_sold_amount
WHERE county = 'suwannee'
  AND sold_amount IS NULL
  AND tier1_sold_amount IS NOT NULL;
