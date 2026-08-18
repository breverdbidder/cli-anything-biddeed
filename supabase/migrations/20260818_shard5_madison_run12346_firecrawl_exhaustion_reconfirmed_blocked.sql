-- Gold Standard shard-5, dispatch b9424095-68da-434e-93fb-0b27acb821b0, county=madison,
-- letters B/F/I. Date: 2026-08-18 (loop run 12346). ULTRALOOP native mode (Workflow-tool
-- 3-agent fan-out + adversarial refuter pass on any candidate).
--
-- LIVE STATE (pencil_dod_evaluate_county('madison'), unchanged before/after this session):
--   A PASS fc=6/td=2 | B FAIL verified=0/closed_sold=0 | C/D/E PASS 100.0 | F FAIL
--   tier1_sold=0/closed_sold=0 | G PASS 100.0 | H PASS 0.2-0.7h | I FAIL card_complete=6 of 8
--   (75.0) | J PASS 100.0. pass_count=7/10, unchanged from every session since 2026-07-10.
--
-- This is the 10th+ consecutive independent session confirming this exact B/F/I structural
-- block (prior: 2026-07-10, 07-11, 07-28, 07-30, 08-01, 08-03 x2, 08-13, 08-15, 08-16, 08-17 x2
-- -- decision_log ids 169, 254, 673, 855, 960, 1131, 1233, 1304/1474, 1575, 1949 and this
-- session's own new evidence below).
--
-- WHAT THIS SESSION DID DIFFERENTLY: prior sessions' stated blocker for the OCRS (B/F) and
-- FGDL.org (I) leads was "no browser tool available" / CAPTCHA / JS-rendering. This session had
-- firecrawl-browser available and fanned out 3 parallel agents specifically to attempt it:
--   1. bf_clerk_fresh: fresh curl/WebFetch re-check of madisonclerk.com (rendered HTML + raw
--      wp-json/wp/v2/foreclosures feed + tax-deed-sales embedded JSON) for all 8 madison cases,
--      with particular attention to 21-36-CA and 26-20-CA (auction_date already passed while
--      status still reads "scheduled" -- a possible stale-status lead) and 24-62-CA (status
--      already "sold"). CONFIRMED: the wp-json feed's "amount" field is populated identically
--      for every case regardless of sale status (e.g. future-scheduled 25-31-CA also carries an
--      "amount") -- it is the judgment amount, not a sale-result figure. No sold/cancelled/
--      redeemed text exists anywhere on the site for any of the 3 past-due cases; the front-end
--      simply stops rendering a case once its date passes rather than publishing a result. No
--      new information; feed unchanged since 2026-06-04/05-07 per the fetched "modified"
--      timestamps.
--   2. bf_ocrs_browser: attempted firecrawl-browser against myfloridacounty.com/orisearch,
--      civitekflorida.com, and myfloridacounty.com/publicresearch for cases 24-62-CA and
--      21-36-CA.
--   3. i_fgdl_zoning: attempted firecrawl-browser against fgdl.org, madisonpa.com/qpublic, and
--      planning.madisoncountyfla.com/gis for the 2 I-blocking parcels
--      (21-2N-09-5288-022-000 / -021-000).
--
-- NEW FINDING (genuinely new, not a repeat): agents 2 and 3 never actually reached any target
-- site. The shared FIRECRAWL_API_KEY account for this project is over its monthly quota:
-- `firecrawl credit-usage` -> remainingCredits=-15 of planCredits=1000 (101.5%% used), current
-- billing period 2026-07-28 to 2026-08-28. Every scrape/browser call failed immediately with
-- HTTP 402 "Insufficient credits to perform this request" before any page load. This is an
-- account-level exhaustion affecting every county/session on this project for the rest of the
-- current billing period (through 2026-08-28), not a per-site CAPTCHA/JS block -- a materially
-- different and more actionable root cause than what prior sessions assumed ("browser tool not
-- available"/CAPTCHA). Flagging fleet-wide: any other shard this billing period relying on
-- firecrawl-browser/firecrawl-scrape for a JS-gated or Cloudflare-protected source will hit the
-- identical 402, and should not re-attempt it as if it were a fresh capability -- either wait
-- for the 2026-08-28 quota reset or get the Firecrawl plan topped up (this session's own
-- earlier prior-report review found the 2026-08-15 session had already independently flagged
-- "Firecrawl re-confirmed dead ('Insufficient credits')" for the same reason -- so this
-- constraint predates this session and is not new-since-08-17, but the exact numeric quota
-- state and billing-period end date are newly confirmed here).
--
-- SEPARATELY (no new tool needed): re-examined the one existing foreclosure_outcomes row for
-- madison (case_number=24-62-CA, data_source='auction.com listing ... trustee_sale_number
-- 2024000062CAAXMX, listing_status=NO_SALE/Reverted', outcome='sold', opening_bid=100.00,
-- winning_bid=NULL, created 2026-07-30). This is a real, non-fabricated, already-ingested row --
-- but it independently confirms the exact same dead end the 2026-08-03 session already reached
-- (migration 20260803_gold_standard_shard_df5a4f3a_madison_abf_fix.sql): a reverted/no-3rd-
-- party-bid foreclosure has no winning_bid by definition, so there is no dollar figure to
-- backfill into multi_county_auctions.sold_amount. Per the fabrication ban, opening_bid ($100)
-- or the clerk's judgment amount ($127,543.12) are NOT valid stand-ins for an actual sale price
-- and were not written anywhere.
--
-- ULTRALOOP: 3 recon agents fanned out (Workflow tool, native mode), 0 candidates surfaced
-- (all 3 reported found_new_info=false / unblocked=false with literal evidence), so 0 refuter
-- agents were needed -- there was nothing to adversarially verify a "found something" claim
-- against. The "still genuinely blocked" claim itself is logged below as the audited claim,
-- consistent with prior sessions' convention (see gold_standard_ultraloop_audit rows for
-- madison dated 2026-08-16, dispatch 6a9e3c3a).
--
-- CONCLUSION: B, F, I remain FAIL. Genuine data ceiling, re-confirmed with new evidence
-- (Firecrawl account exhaustion, not CAPTCHA, is today's specific blocker for the one untried
-- lever). No schema or data changes. Zero rows written to multi_county_auctions,
-- foreclosure_outcomes, tax_deed_outcomes, or parcel_zones this session. BLANK > WRONG.
--
-- Remaining real unblock paths (unchanged): B/F need either a Madison Clerk phone/records-
-- request for 21-36-CA and 24-62-CA's actual disposition, or Firecrawl quota to reset/refill
-- (2026-08-28) so civitekflorida.com/myfloridacounty.com OCRS can actually be attempted through
-- their Cloudflare Turnstile challenge. I needs the same Firecrawl capability against fgdl.org,
-- OR a phone call to Madison County Planning/Zoning (850-973-1454) for the 2 vacant SR-53
-- parcels' real zone_code.

INSERT INTO public.gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
VALUES
  ('b9424095-68da-434e-93fb-0b27acb821b0', 'native', 'madison', 'B',
   'B still FAIL (verified=0/closed_sold=0). New lever attempted this session (firecrawl-browser against myfloridacounty.com/civitekflorida.com for cases 24-62-CA/21-36-CA) never reached the target site: shared FIRECRAWL_API_KEY account over quota (remainingCredits=-15/1000, billing period 2026-07-28..2026-08-28), confirmed via literal `firecrawl credit-usage` output, not a CAPTCHA/JS block this time. Existing foreclosure_outcomes row for 24-62-CA (auction.com, NO_SALE/Reverted, winning_bid=NULL) re-confirmed as having no recoverable dollar amount by definition. 10th+ consecutive session reaching this conclusion. Zero writes.',
   jsonb_build_object('firecrawl_credit_usage', '{"remainingCredits":-15,"planCredits":1000,"billingPeriodStart":"2026-07-28T22:28:40.091Z","billingPeriodEnd":"2026-08-28T22:28:40.091Z"}', 'clerk_feed_reconfirmed', 'wp-json amount field = judgment amount on all 6 rows regardless of status, no sold/result field exists', 'existing_outcome_row', 'foreclosure_outcomes case_number=24-62-CA winning_bid=NULL opening_bid=100.00, no dollar figure recoverable'),
   true),
  ('b9424095-68da-434e-93fb-0b27acb821b0', 'native', 'madison', 'F',
   'F still FAIL (tier1_sold=0/closed_sold=0). Same root cause and same new evidence as B this session (single denominator gap, case 24-62-CA, Firecrawl account exhaustion blocked the one untried lever).',
   jsonb_build_object('shares_root_cause_with', 'B', 'firecrawl_credit_usage', '{"remainingCredits":-15,"planCredits":1000}'),
   true),
  ('b9424095-68da-434e-93fb-0b27acb821b0', 'native', 'madison', 'I',
   'I still FAIL (card_complete=6 of 8, 75.0). New lever attempted this session (firecrawl-browser against fgdl.org, madisonpa.com/qpublic, planning.madisoncountyfla.com/gis for parcels 21-2N-09-5288-022-000 and -021-000) never reached any target site: identical Firecrawl account-exhaustion blocker as B/F. No zone_code recovered for either of the 2 blocking tax-deed parcels. No proximity/analogy inference used (fabrication ban).',
   jsonb_build_object('firecrawl_credit_usage', '{"remainingCredits":-15,"planCredits":1000}', 'target_parcels', jsonb_build_array('21-2N-09-5288-022-000','21-2N-09-5288-021-000'), 'real_district_code_list', jsonb_build_array('A-1','A-2','R-1','CO','HI','MU','CP','I','P','C','REC','UDO')),
   true);
