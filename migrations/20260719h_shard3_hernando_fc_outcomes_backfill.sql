-- SHARD3-HERNANDO-FC-V1: backfill closed foreclosure sale outcome for Hernando
-- county, sourced from live Certificate of Title postings on the Hernando
-- County Clerk's Official Records search (or.hernandoclerk.com/LandmarkWeb).
--
-- Context: 10 hernando foreclosure auctions with auction_date < now() had
-- sold_amount/outcome NULL, causing pencil_dod_evaluate_county('hernando')
-- letters B and F to FAIL (verified_outcomes=0, closed_sold=0, tier1_sold=0).
--
-- Real-source verification performed this session:
--   1. hernandoclerk.com foreclosure-sale-lists PDFs (30-JUNE/07-JULY/14-JULY
--      2026) confirmed all 10 cases still show "Pending" pre-auction notices
--      only (published 6/4/2026, pre-sale) -- no sold results published there.
--   2. or.hernandoclerk.com/LandmarkWeb (Civitek-powered Official Records
--      Search) Name-search (party name, Contains match, date range
--      01/01/2024-07/19/2026) run against the defendant name for each of the
--      10 case numbers. Only ONE case has a recorded Certificate of Title
--      (Doc Type DEED2) post-dating its auction date:
--        Case 25000967CA (U.S. Bank National Assoc. vs. Cooper B. Knowles)
--        Instrument #2026046908, OR Book 4733 / Page 1708
--        Recorded 07/13/2026 10:24:10 AM
--        Sale Date: 06/30/2026 (matches multi_county_auctions.auction_date)
--        Consideration: $68,100.00
--        Grantor: Hernando County Clerk of the Circuit Court / U.S. Bank NA /
--                 Cooper B. Knowles et al.
--        Grantee: Home Discounters LLC
--        Legal: Lots 9 and 10, Block 18, Masaryktown
--        Property: 237 Broad Street, Brooksville, FL 34604
--        (matches multi_county_auctions.property_address "237  BROAD ST")
--
--   The other 9 cases (23001588CA, 25000637CA, 25001269CA, 25000736CA,
--   25000792CA, 23001250CA, 22001005CA, 25000885CA, 25000696CA) were checked
--   via the same Name-search method and have NO Certificate of Title or any
--   post-auction-date recorded instrument as of 2026-07-19 -- their most
--   recent record is a pre-auction JUDGMENT (final judgment of foreclosure).
--   This is left untouched per NEVER-LIE / no-fabrication rules -- honest
--   1/10 backfill, not a fake 10/10.
--
-- source_url: https://or.hernandoclerk.com/LandmarkWeb/ (Case Number/Name
--   search interface); direct document view for Instrument #2026046908

SET statement_timeout = 0;

INSERT INTO public.foreclosure_outcomes (
    case_number, county, sale_type, auction_date,
    winning_bid, outcome, winner_name, winner_type,
    property_address, data_source, source_url
)
VALUES (
    '25000967CA', 'hernando', 'foreclosure', '2026-06-30',
    68100.00, 'sold', 'HOME DISCOUNTERS LLC', 'third_party',
    '237 BROAD ST, BROOKSVILLE, FL 34604',
    'hernando_landmarkweb_cot:SHARD3-HERNANDO-FC-V1',
    'https://or.hernandoclerk.com/LandmarkWeb/ (Instrument #2026046908, OR 4733/1708)'
)
ON CONFLICT (case_number, county, auction_date) DO UPDATE
SET winning_bid = EXCLUDED.winning_bid,
    outcome = EXCLUDED.outcome,
    winner_name = EXCLUDED.winner_name,
    winner_type = EXCLUDED.winner_type,
    property_address = EXCLUDED.property_address,
    data_source = EXCLUDED.data_source,
    source_url = EXCLUDED.source_url,
    enriched_at = now();

UPDATE public.multi_county_auctions
SET sold_amount = 68100.00,
    tier1_sold_amount = 68100.00
WHERE case_number = '25000967CA'
  AND county = 'hernando'
  AND sale_type = 'foreclosure';
