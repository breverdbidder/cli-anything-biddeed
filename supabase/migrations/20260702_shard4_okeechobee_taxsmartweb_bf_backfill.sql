-- SHARD-4 (dispatch ee409c09-b216-44e6-a39c-756982dac777, continuation run)
-- okeechobee B/F: real tax deed sale results from the PUBLIC, no-auth
-- pioneer.okeechobeelandmark.com/TaxSmartWebLive jqGrid API (Pioneer Technology
-- Group's official Clerk tax-deed-case portal, independent of PropertyOnion and
-- of our own scraper). Live-verified 2026-07-02 for all 17 okeechobee TD-format
-- cases: 6 genuinely SOLD (real high_bid), 4 REDEEMED (no sale, correctly no
-- amount), 7 still upcoming (2026-08-06 sale date, no amount). Only the 6 SOLD
-- rows get a sold_amount here — REDEEMED/upcoming rows are left untouched.
--
-- Also corrects auction_status for 3 of the 6 (2026TD020/028/029) which our own
-- scraper had stale-labeled 'cancelled' — TaxSmartWebLive confirms these sold on
-- 2026-04-09; opening_bid and parcel_id cross-checked byte-for-byte against our
-- existing multi_county_auctions rows before this migration was written (see
-- session notes), so this is a correction of a known scraper mislabel, not a
-- reclassification guess.

BEGIN;

INSERT INTO public.tax_deed_outcomes (
  case_number, county, auction_date, opening_bid, winning_bid, outcome,
  parcel_id, data_source, source_url, enriched_at
) VALUES
  ('2026TD020', 'okeechobee', '2026-04-09', 3153.80, 23000.00, 'sold_third_party',
   '1-36-34-33-0A00-00001-O000', 'okeechobee_taxsmartweb:SHARD4-OKEE-TD-V2',
   'https://pioneer.okeechobeelandmark.com/TaxSmartWebLive/', now()),
  ('2026TD028', 'okeechobee', '2026-04-09', 2554.31, 4500.00, 'sold_third_party',
   '1-08-34-33-0A00-00008-P000', 'okeechobee_taxsmartweb:SHARD4-OKEE-TD-V2',
   'https://pioneer.okeechobeelandmark.com/TaxSmartWebLive/', now()),
  ('2026TD029', 'okeechobee', '2026-04-09', 1383.19, 5000.00, 'sold_third_party',
   '1-10-34-33-0A00-00011-3100', 'okeechobee_taxsmartweb:SHARD4-OKEE-TD-V2',
   'https://pioneer.okeechobeelandmark.com/TaxSmartWebLive/', now()),
  ('2026TD030', 'okeechobee', '2026-04-09', 5048.28, 5700.00, 'sold_third_party',
   '1-13-34-33-0A00-00005-E000', 'okeechobee_taxsmartweb:SHARD4-OKEE-TD-V2',
   'https://pioneer.okeechobeelandmark.com/TaxSmartWebLive/', now()),
  ('2026TD032', 'okeechobee', '2026-04-09', 5835.29, 16000.00, 'sold_third_party',
   '1-20-34-33-0A00-00009-B000', 'okeechobee_taxsmartweb:SHARD4-OKEE-TD-V2',
   'https://pioneer.okeechobeelandmark.com/TaxSmartWebLive/', now()),
  ('2026TD034', 'okeechobee', '2026-04-09', 2490.80, 12900.00, 'sold_third_party',
   '1-21-34-33-0A00-00015-P000', 'okeechobee_taxsmartweb:SHARD4-OKEE-TD-V2',
   'https://pioneer.okeechobeelandmark.com/TaxSmartWebLive/', now())
ON CONFLICT DO NOTHING;

UPDATE public.multi_county_auctions
SET sold_amount = v.winning_bid,
    sold_amount_source = 'okeechobee_taxsmartweb',
    sold_amount_captured_at = now(),
    auction_status = 'sold'
FROM (VALUES
  ('2026TD020', 23000.00::numeric),
  ('2026TD028', 4500.00::numeric),
  ('2026TD029', 5000.00::numeric),
  ('2026TD030', 5700.00::numeric),
  ('2026TD032', 16000.00::numeric),
  ('2026TD034', 12900.00::numeric)
) AS v(case_number, winning_bid)
WHERE multi_county_auctions.case_number = v.case_number
  AND lower(multi_county_auctions.county) = 'okeechobee'
  AND multi_county_auctions.sold_amount IS NULL;

SELECT public.promote_tier1_from_outcomes();

COMMIT;
