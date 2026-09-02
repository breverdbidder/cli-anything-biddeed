-- Issue #19720 follow-up: sale_result must be derived automatically on every write,
-- not only by the one-time backfill in 20260902_harvest_completeness_19720.sql.
-- Without this, any script that still writes winning_bidder directly (e.g.
-- realtaxdeed_winning_bidder_backfill.py, unchanged in this issue's scope) would
-- leave sale_result stale at 'PENDING' until someone remembers to re-run the backfill.
CREATE OR REPLACE FUNCTION public.trg_derive_sale_result()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.parity_status = 'CLERK_SSOT_CANCELLED' OR NEW.parity_status = 'REALTDM_CANCELLED' OR NEW.auction_status ILIKE '%cancel%' THEN
    NEW.sale_result := 'CANCELLED';
  ELSIF NEW.parity_status = 'REALTDM_REDEEMED' OR NEW.auction_status = 'redeemed' THEN
    NEW.sale_result := 'REDEEMED';
  ELSIF NEW.winning_bidder IS NOT NULL AND NEW.plaintiff IS NOT NULL AND NEW.winning_bidder = NEW.plaintiff THEN
    -- realforeclose's plaintiff-retained sentinel is opportunistically replaced with the real
    -- bank/lender name (resolve_bidder() in realtaxdeed_winning_bidder_backfill.py), which also
    -- fills the plaintiff column from the same alias -- winning_bidder=plaintiff is the reliable
    -- signal, not a text pattern on winning_bidder (a real name never contains "plaintiff").
    NEW.sale_result := 'SOLD_PLAINTIFF';
  ELSIF NEW.winning_bidder ILIKE '3rd party%' OR (NEW.winning_bidder IS NOT NULL
        AND NEW.winning_bidder NOT IN ('Plaintiff', 'Cert Holder') AND NEW.winning_bidder NOT ILIKE '%plaintiff%') THEN
    NEW.sale_result := 'SOLD_THIRD_PARTY';
  ELSIF NEW.winning_bidder IN ('Plaintiff', 'Cert Holder') OR NEW.winning_bidder ILIKE '%plaintiff%'
        OR NEW.auction_status = 'sold to plaintiff' THEN
    NEW.sale_result := 'SOLD_PLAINTIFF';
  ELSE
    RETURN NEW; -- no new signal, leave sale_result as whatever it already was (incl. case_status-driven writes)
  END IF;
  NEW.sale_result_at := now();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS derive_sale_result ON public.multi_county_auctions;
CREATE TRIGGER derive_sale_result
  BEFORE INSERT OR UPDATE OF winning_bidder, plaintiff, auction_status, parity_status ON public.multi_county_auctions
  FOR EACH ROW
  EXECUTE FUNCTION public.trg_derive_sale_result();

COMMENT ON FUNCTION public.trg_derive_sale_result() IS 'Issue #19720 -- auto-derives sale_result/sale_result_at from winning_bidder/auction_status/parity_status on every write, so no harvester script needs to remember to set it. Ordered after trg_no_future_winner alphabetically (derive_sale_result < no_future_winner) -- both are independent BEFORE triggers on disjoint-enough concerns that ordering does not matter here (the guard only rejects; it never re-derives).';
