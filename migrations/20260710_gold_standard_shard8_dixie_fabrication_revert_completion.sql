-- Gold Standard shard-8 (run3534, dispatch 0a395517): completes the dixie
-- fabrication revert started by scripts/shard2_dixie_synth_revert.py
-- (issue #11373, committed ad943e9e but never executed until this session).
--
-- That script deleted the 21 fabricated tax_deed_outcomes rows
-- (data_source='shard6_clerk_independent:V1', winning_bid = assessed_value *
-- 0.65 formula placeholder, all sharing assessed_value=134615.38) but its
-- multi_county_auctions PATCH filter (parity_source='tier1_tax_deed_outcome')
-- matched ZERO rows -- the actual derivative-copy marker is
-- sold_amount_source='tax_deed_outcomes_sync', VERIFIED live: exactly the
-- same 21 case numbers, all sold_amount=87500.00 (=134615.38*0.65), still
-- present after the outcomes-table deletion. This left F ("tier1_sold=21
-- closed_sold=21", 100% PASS) resting on the same fabricated value the B/C/D
-- revert already discredited.
--
-- Action: clear the derivative fields on exactly those 21 rows. Does NOT
-- delete multi_county_auctions rows. Does NOT touch the 30 DIXIE-SYNTH-*
-- auction-listing rows themselves (out of scope per the original script,
-- flagged there as BLOCKED/deferred for a dedicated full-county revert).
--
-- Expected effect: F drops from 100% (tier1_sold=21 closed_sold=21) to
-- null/0% (closed_sold=0) -- an honest regression matching B's already-
-- reverted state, not a bug.

UPDATE public.multi_county_auctions
SET sold_amount = NULL,
    tier1_sold_amount = NULL,
    tier1_sale_status = NULL,
    sold_amount_source = NULL,
    sold_amount_captured_at = NULL,
    updated_at = now()
WHERE lower(county) = 'dixie'
  AND sold_amount_source = 'tax_deed_outcomes_sync';
