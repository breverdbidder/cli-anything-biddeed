-- SHARD-8 run2886: lafayette H (freshness) honest diagnosis + pipeline.counties wiring
-- dispatch_id: 0b518e79-822d-473f-ae19-1362c72bf9be
-- Session: architect-shard8-run2886
--
-- APPLIED LIVE via PostgREST during this session (no exec_sql/DDL RPC reachable on
-- this project for pipeline.counties updates -- same constraint documented in prior
-- shard migrations). This file is the historical record of that live UPDATE.
--
-- ═══════════════════════════════════════════════════════════════════════════════
-- CONTEXT: lafayette entering this shard was 9/10, only H (freshness) failing at
-- 55.4h (re-verified live this session: 56.1h). The task asked to (a) re-verify the
-- real-world status of the 2 existing multi_county_auctions rows and refresh
-- last_seen_at with a REAL check, and (b) wire pipeline.counties correctly so this
-- doesn't recur.
--
-- FINDING (RE-CONFIRMS a prior shard's GHOST-SUCCESS diagnosis, dispatch_id
-- a22499ac-311b-4b6d-ad24-5d9422b2cee2, gold_standard_ultraloop_audit
-- county_slug=lafayette letter=F, created_at 2026-07-02): the 2 lafayette rows in
-- multi_county_auctions (case_number LAFAYETTE-FC-SEED-2026 /
-- LAFAYETTE-TD-SEED-2026, parcel_id SYN-LAF-FC-001 / SYN-LAF-TD-001) are entirely
-- SYNTHETIC seed rows created 2026-06-25 by scripts/shard1_lafayette_bootstrap.py
-- (see that script's own docstring: "HYPOTHESIS: Pipeline configured; real auctions
-- pending first live scrape") and later patched to auction_status=completed/sold
-- with INFERRED median dollar amounts ($45,000/$25,000) by
-- scripts/shard12_run1113_lafayette_bf.py, which explicitly documents these as
-- "INFERRED: Lafayette County FL tiny rural market... generous estimates."
-- These case numbers do NOT correspond to any real Lafayette County court case.
--
-- Because the case numbers are fabricated, there is no real source to "re-verify
-- their current status" against -- the fabricated case never existed to check.
-- Per guardrail #6 (never fabricate rows/ghost-success) and the explicit
-- instruction that a fake timestamp bump is not acceptable, last_seen_at was left
-- UNCHANGED. H genuinely fails and this is disclosed, not patched.
--
-- INDEPENDENT LIVE RE-VERIFICATION performed this session (2026-07-04, all three
-- confirm the prior shard's finding still holds with fresh network conditions):
--   1. curl -A <chrome-UA> https://lafayette.realforeclose.com/index.cfm?zaction=USER&zmethod=CALENDAR
--        -> HTTP 302 -> http://www.realauction.com/ (148-byte "Object Moved" body,
--        generic marketing splash, NOT a county calendar). Same result for
--        .../index.cfm?zaction=AUCTION&Zmethod=RESULTS&StatusType=S&bypassPage=1.
--   2. Same pattern against lafayette.realtaxdeed.com -> identical 302 to
--        www.realauction.com.
--      Control comparison: martin.realforeclose.com with the IDENTICAL request
--      pattern returns HTTP 200 with 25,146 bytes of real calendar content,
--      proving the redirect is lafayette-subdomain-specific (unprovisioned
--      tenant), not a network-wide block.
--   3. lafayette.realtdm.com returns HTTP 200 but with page text "county-info ->
--      TEST", "Test Clerk" -- confirmed RealAuction demo/sandbox tenant, not
--      real Lafayette County data. Matches realauction_subdomains.notes exactly.
--   4. NEW THIS SESSION: fetched the real Lafayette County Clerk of Court site
--      (www.lafayetteclerk.com), which has genuine Foreclosure Sales and Tax Deed
--      Sales pages. Both currently read "There are no foreclosure sales available
--      at this time." / "There are no properties on the list of tax deeds at this
--      time." Sales are conducted IN-PERSON on the courthouse steps (120 West Main
--      Street, Mayo FL), advertised in the local newspaper -- no online
--      RealAuction/LienHub/GovEase platform is provisioned for this tiny
--      (pop. ~8,500) county. This matches the exact "clerk_inperson" pattern
--      already used for union county (pipeline_status=blocked,
--      foreclosure_platform=clerk_inperson) -- see migration
--      20260703_shard9_union_clerk_realdata_okeechobee_td_extension_indian_river_reconcile.sql.
--
-- ACTION TAKEN: pipeline.counties for lafayette updated from the misleading
-- pipeline_status='pending' (implies "not yet configured", inviting a future
-- shard to assume a scrape just needs to be run) to pipeline_status='blocked'
-- (honest: real source identified, but it is a manual/in-person process with no
-- scrapeable online calendar or historical archive). foreclosure_platform set to
-- 'clerk_inperson' with foreclosure_url pointing at the real, live, VERIFIED
-- clerk foreclosure-sales page (not a fabricated RealAuction URL). No
-- taxdeed_platform/taxdeed_url distinct URL is set separately since the same
-- clerk site serves both under one domain; taxdeed_platform/taxdeed_url are set
-- to the analogous real tax-deed-sales page for symmetry with the union pattern.
-- last_scrape_at / last_successful_scrape_at intentionally left NULL: no
-- automated scraper exists for this manual/in-person process. pipeline_health
-- left 'inactive' (accurate -- no working automated pipeline).
--
-- H WILL CONTINUE TO FAIL until either (a) a real historical archive of past
-- Lafayette sales is found to replace the 2 fabricated seed rows with real
-- outcomes (none found this session across clerk site, realforeclose,
-- realtaxdeed, realtdm, myfloridacounty.com/orisearch which returned HTTP 403),
-- or (b) the campaign adopts a documented exception policy for genuinely-manual
-- tiny counties (no such exception table/policy exists yet in this schema --
-- out of scope for a single-county shard to invent unilaterally).
--
-- NOT DONE (honestly flagged): the 2 fabricated seed rows were NOT deleted/reverted
-- in this migration. Guardrail #7 restricts this shard to lafayette's own rows/files,
-- and guardrail #6 forbids fabrication but a full purge-and-revert of a prior
-- shard's already-disclosed seed rows (which currently hold A/C/D/E/F/G/I/J passing)
-- is a larger decision than "fix H" and was left untouched this session pending
-- an explicit purge decision, consistent with how the prior shard (a22499ac) also
-- left them in place with disclosure rather than unilaterally deleting them.

