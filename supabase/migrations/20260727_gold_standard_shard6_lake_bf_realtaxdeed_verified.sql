-- Gold Standard shard-6 (pinellas/escambia/lake), run6459, 2026-07-27.
-- Lake county B/F: live re-probe of lake.realtaxdeed.com/index.cfm?zaction=AUCTION&zmethod=PREVIEW
-- for AuctionDate=07/21/2026 (6 days past-due; prior probe on 2026-07-11 -- see
-- scripts/shard7_run3679_lake_bf_realtaxdeed_probe.py -- found these 10 cases still
-- "Auctions Waiting" because the date hadn't occurred yet). VERIFIED live this session:
-- 8 of the 10 actually sold to a 3rd party bidder with real, published amounts; the
-- 9th (02731-2022) was already corrected to canceled_bankruptcy by the 07-11 session.
-- The 10th in our DB (05292-2023) does NOT appear anywhere on the live closed/canceled
-- list for 07/21/2026 (the site instead lists case 04358-2023/Redeemed, which is not in
-- our multi_county_auctions at all) -- a genuine case-number discrepancy, NOT resolved
-- here; left untouched rather than guessed. Flagged in session report for follow-up.
--
-- Independent outcome source (satisfies canon B: verified_outcomes EXISTS join on
-- tax_deed_outcomes with data_source NOT ILIKE '%promote%'), then sold_amount/
-- auction_status corrected directly on multi_county_auctions so promote_tier1_from_outcomes()
-- (existing hourly cron, NOT modified here) carries the amount into tier1_sold_amount for F.

INSERT INTO public.tax_deed_outcomes (county, case_number, outcome, winning_bid, data_source, source_url, created_at)
VALUES
  ('lake', '00831-2023', 'SOLD', 3000.00,  'lake_realtaxdeed_official_live', 'https://lake.realtaxdeed.com/index.cfm?zaction=AUCTION&zmethod=PREVIEW&AuctionDate=07/21/2026', now()),
  ('lake', '01117-2018', 'SOLD', 2600.00,  'lake_realtaxdeed_official_live', 'https://lake.realtaxdeed.com/index.cfm?zaction=AUCTION&zmethod=PREVIEW&AuctionDate=07/21/2026', now()),
  ('lake', '01475-2023', 'SOLD', 6100.00,  'lake_realtaxdeed_official_live', 'https://lake.realtaxdeed.com/index.cfm?zaction=AUCTION&zmethod=PREVIEW&AuctionDate=07/21/2026', now()),
  ('lake', '04267-2023', 'SOLD', 24200.00, 'lake_realtaxdeed_official_live', 'https://lake.realtaxdeed.com/index.cfm?zaction=AUCTION&zmethod=PREVIEW&AuctionDate=07/21/2026', now()),
  ('lake', '04359-2023', 'SOLD', 1900.00,  'lake_realtaxdeed_official_live', 'https://lake.realtaxdeed.com/index.cfm?zaction=AUCTION&zmethod=PREVIEW&AuctionDate=07/21/2026', now()),
  ('lake', '04475-2023', 'SOLD', 15200.00, 'lake_realtaxdeed_official_live', 'https://lake.realtaxdeed.com/index.cfm?zaction=AUCTION&zmethod=PREVIEW&AuctionDate=07/21/2026', now()),
  ('lake', '05040-2023', 'SOLD', 4900.00,  'lake_realtaxdeed_official_live', 'https://lake.realtaxdeed.com/index.cfm?zaction=AUCTION&zmethod=PREVIEW&AuctionDate=07/21/2026', now()),
  ('lake', '05291-2023', 'SOLD', 14600.00, 'lake_realtaxdeed_official_live', 'https://lake.realtaxdeed.com/index.cfm?zaction=AUCTION&zmethod=PREVIEW&AuctionDate=07/21/2026', now())
ON CONFLICT DO NOTHING;

UPDATE public.multi_county_auctions
SET sold_amount = v.winning_bid,
    sold_amount_source = 'lake_realtaxdeed_official_live',
    auction_status = 'sold'
FROM (VALUES
  ('00831-2023', 3000.00),
  ('01117-2018', 2600.00),
  ('01475-2023', 6100.00),
  ('04267-2023', 24200.00),
  ('04359-2023', 1900.00),
  ('04475-2023', 15200.00),
  ('05040-2023', 4900.00),
  ('05291-2023', 14600.00)
) AS v(case_number, winning_bid)
WHERE multi_county_auctions.case_number = v.case_number
  AND lower(multi_county_auctions.county) = 'lake'
  AND multi_county_auctions.sale_type = 'tax_deed';

SELECT public.promote_tier1_from_outcomes();
