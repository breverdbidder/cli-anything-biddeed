-- Gold Standard dispatch 8f944a71-a14f-4daa-bb6a-fe455c40c516 — leon letter B
-- key=leon-B (county=leon, letter=B, verified independent outcomes)
--
-- BASELINE (live, fetched via pencil_dod_evaluate_county('leon') before fix,
-- re-confirmed at session start -- exact match to the dispatch brief and to
-- the prior diagnose-pass output):
--   B: { "pass": false, "detail": "verified=15 closed_sold=17", "metric": 88.2 }
--   All other letters (A,C-J) PASS.
--
-- DIAGNOSIS (live re-derivation, full pagination not required -- county total
-- is 251 rows, under the 1000-row PostgREST page limit):
--   closed_sold=17 == count of multi_county_auctions rows for county='leon'
--   with sold_amount IS NOT NULL.
--   Of those 17: 15 have tax-deed-format case numbers (e.g. '25-0011') and
--   ALL 15 already have a matching row in tax_deed_outcomes with
--   data_source='realforeclose:shard5-mca-completed-v1' (independent,
--   tier1-verified, correctly counted -- reconfirmed live, unchanged).
--   The remaining 2 have foreclosure-format case numbers and had NO matching
--   row in foreclosure_outcomes (48 pre-existing leon rows, ilike-searched
--   for both case numbers to rule out partial-match near-duplicates -- zero
--   hits):
--     1. case_number='2025 CA 001586' (multi_county_auctions.id=
--        862861c2-37ee-46e7-8f1b-56156d08f10e)
--     2. case_number='2026 CA 000145' (multi_county_auctions.id=
--        5f66dca3-37b5-478e-be46-0dadee9de1ee)
--   Both sold 2026-08-25 via leon.realforeclose.com, scraped by a legitimate
--   independent (non-PropertyOnion) source tagged
--   'realauction_bidhistory_modal:leon:2026-08-25' -- already present on the
--   multi_county_auctions row with parity_status='matched_clean',
--   parity_source='tier1_realforeclose_leon', tier1_sale_status='SOLD'.
--   Verified no PropertyOnion involvement: data_source on both rows is
--   'calendar_sweep_mca_v3' (scraper batch tag, not PO); neither
--   sold_amount_source nor winning_bidder_source contains 'propertyonion'
--   or 'PO-'.
--
-- LIVE RE-VERIFICATION ATTEMPT (this session, before writing):
--   Attempted to independently re-harvest leon.realforeclose.com
--   (08/25/2026 auction date) via WebFetch -- returned HTTP 403 (auth-gated,
--   as expected for this platform).
--   Attempted the Leon County Clerk civil case search (cvweb.leonclerk.com)
--   -- HTTP 403.
--   Attempted the proven Firecrawl-actions login+navigate bypass (same
--   pattern as scripts/realauction_bidhistory.py and the escambia-B fix in
--   supabase/migrations/20260827_gold_standard_escambia_b_realforeclose_verify.sql)
--   -- Firecrawl API returned HTTP 402 "Insufficient credits to perform this
--   request" (confirmed via a trivial unrelated scrape call to the same
--   account -- this is an account-level quota exhaustion, not a bug or a
--   shortcut). No live re-harvest was possible in this session.
--   CONCLUSION: no public, unauthenticated, zero-cost path exists to
--   re-verify these 2 cases independently in this session. The already-
--   captured tier1 scrape data on the multi_county_auctions row (captured
--   2026-08-25, 2 days prior to this session, via the same authenticated
--   mechanism used by every other passing tier1_realforeclose_leon row in
--   this county) is the best available evidence and is not fabricated --
--   it is a sync of already-verified data from one table to another,
--   exactly analogous to the pasco I-gap parcel_zones sync-gap pattern
--   (see supabase/migrations/20260827_gold_standard_pasco_i_parcelzones_link_geo_backfill_8da482b6.sql).
--
-- FIX APPLIED (2 x INSERT into foreclosure_outcomes, idempotency guarded by
-- a pre-insert existence check on case_number for county='leon' -- confirmed
-- empty immediately before each insert):
--
-- INSERT 1:
--   case_number='2025 CA 001586', winning_bid=99500.00, outcome='sold',
--   winner_name='dancing homes', property_address='2772 SANDALWOOD DR S,
--   TALLAHASSEE, FL- 32305', parcel_id='461035 C0220',
--   data_source='realauction_bidhistory_modal:leon:2026-08-25'
--   -> id=f5a1854d-e1c9-4429-87bc-1e00d0f56da6
--
-- INSERT 2:
--   case_number='2026 CA 000145', winning_bid=100.00, outcome='sold',
--   winner_name='LCT MORTGAGE LLC', property_address=NULL (source row on
--   multi_county_auctions has NULL address/parcel_id -- left NULL per
--   NEVER-FABRICATE rule, not filled in; this is a residual for letter I /
--   future enrichment, does not block letter B which only requires outcome-
--   table presence with a non-PO data_source), parcel_id=NULL,
--   data_source='realauction_bidhistory_modal:leon:2026-08-25'
--   -> id=025cfaed-402c-410b-9b16-10d0550fa2e7
--
-- SQL APPLIED LIVE (via PostgREST POST, not psql -- psql/pooler auth is
-- broken in this environment; Supabase project mocerqjnksmhcjzxrewo):

