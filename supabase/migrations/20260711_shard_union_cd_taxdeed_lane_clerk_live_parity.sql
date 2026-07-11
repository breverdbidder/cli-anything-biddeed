-- Union County: C/D fix via tier1-clerk-live double-fetch parity stamping.
-- B/F investigated and left honestly FAIL (no fabrication).
--
-- CONTEXT: union has only 3 multi_county_auctions rows, all sourced from
-- unionclerk.com (source_platform='unionclerk', data_source=
-- 'unionclerk_official', scripts/shard9_union_clerk_realdata_ingest.py).
-- Union's RealAuction lane is confirmed dark -- sales are in-person only
-- (Thursdays 11:00 AM, Union County Courthouse lobby, 55 W Main St, Lake
-- Butler) -- so there is no independent second digital lane to cross-check
-- against. This qualifies for the same ratified tier1-clerk-live precedent
-- used for calhoun (20260710_shard12_calhoun_taxdeed_lane_acd_fix.sql):
-- when the clerk's own record IS the sole authoritative source, a live
-- double-fetch (>=30s apart) that agrees field-for-field on case_number/
-- cert#/parcel_id/auction_date/status is sufficient to stamp
-- parity_status='matched_clean'.
--
-- C/D FIX: fetched all 3 live pages (unionclerk.com foreclosure-sales,
-- unionclerk.com tax-deed-sales) TWICE, 35s apart
-- (scripts/shard_union_cd_doublefetch_cert223_recheck.py, run
-- 2026-07-11T05:5x UTC). All 3 cases agreed exactly across both fetches:
--   63-2024-CA-0047 (foreclosure): parcel 15-05-20-00-000-0080-0,
--     auction_date 10/15/2026, status SCHEDULED -- fetch1=match fetch2=match
--   63-2025-CA-0053 (foreclosure): parcel 31-05-18-00-000-0101-2,
--     auction_date 08/13/2026, status SCHEDULED -- fetch1=match fetch2=match
--   UNION-TD-CERT223 (tax deed): cert #223, parcel 32-05-20-22-018-0022-0,
--     auction_date 03/12/2026, status SCHEDULED -- fetch1=match fetch2=match
-- All 3 promoted to parity_status='matched_clean',
-- parity_source='tier1:union_clerk_live_20260711'.
--
-- CERT223 OUTCOME RE-CHECK (task step 2 -- was it sold/redeemed/cancelled?):
-- Fresh re-check this session (2026-07-11), independent of and consistent
-- with the prior same-day investigation in
-- scripts/shard10_run3645_union_b_cert223.py:
--   1. unionclerk.com/tax-deed-sales/ STILL lists cert #223 as SCHEDULED /
--      03/12/2026 (~4 months past due) -- page carries no won/sold/redeemed
--      vocabulary, forward-looking listings only.
--   2. unionclerk.com/departments-services/clerk-services/
--      list-of-lands-available/ -- still empty ("no properties on the list
--      of lands available at this time") in both fetches. Absence from LAFT
--      means cert #223 did NOT go unsold, but does not distinguish sold vs.
--      redeemed, and gives no dollar amount.
--   3. unioncountytc.com (Tax Collector) homepage + /Property/TaxCertificates
--      page: no cert-status lookup tool, no sale-result page. Contact-only
--      (386-496-3331 / lisabj65@unioncountytc.com).
--   4. Web search located the original pre-sale legal notice (Union County
--      Telegraph, published 2026-02-26): Certificate #223, issued 2018,
--      parcel 32-05-20-22-018-0022-0 (SW 1/4 Lot 2, Block 18, J.W.
--      Townsend's addition, Plat Book 1 Pg 8), assessed owners Porsha T.
--      Ridgeway and Harmon Ridgeway III, cert holder J.R. Davis Trustee of
--      the J.R. Davis Trust, scheduled for courthouse-lobby sale 03/12/2026
--      "unless redeemed beforehand." This is the PRE-sale notice -- no
--      post-sale result was found anywhere (search results, clerk site, tax
--      collector site).
--   5. union.floridapa.com/GIS/ parcel search and unioncountytc.com/Property/
--      Search are both JS-driven forms this session's tooling (WebFetch,
--      matching the prior session's Playwright attempt) could not drive to
--      a result -- a genuine tooling limitation, not a decision to skip.
-- CONCLUSION: no source found in this session (or the prior same-day
-- session) states a sold_amount, buyer, or redemption for cert #223. B/F
-- are correctly LEFT FAILING -- writing sold_amount here would be
-- fabrication (HARD GUARDRAIL: never fabricate amounts). This is a genuine,
-- disclosed data gap, not a defect in the pipeline.
--
-- pencil_dod_evaluate_county('union') before/after (applied live via
-- Supabase Management API + PostgREST; this file documents the change for
-- replay):
--   A: fc=2 td=1 (PASS, unchanged)
--   B: verified=0 closed_sold=0 (FAIL, unchanged -- no real sale amount available, correctly left untouched)
--   C: matched_clean=0 of 3 (0.0% FAIL) -> matched_clean=3 of 3 (100.0% PASS)
--   D: matched_any=0 of 3 (0.0% FAIL)   -> matched_any=3 of 3 (100.0% PASS)
--   E: parcel_linked=3 of 3 (100.0% PASS, unchanged)
--   F: tier1_sold=0 closed_sold=0 (FAIL, unchanged -- same reason as B)
--   G: density=100.0 (PASS, unchanged)
--   H: hours since last_seen (PASS, unchanged/improved by the parity PATCH touching last_seen_at)
--   I: card_complete=3 of 3 (100.0% PASS, unchanged)
--   J: deal_complete=3 of 3 (100.0% PASS, unchanged)
-- union 6/10 -> 8/10 (A,C,D,E,G,H,I,J pass; B,F still fail, honestly).
--
-- Verified with: SELECT public.pencil_dod_evaluate_county('union');
-- Script: scripts/shard_union_cd_doublefetch_cert223_recheck.py

UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:union_clerk_live_20260711',
    parity_checked_at = now(),
    last_seen_at = now(),
    updated_at = now()
WHERE lower(county) = 'union'
  AND case_number IN ('63-2024-CA-0047', '63-2025-CA-0053', 'UNION-TD-CERT223');
