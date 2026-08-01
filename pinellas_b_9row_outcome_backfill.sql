-- Gold Standard shard-1 (dispatch ba0dc9d8): pinellas B regression fix.
--
-- The pinellas C/D fix (pinellas_cd_21row_parity_backfill.sql, commit 0eee0f26) discovered 9
-- previously-unknown CLOSED foreclosure sales among the 21 never-parity-checked pinellas cases,
-- via the RealAuction Clerk's Auction Results Report (report_id=18) for pinellas.realforeclose.com.
-- multi_county_auctions.sold_amount/tier1_sold_amount/sold_amount_source were already backfilled for
-- these 9 cases as part of that fix (VERIFIED live 2026-08-01), but no corresponding row was written
-- to foreclosure_outcomes, so closed_sold grew from 132 to 141 while verified_outcomes stayed at 132 --
-- dropping B from 100.0% (132/132) to 93.6% (132/141), a real regression per pencil_dod_evaluate_county.
--
-- This backfills foreclosure_outcomes for exactly those 9 cases, sourced from the SAME primary
-- document already used for sold_amount (RealAuction Auction Results Report), tagged with an
-- INDEPENDENT (non-"promote") data_source so the B evaluator counts them.

INSERT INTO foreclosure_outcomes (case_number, county, sale_type, outcome, winning_bid, data_source, source_url)
VALUES
  ('522019CA006299XXCICI', 'pinellas', 'foreclosure', 'sold', 350100.00, 'tier1_realforeclose_results_report:pinellas:20260801_cd21gap', 'https://pinellas.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AuctionDate=2026-07-21'),
  ('522023CC009988XXCOCO', 'pinellas', 'foreclosure', 'sold',  16900.00, 'tier1_realforeclose_results_report:pinellas:20260801_cd21gap', 'https://pinellas.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AuctionDate=2026-07-23'),
  ('522024CA005092XXCICI', 'pinellas', 'foreclosure', 'sold', 425100.00, 'tier1_realforeclose_results_report:pinellas:20260801_cd21gap', 'https://pinellas.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AuctionDate=2026-07-14'),
  ('522025CA000496XXCICI', 'pinellas', 'foreclosure', 'sold',    600.00, 'tier1_realforeclose_results_report:pinellas:20260801_cd21gap', 'https://pinellas.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AuctionDate=2026-07-14'),
  ('522025CA001203XXCICI', 'pinellas', 'foreclosure', 'sold',  44000.00, 'tier1_realforeclose_results_report:pinellas:20260801_cd21gap', 'https://pinellas.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AuctionDate=2026-07-23'),
  ('522025CA003770XXCICI', 'pinellas', 'foreclosure', 'sold', 368600.00, 'tier1_realforeclose_results_report:pinellas:20260801_cd21gap', 'https://pinellas.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AuctionDate=2026-07-28'),
  ('522025CA004720XXCICI', 'pinellas', 'foreclosure', 'sold', 286400.00, 'tier1_realforeclose_results_report:pinellas:20260801_cd21gap', 'https://pinellas.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AuctionDate=2026-07-15'),
  ('522025CA005221XXCICI', 'pinellas', 'foreclosure', 'sold',    100.00, 'tier1_realforeclose_results_report:pinellas:20260801_cd21gap', 'https://pinellas.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AuctionDate=2026-07-14'),
  ('522026CC003183XXCOCO', 'pinellas', 'foreclosure', 'sold',  53100.00, 'tier1_realforeclose_results_report:pinellas:20260801_cd21gap', 'https://pinellas.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AuctionDate=2026-07-30')
ON CONFLICT DO NOTHING;
