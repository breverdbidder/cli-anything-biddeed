-- Gold Standard: Calhoun County, letters B (verified/closed_sold) and F (tier1_sold/closed_sold)
-- Date: 2026-08-13 (dispatch 8389b490-c112-47cd-9fb8-c794250153c3)
--
-- Diagnosis (pre-fix): B and F both fail at metric=null (0/0 -- no rows in the
--   "closed_sold" set at all for calhoun). Root cause: single offending row,
--   case_number='171 OF 2023', parcel_id='33-1N-08-0780-0001-0203',
--   sale_type=tax_deed, auction_date=2026-07-09 (past), auction_status='completed',
--   opening_bid=6472.01, tier1_authoritative=true, tier1_sale_status='sold'
--   (tier1_verified_at = today) -- but sold_amount AND tier1_sold_amount were
--   BOTH NULL. closed_sold requires sold_amount IS NOT NULL; this was the only
--   auction row in the county, so its NULL sold_amount zeroed out both letters.
--
-- Investigation (live, 2026-08-13) -- searched for a DIRECTLY-STATED winning
--   bid / sale consideration before falling back to any derived value:
--   1. Calhoun Clerk WP REST API, taxdeedoverbids custom post type (surplus/
--      closed-sale feed), id=3553:
--        https://calhounclerk.com/wp-json/wp/v2/taxdeedoverbids/3553
--        -> acf.cert="171 OF 2023" (exact match), acf.parcel="33-1N-08-0780-0001-0203"
--           (exact match), acf.balance="2579.51" (surplus owed to former titleholder),
--           acf.owner="Bama Lee Cooper" (FORMER OWNER / surplus claimant, NOT the
--           auction winner -- not written anywhere as winning_bidder).
--        -> No content/excerpt field (ACF-only CPT). No embedded sale amount.
--   2. Media attachments on that post (checked for a recorded Tax Deed PDF):
--        https://calhounclerk.com/wp-json/wp/v2/media?parent=3553 -> [] (0 results,
--        re-verified live -- confirms the prior "already checked once" note).
--   3. Companion "taxdeeds" custom post type (pre-sale listing for the same
--      cert), id=3381:
--        https://calhounclerk.com/wp-json/wp/v2/taxdeeds?per_page=100 (search by
--        cert "171")
--        -> acf.cert="171 OF 2023", acf.cert_holder="FIG 20 LLC",
--           acf.opening_bid="6472.01" (matches our DB), acf.status="scheduled"
--           (never flipped to sold/closed post-auction), acf.pdf_file=false.
--        -> No winning-bid / sale-price field exists on this CPT at all; it only
--           ever carries opening_bid. Media check on this post also returned [].
--   4. Calhoun County Property Appraiser (Beacon/Schneider Corp) sales-history
--      tab, both URL variants supplied in the ACF records:
--        https://beacon.schneidercorp.com/Application.aspx?AppID=829&LayerID=15004&
--          PageTypeID=4&PageID=6750&Q=1494029846&KeyValue=33-1N-08-0780-0001-0203
--        https://beacon.schneidercorp.com/Application.aspx?AppID=829&LayerID=15004&
--          PageTypeID=4&PageID=6750&Q=33055124&KeyValue=33-1N-08-0780-0001-0203
--        -> HTTP 403 Forbidden on both direct curl AND a retry with a full
--           browser User-Agent + Referer header, AND via WebFetch. Beacon blocks
--           non-interactive/bot access; sales-history tab is not reachable
--           without a real browser session. UNTESTED via browser automation
--           (out of scope for this pass -- would require firecrawl-browser).
--   5. Calhoun Clerk site search ("171 OF 2023") and the county-recorder
--      "Tax Deed Surplus" listing page -- both surface only the same ACF data
--      already captured above (opening_bid, balance=2579.51), no new sale
--      amount. The statewide Official Records Index
--      (https://www.myfloridacounty.com/orisearch/07, county code 07=Calhoun)
--      is an interactive/subscription document search, not a queryable API --
--      not pursued further per the 2-3 solid tries guidance.
--
--   No directly-stated winning bid / sale consideration was found after a
--   genuinely diligent multi-source attempt. Falling back to the FL Statute
--   197.582 statutory identity per instructions:
--     winning_bid = opening_bid + surplus
--                 = 6472.01 + 2579.51
--                 = 9051.52
--   Both inputs are independently corroborated exact matches on cert AND
--   parcel_id (opening_bid from our own DB row AND the clerk's taxdeeds CPT;
--   surplus from the clerk's taxdeedoverbids CPT). Label: INFERRED (formula-
--   derived, not a directly observed sale amount).
--
--   winning_bidder is intentionally NOT set -- acf.owner="Bama Lee Cooper" on
--   the taxdeedoverbids record is the FORMER TITLEHOLDER / surplus claimant,
--   not the auction winner. No verified winning-bidder name exists for this
--   case from any source checked above.
--
-- Verification (public.pencil_dod_evaluate_county('calhoun')):
--   BEFORE:
--     B: {"pass": false, "detail": "verified=0 closed_sold=0", "metric": null}
--     F: {"pass": false, "detail": "tier1_sold=0 closed_sold=0", "metric": null}
--   AFTER:
--     B: {"pass": true, "detail": "verified=1 closed_sold=1", "metric": 100.0}
--     F: {"pass": true, "detail": "tier1_sold=1 closed_sold=1", "metric": 100.0}
--   All other letters unchanged (auctions_total=8 throughout; C remains at
--   87.5% pre-existing/out-of-scope, structurally blocked per the companion
--   calhoun_c_546of2024_phantom_ssot_cancel_reconcile.sql migration).

SET statement_timeout = 0;

INSERT INTO tax_deed_outcomes (
  case_number, county, auction_date, parcel_id, opening_bid, winning_bid,
  outcome, property_address, data_source, source_url
) VALUES (
  '171 OF 2023', 'calhoun', '2026-07-09', '33-1N-08-0780-0001-0203',
  6472.01, 9051.52, 'SOLD', NULL,
  'calhoun_clerk_taxdeedoverbids:derived_opening_plus_surplus_20260813',
  'https://calhounclerk.com/taxdeedoverbids/2026-5-td/'
)
RETURNING id, case_number, county, opening_bid, winning_bid, outcome, data_source;

-- Result: 1 row inserted (id=61a90e4c-d7e8-4a08-993d-7a790dd4ed4c)

UPDATE multi_county_auctions
SET sold_amount = 9051.52,
    tier1_sold_amount = 9051.52,
    sold_amount_source = 'calhoun_clerk_taxdeedoverbids:derived_opening_plus_surplus_20260813',
    sold_amount_captured_at = now()
WHERE lower(county) = 'calhoun'
  AND case_number = '171 OF 2023'
RETURNING county, case_number, parcel_id, opening_bid, sold_amount, tier1_sold_amount,
          sold_amount_source, sold_amount_captured_at, winning_bidder;

-- Result: 1 row updated. winning_bidder untouched (remains NULL -- no
--   verified auction-winner name available; acf.owner on the source record is
--   the former titleholder/surplus claimant, not the winning bidder).
