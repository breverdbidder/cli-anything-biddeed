-- Gold Standard cert-fix, dispatch ca56cc4d-4e7f-4234-814f-a1e6de065d52 (SHARD-C1), county=desoto
-- Real sale outcome discovered live 2026-07-31 in DeSoto County Clerk's Tax Deed
-- Excess Funds / Surplus list (source PDF stamped "UPDATED 07/30/2026"), a genuinely
-- new document versus all 8 prior sessions on this dispatch (which only saw the
-- foreclosure surplus list stuck at 6/29/2026, and no tax-deed excess-funds entry
-- for this case). Source:
--   https://www.desotoclerk.com/wp-content/uploads/2026/07/7.30Copy-of-EXCESS-FUNDS-LIST-1.pdf
-- Row: File #26-06-TD | Owner THOMAS WIDEMAN | Parcel 20-37-25-0059-0000-015A
--      | New Owner PATRICIA NARVAEZ | Sale Date 7/29/2026 | Sale Price $23,000.00
--      | Surplus $20,301.02 | Final Date Submit Claim 12/5/2026
-- This is the ONLY one of the 4 past-due desoto cases (25CA632, 25CA638, 26-04-TD,
-- 26-06-TD) with real, independently-sourced sale evidence as of this session.
-- 25CA632/25CA638 (foreclosure): checked against
--   https://www.desotoclerk.com/wp-content/uploads/2026/06/6.30SURPLUS-LIST-FOR-FORECLOSURE.pdf
--   (still stale, updated 6/29/26, neither case present) -- NOT fixed, still blocked.
-- 26-04-TD (tax deed): checked against the same 7/30/2026 excess funds list above --
--   NOT present -- NOT fixed, still blocked.
--
-- Idempotent: ON CONFLICT guards on both statements.

BEGIN;

UPDATE public.multi_county_auctions
SET sold_amount = 23000.00,
    tier1_sold_amount = 23000.00,
    winning_bidder = 'PATRICIA NARVAEZ',
    auction_status = 'sold',
    sale_result_date = '2026-07-29',
    sold_amount_source = 'desoto_clerk_excess_funds_pdf:7.30Copy-of-EXCESS-FUNDS-LIST-1',
    sold_amount_captured_at = now(),
    tier1_authoritative = true,
    tier1_verified_at = now(),
    tier1_sale_status = 'sold',
    updated_at = now()
WHERE county = 'desoto'
  AND case_number = '26-06-TD'
  AND sold_amount IS NULL;

INSERT INTO public.tax_deed_outcomes (
    case_number, county, auction_date, parcel_id,
    cert_number, winning_bid, outcome,
    winner_name, property_address,
    data_source, source_url, enriched_at, created_at
) VALUES (
    '26-06-TD', 'desoto', '2026-07-29', '20-37-25-0059-0000-015A',
    NULL, 23000.00, 'sold',
    'PATRICIA NARVAEZ', '3785 NE BONANZA PARK AVE, ARCADIA FL',
    'desoto_clerk_excess_funds_pdf',
    'https://www.desotoclerk.com/wp-content/uploads/2026/07/7.30Copy-of-EXCESS-FUNDS-LIST-1.pdf',
    now(), now()
)
ON CONFLICT (case_number, county, auction_date) DO NOTHING;

COMMIT;
