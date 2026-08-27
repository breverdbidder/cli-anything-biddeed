-- Gold Standard: escambia letter B (verified independent outcomes)
--
-- BEFORE (live, fetched via pencil_dod_evaluate_county('escambia') prior to fix):
--   B: { "pass": false, "detail": "verified=4 closed_sold=5", "metric": 80.0 }
--   (task brief cited an earlier snapshot of verified=2 closed_sold=3; by the
--   time this session ran, 4/5 already had independent outcomes and only the
--   one gap row below remained)
--
-- GAP ROW:
--   case_number = '2025 CA 000118', county = 'escambia', sale_type = 'foreclosure'
--   auction_date = 2026-08-25, sold_amount = 77900.0 in multi_county_auctions
--   (data_source = 'calendar_sweep_mca_v3' — our own scrape, not independent)
--   No matching row existed in foreclosure_outcomes / tax_deed_outcomes with a
--   non-promote data_source.
--
-- EVIDENCE (fetched live 2026-08-27 via Playwright/Chromium render of the
-- official Escambia Clerk-contracted RealAuction auction platform):
--   URL: https://escambia.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE=08/25/2026
--   Rendered auction card for case "2025 CA 000118":
--     Auction Status: Auction Sold, 08/25/2026 11:06 AM CT
--     Amount: $77,900.00
--     Sold To: 3rd Party Bidder
--     Final Judgment Amount: $47,921.16
--     Parcel ID: 162S304800000039
--     Property Address: 1955 GARY CIR, PENSACOLA, FL 32505
--     Court document link (Escambia Clerk LandmarkWeb, CFN 2026041275):
--       http://dory.escambiaclerk.com/LandmarkWeb1.4.6.134/Document/GetDocumentByCFN/?cfn=2026041275
--   This matches our internal sold_amount ($77,900.00) exactly, confirmed
--   independently against the official clerk-sanctioned auction results page.
--
-- SQL RUN LIVE (via Supabase Management API, mocerqjnksmhcjzxrewo):

INSERT INTO public.foreclosure_outcomes
  (case_number, county, sale_type, auction_date, final_judgment, winning_bid,
   outcome, winner_type, property_address, parcel_id, zip_code,
   data_source, source_url, enriched_at)
VALUES
  ('2025 CA 000118', 'escambia', 'foreclosure', '2026-08-25', 47921.16, 77900.00,
   'sold', '3rd_party', '1955 GARY CIR', '162S304800000039', '32505',
   'escambia_realforeclose_official',
   'https://escambia.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE=08/25/2026',
   now());

-- AFTER (live, fetched via pencil_dod_evaluate_county('escambia') post-fix):
--   B: { "pass": true, "detail": "verified=5 closed_sold=5", "metric": 100.0 }
