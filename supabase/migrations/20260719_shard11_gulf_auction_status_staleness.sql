-- Shard-11 dispatch 1a211136-77c7-4125-b70c-06b26ad13ebe
-- Gulf County auction_status staleness fix.
--
-- FINDING (from GOLD_STANDARD_SARASOTA_NASSAU_BAY_GULF_DISPATCH_9F070F2B_SESSION_REPORT.md, 2026-07-18):
-- "10 of gulf's 14 rows carry auction_status='upcoming' with auction_date already in the past
--  relative to today — a status-staleness bug worth a future session's attention."
--
-- ACTION: update auction_status to 'unknown_past_due' for all gulf rows where
-- auction_status='upcoming' AND auction_date < today.
-- This is the same pattern used for union CERT223 (commit d4567eca, 2026-07-18).
-- Does NOT write a sold_amount (no real outcome sourced — BLANK > WRONG).
-- Does NOT directly move any DoD letter, but it is honest data quality.
--
-- Idempotent: only touches rows where auction_status='upcoming' AND date is past.

UPDATE public.multi_county_auctions
SET
    auction_status = 'unknown_past_due',
    updated_at     = now()
WHERE lower(county) = 'gulf'
  AND auction_status = 'upcoming'
  AND auction_date < current_date;

-- Verification:
SELECT auction_status, count(*) AS n, min(auction_date) AS oldest, max(auction_date) AS newest
FROM public.multi_county_auctions
WHERE lower(county) = 'gulf'
GROUP BY auction_status;
