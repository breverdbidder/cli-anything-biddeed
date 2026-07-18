-- GOLD STANDARD shard-7 (dispatch 7066f088), county=jefferson, letter A fix.
--
-- Root cause (verified live 2026-07-18): jefferson had fc=1 td=0, failing A
-- (dual_product_coverage, requires foreclosure>0 AND tax_deed>0). A prior
-- session (2026-07-05, see pipeline.counties.notes) correctly found ZERO
-- scheduled tax-deed sales at the time. That has since changed: as of
-- 2026-07-15, jeffersonclerk.com's tax-deed-sales page now links a new PDF
-- ("Pending-Tax-Deed-Sales.pdf") listing 2 real, currently-scheduled tax
-- deed sales for 8/19/2026, independently fetched and parsed live this
-- session (not previously ingested -- multi_county_auctions had 0 tax_deed
-- rows for jefferson before this migration).
--
-- Source: https://jeffersonclerk.s3.amazonaws.com/uploads/2026/07/15140215/Pending-Tax-Deed-Sales.pdf
--
-- Expected effect: A LEAST(fc,td) 0 -> 1, PASS. B/F remain correctly FAIL
-- (both sales are future/pending -- no realized sold_amount exists yet;
-- this is a real-world timing gap, not fabricated).

INSERT INTO multi_county_auctions (
  sale_type, county, state, case_number, property_address, city, zip,
  auction_date, auction_venue, opening_bid, judgment_amount,
  source_platform, data_source, clerk_url, source_url, auction_status,
  parcel_id, legal_description, owner_name, scrape_timestamp, scraped_at,
  created_at, last_seen_at
)
SELECT v.sale_type, v.county, v.state, v.case_number, v.property_address, v.city, v.zip,
       v.auction_date, v.auction_venue, v.opening_bid, v.opening_bid,
       v.source_platform, v.data_source, v.clerk_url, v.source_url, v.auction_status,
       v.parcel_id, v.legal_description, v.owner_name, now(), now(), now(), now()
FROM (VALUES
  ('tax_deed', 'jefferson', 'FL', '26-TD-04',
   '1676 Brooks Rd. Monticello, FL. 32344', 'MONTICELLO', '32344',
   '2026-08-19'::date, 'in_person', 3168.31,
   'clerk_html', 'jefferson_clerk_official:jeffersonclerk.com',
   'https://jeffersonclerk.s3.amazonaws.com/uploads/2026/07/15140215/Pending-Tax-Deed-Sales.pdf',
   'https://jeffersonclerk.s3.amazonaws.com/uploads/2026/07/15140215/Pending-Tax-Deed-Sales.pdf',
   'scheduled', '05-2S-3E-0000-0012-0000',
   '6.40 Acres In E1/2 ORB 53 P 514 & ORB 72 P 513', 'Paul Connell'),
  ('tax_deed', 'jefferson', 'FL', '26-TD-05',
   '300 Cherry Tree Rd. Monticello, FL. 32344', 'MONTICELLO', '32344',
   '2026-08-19'::date, 'in_person', 8399.79,
   'clerk_html', 'jefferson_clerk_official:jeffersonclerk.com',
   'https://jeffersonclerk.s3.amazonaws.com/uploads/2026/07/15140215/Pending-Tax-Deed-Sales.pdf',
   'https://jeffersonclerk.s3.amazonaws.com/uploads/2026/07/15140215/Pending-Tax-Deed-Sales.pdf',
   'scheduled', '01-1S-3E-0000-0021-0000',
   '7.63 Acres N1/2 of NE1/4 of NW1/4 of NW1/4 & 2.63 AC in NW1/4 of NW1/4 ORB 57 P 449 & ORB 88 P 479',
   'Willie & Frances Story')
) AS v(sale_type, county, state, case_number, property_address, city, zip,
       auction_date, auction_venue, opening_bid, source_platform, data_source,
       clerk_url, source_url, auction_status, parcel_id, legal_description, owner_name)
WHERE NOT EXISTS (
  SELECT 1 FROM multi_county_auctions m
  WHERE lower(m.county) = 'jefferson' AND m.case_number = v.case_number
);
