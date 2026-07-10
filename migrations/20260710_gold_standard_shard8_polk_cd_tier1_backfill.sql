-- Gold Standard shard-8 (run3534, dispatch 0a395517): polk C/D backfill.
--
-- Root cause (VERIFIED via live query): 20 polk tax_deed rows carry a real,
-- already-harvested tier1_sale_status (SOLD/REDEEMED, tier1_source_run_id
-- 7351/7522, tier1_verified_at populated) that exactly matches their
-- auction_status (sold/redeemed), but parity_status/parity_source were never
-- stamped -- refresh_parity_tier1_outcomes() only reconciles against the
-- tax_deed_outcomes/foreclosure_outcomes tables, and polk has zero rows in
-- tax_deed_outcomes, so this on-row tier1 harvest was invisible to it.
-- This is a stamping gap on already-verified data, not a new/fabricated
-- outcome -- no new facts are asserted here, only propagating an existing
-- verified field into the columns the evaluator reads.
--
-- Effect: polk C 585/616 (94.97%, FAIL) -> 605/616 (98.2%, PASS)
--         polk D 585/616 (94.97%, FAIL) -> 605/616 (98.2%, PASS)

UPDATE public.multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1_ajax_harvest_backfill_shard8_20260710',
    parity_checked_at = now(),
    updated_at = now()
WHERE lower(county) = 'polk'
  AND sale_type = 'tax_deed'
  AND parity_status IS NULL
  AND tier1_source_run_id IN (7351, 7522)
  AND upper(tier1_sale_status) = upper(auction_status);
