-- Winner-name harvest (issue #19446): additive columns for the durable buyer-identity spine.
-- bidder_id = RealAuction's per-site numeric bidder identity of the WINNING bid (stable across
--             auctions within a county subdomain even when no name prints — e.g. plaintiff wins).
-- case_id   = RealAuction's internal case identifier (distinct from the county case_number),
--             shown in the Bid History modal header. Useful for direct re-pulls / dedupe.
-- bid_ladder = full proxy + live bid ladder (bidder_id, amount, type, timestamp, auto-bid flag)
--              as JSONB, for downstream ML / repeat-buyer analysis.
ALTER TABLE public.multi_county_auctions
  ADD COLUMN IF NOT EXISTS bidder_id text,
  ADD COLUMN IF NOT EXISTS case_id text,
  ADD COLUMN IF NOT EXISTS bid_ladder jsonb;

COMMENT ON COLUMN public.multi_county_auctions.bidder_id IS 'RealAuction winning-bid bidder ID (per-site numeric identity), from authenticated Bid History modal';
COMMENT ON COLUMN public.multi_county_auctions.case_id IS 'RealAuction internal Case ID (distinct from case_number), from Bid History modal header';
COMMENT ON COLUMN public.multi_county_auctions.bid_ladder IS 'Full proxy+live bid ladder JSONB: [{bidder_id, amount, bid_type, ts, is_winner, note}], from authenticated Bid History modal';

CREATE INDEX IF NOT EXISTS idx_mca_bidder_id ON public.multi_county_auctions(bidder_id) WHERE bidder_id IS NOT NULL;
