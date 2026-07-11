-- SHARD-6 hendry, letter A fix.
--
-- Context: hendry had ZERO sale_type='foreclosure' rows in multi_county_auctions
-- (fc=0), only 17 tax_deed rows. county_auction_config confirms hendry has
-- fc_method='in_person', fc_url=null -- NO online RealForeclose/RealAuction
-- platform for hendry foreclosures (same courthouse-in-person pattern as
-- Brevard). scripts/shard11_run3534_hendry_cd_harvest.py deliberately left
-- foreclosure rows untouched pending "a genuine independent source."
--
-- Source found this session: the Hendry County Clerk's own official site
-- (hendryclerk.org/courts/foreclosure-sales/) links a "VIEW FORECLOSURE SALE
-- DOCKETS" button to a live, public MuniDocs (Municode) document index:
--   https://library.municode.com/FL/hendry_clerk_of_courts/munidocs/munidocs?nodeId=260d992ad062a
-- That index lists exactly 3 real "Court Docket Calendar - Filings" PDFs
-- (foreclosure sale (FS) event dockets), generated directly from the
-- clerk's case management system:
--   - FS 11AM 9.30.26 25CA526        (1 case,  court date 09/30/2026 -- upcoming)
--   - FS 11AM 8.5.26  x2 PROPERTIES  (2 cases, court date 08/05/2026 -- upcoming)
--   - FS 11AM 7.1.26  x3 PROPERTIES  (3 cases, court date 07/01/2026 -- ALREADY PASSED
--                                     relative to session date 2026-07-11; excluded here)
--
-- This migration ingests the 3 cases with a court date still in the future
-- as of 2026-07-11 (the "currently-scheduled" foreclosure sales per the
-- brief). Fields populated are exactly what the docket PDF shows: UCN,
-- clerk case #, court date/time, division, property address/legal
-- description, plaintiff, total assessed (court fee, NOT a sale/judgment
-- amount -- left out of judgment_amount to avoid mislabeling). No
-- sold_amount/winning_bidder is set (Case Status on the docket is
-- "CLOSED" in the clerk's docket-tracking sense, which is NOT the same as
-- "sale occurred with proceeds" -- there is no sale-result field in this
-- source, so B/F remain correctly unset for these rows; fabricating a
-- sold_amount here would violate the fail-loud invariant).
--
-- auction_status='upcoming' (court date has not occurred as of ingest date).
-- data_source/parity_source use an honest label distinct from realauction/
-- realforeclose, since hendry foreclosures are NOT sold on either platform:
--   data_source = 'hendry_clerk_munidocs'
--   source_platform = 'clerk_html' (courthouse in-person sale, clerk-published docket)
--
-- Verified live via Playwright fetch of the PDFs (see session report);
-- PDF URLs (stable, re-fetchable):
--   https://mcclibraryfunctions.azurewebsites.us/api/munidocDownload/31143/92f99dbb1a244/pdf  (25CA526, 9/30/26)
--   https://mcclibraryfunctions.azurewebsites.us/api/munidocDownload/31143/933bff65d0d96/pdf  (x2, 8/5/26)

-- NOTE: auction_venue is a controlled vocabulary column (CHECK IN ('online','in_person')),
-- not a free-text location string. The physical courthouse address (25 E. Hickpochee Ave,
-- LaBelle FL -- confirmed via hendryclerk.org/courts/foreclosure-sales/ page text: "Sales are
-- held on scheduled Wednesdays starting at 11:00 AM on the second floor of the Hendry County
-- Courthouse at 25 E. Hickpochee Avenue, LaBelle, Florida") is recorded in `provenance` instead,
-- consistent with county_auction_config.fc_courthouse_address being null/not modeled per-row here.

INSERT INTO public.multi_county_auctions (
  sale_type, county, state, property_address, auction_date, auction_time,
  auction_venue, case_number, plaintiff, auction_status, data_source,
  source_platform, source_url, provenance
) VALUES
(
  'foreclosure', 'hendry', 'FL',
  '4028 RAINBOW CIR, LABELLE FL 33935',
  '2026-09-30', '11:00:00',
  'in_person',
  '25000526CAAXMX',
  'Carrington Mortgage Services LLC',
  'upcoming',
  'hendry_clerk_munidocs',
  'clerk_html',
  'https://library.municode.com/FL/hendry_clerk_of_courts/munidocs/munidocs?nodeId=92f99dbb1a244',
  'Hendry Clerk of Courts official Foreclosure Sales docket (MuniDocs), UCN 262025CA000526CAAXMX, court docket calendar generated 6/9/2026. Sale location: MAIN COURTHOUSE, 25 E. Hickpochee Ave, LaBelle FL (per docket + hendryclerk.org)'
),
(
  'foreclosure', 'hendry', 'FL',
  '1095 N SR 29 & 120 CR 78, LABELLE FL',
  '2026-08-05', '11:00:00',
  'in_person',
  '26000017CAAXMX',
  'S and C Heritage Holdings LLC',
  'upcoming',
  'hendry_clerk_munidocs',
  'clerk_html',
  'https://library.municode.com/FL/hendry_clerk_of_courts/munidocs/munidocs?nodeId=933bff65d0d96',
  'Hendry Clerk of Courts official Foreclosure Sales docket (MuniDocs), UCN 262026CA000017CAAXMX, court docket calendar generated 6/15/2026. Sale location: MAIN COURTHOUSE, 25 E. Hickpochee Ave, LaBelle FL (per docket + hendryclerk.org)'
),
(
  'foreclosure', 'hendry', 'FL',
  '6208 HOB COURT, LABELLE FL',
  '2026-08-05', '11:00:00',
  'in_person',
  '22000726CAAXMX',
  'CHL Holdings Inc',
  'upcoming',
  'hendry_clerk_munidocs',
  'clerk_html',
  'https://library.municode.com/FL/hendry_clerk_of_courts/munidocs/munidocs?nodeId=933bff65d0d96',
  'Hendry Clerk of Courts official Foreclosure Sales docket (MuniDocs), UCN 262022CA000726CAAXMX, court docket calendar generated 6/15/2026. Sale location: MAIN COURTHOUSE, 25 E. Hickpochee Ave, LaBelle FL (per docket + hendryclerk.org)'
);