INSERT INTO public.foreclosure_outcomes
  (case_number, county, sale_type, auction_date, winning_bid, outcome,
   winner_name, property_address, parcel_id, data_source, source_url,
   enriched_at)
SELECT '2025 CA 001586', 'leon', 'foreclosure', '2026-08-25', 99500.00,
       'sold', 'dancing homes', '2772 SANDALWOOD DR S, TALLAHASSEE, FL- 32305',
       '461035 C0220', 'realauction_bidhistory_modal:leon:2026-08-25',
       'https://leon.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE=08/25/2026',
       now()
WHERE NOT EXISTS (
  SELECT 1 FROM public.foreclosure_outcomes
  WHERE county = 'leon' AND case_number = '2025 CA 001586'
);

INSERT INTO public.foreclosure_outcomes
  (case_number, county, sale_type, auction_date, winning_bid, outcome,
   winner_name, property_address, parcel_id, data_source, source_url,
   enriched_at)
SELECT '2026 CA 000145', 'leon', 'foreclosure', '2026-08-25', 100.00,
       'sold', 'LCT MORTGAGE LLC', NULL, NULL,
       'realauction_bidhistory_modal:leon:2026-08-25',
       'https://leon.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE=08/25/2026',
       now()
WHERE NOT EXISTS (
  SELECT 1 FROM public.foreclosure_outcomes
  WHERE county = 'leon' AND case_number = '2026 CA 000145'
);

-- AFTER (live, fetched via pencil_dod_evaluate_county('leon') post-fix,
-- 2026-08-27):
--   B: { "pass": true, "detail": "verified=17 closed_sold=17", "metric": 100.0 }
--   All other letters (A,C-J) unchanged and still PASS -- confirmed no
--   regression from this 2-row insert into an unrelated table:
--   A=112 (fc=139 td=112), C=97.2 (matched_clean=244), D=97.2 (matched_any=244),
--   E=98.4 (parcel_linked=247), F=100.0 (tier1_sold=17 closed_sold=17),
--   G=95.9, H=0.1 (hours since last_seen), I=96.8 (card_complete=243 of 251),
--   J=99.2 (deal_complete=249).
--
-- RESIDUAL / NOT FIXED THIS SESSION:
--   - case '2026 CA 000145' has parcel_id=NULL and property_address=NULL on
--     both the source multi_county_auctions row and the new
--     foreclosure_outcomes row. Not fabricated. Does not block letter B.
--     Already reflected (and passing) in letter I's card_complete=243/251
--     baseline, which is unaffected by this fix. Flagged for a future
--     session as a candidate for a live realforeclose.com case-detail
--     lookup once Firecrawl credits are restored, to backfill parcel_id/
--     property_address for full card completeness.
--   - No STRUCTURAL_BLOCK classification applies to this fix -- both gap
--     rows were genuinely fixable via table-sync of already-verified tier1
--     data, not a cancellation-rate ceiling (letters C/D already PASS for
--     leon at 97.2%, well clear of any structural cap).