UPDATE pipeline.counties
SET
  foreclosure_platform = 'clerk_inperson',
  foreclosure_url = 'https://www.lafayetteclerk.com/departments-services/court-services/foreclosure-sales/',
  taxdeed_platform = 'clerk_inperson',
  taxdeed_url = 'https://www.lafayetteclerk.com/departments-services/clerk-services/tax-deeds/',
  pipeline_status = 'blocked',
  pipeline_health = 'inactive',
  notes = 'Auto-seeded 2026-05-20 from realauction_subdomains during SSOT-completion sweep | 2026-07-02 shard6: multi_county_auctions has ONLY 2 rows for lafayette (LAFAYETTE-FC-SEED-2026, LAFAYETTE-TD-SEED-2026), both synthetic seeds created 2026-06-25, zero real scrape ever run. lafayette.realtdm.com resolves to a REALAUCTION TEST/DEMO TENANT (page shows county=TEST, Test Clerk), not real county data. realforeclose/realtaxdeed subdomains both is_active=false. Gold-standard PASS for this county rests partly on fabricated seed rows -- see gold_standard_ultraloop_audit county_slug=lafayette letter=F (dispatch a22499ac, 2026-07-02, GHOST-SUCCESS confirmed) and letter=H (dispatch a22499ac, restamp claim corrected). | 2026-07-04 shard8 run2886 (dispatch 0b518e79): RE-VERIFIED live -- lafayette.realforeclose.com and lafayette.realtaxdeed.com both 302-redirect to www.realauction.com generic marketing splash (control-compared against martin.realforeclose.com which returns real 200 content on the identical request pattern, proving this is an unprovisioned-tenant issue not a network block). realtdm.com TEST-tenant finding reconfirmed. NEW: fetched real www.lafayetteclerk.com Foreclosure Sales + Tax Deed Sales pages -- both currently show zero upcoming sales; sales are conducted IN-PERSON on the courthouse steps (120 West Main St, Mayo FL), advertised in local newspaper legal ads, no online bidding platform provisioned for this pop-8,500 county. pipeline_status corrected pending->blocked (was misleadingly implying "not yet configured"; real situation is a manual/in-person process with no scrapeable calendar), foreclosure_platform/taxdeed_platform set to clerk_inperson with real verified clerk URLs, matching the union county pattern (see migration 20260703_shard9_union_clerk_realdata_okeechobee_td_extension_indian_river_reconcile.sql). H (freshness) NOT fixed this session -- the 2 existing auction rows are fabricated seeds with no real case behind them to re-verify; last_seen_at intentionally left unchanged rather than fake-bumped. DO NOT certify H PASS until either a real historical sale archive is found or a documented county-exception policy exists.'
WHERE county_slug = 'lafayette';
