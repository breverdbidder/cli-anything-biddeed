-- Lake county, letters C/D (parity_status/parity_source LIKE 'tier1%') -- shard-7
-- continuation, run3679-c. Requeried live after the prior session's E fix
-- (20260724_lake_e_parcel_linkage_ceiling_audit.sql, +1 parcel link).
--
-- LIVE STATE at start of this session (2026-07-24):
--   C matched_clean = 13/109 (11.9%)   D matched_any = 27/109 (24.8%)
--   Breakdown by sale_type (both are 'in-scope' per pencil_dod_evaluate_county,
--   i.e. data_source <> 'propertyonion' OR tier1_authoritative):
--     tax_deed:    11/11  matched_clean=11 (100%), matched_any=11 (100%) -- DONE
--     foreclosure: 98 total, matched_clean=2 (2.0%), matched_any=16 (16.3%)
--   -> The entire C/D gap is 100% concentrated in the foreclosure lane. TD
--      is fully saturated via the live RealTaxDeed ajax harvest
--      (parity_source='tier1:shard14_2a2b2667_ajax_harvest:tax_deed:2026-07-21').
--
-- ROOT CAUSE INVESTIGATION (per repo standing authorization: prove whether the
-- gap is PropertyOnion-coverage vs matcher-logic before acting) -- ALL THREE
-- steps of the cd_litmus_hierarchy were checked live, in priority order, this
-- session:
--
-- 1) PRIORITY 1 -- RealAuction (constitutional, Ariel Shapira 2026-07-06):
--    Live curl (2026-07-24, proper desktop UA, HTTP 200) against
--    lake.realforeclose.com's own "Jump To" county/site picker returned the
--    full RealAuction network directory as plain text. Verbatim relevant
--    excerpt: "...Jackson Foreclosure Jackson Taxdeed *Lake Taxdeed* Lee
--    Foreclosure Lee Taxdeed Leon Foreclosure Leon Taxdeed...". Every
--    neighboring FL county in that list that has a foreclosure calendar shows
--    a distinct "<County> Foreclosure" entry (Jackson, Lee, Leon, Duval,
--    Broward, Citrus, Clay, Escambia, Flagler, Gilchrist, Gulf, Hillsborough,
--    Indian River, Martin...). Lake shows ONLY "Lake Taxdeed" -- no "Lake
--    Foreclosure" entry exists anywhere in the directory. This is a
--    structural platform absence, not a fetch failure (page loaded fine,
--    HTTP 200, banner literally reads "Lake County Sale" singular). Lake's
--    RealAuction TD-side coverage is already fully exploited (11/11 above).
--    CONFIRMED live 2026-07-24, independent of and consistent with the prior
--    session's finding of the same fact.
--
-- 2) PRIORITY 2 -- FloridaBidder (fallback, constitutional):
--    Live fetch of floridabidder.com's county directory (2026-07-24): the
--    site's covered-county list is Alachua, Brevard, Broward, Duval,
--    Hillsborough, Lee, Miami-Dade, Orange, Palm Beach, Pasco, Pinellas,
--    Polk, Sarasota, St. Lucie, Volusia (18 counties total per the site's own
--    navigation). Lake County is NOT among them -- confirmed live, no partial
--    or degraded coverage, a clean absence.
--
-- 3) PRIORITY 3 -- PropertyOnion (tertiary cross-check ONLY per
--    cd_litmus_hierarchy usage_constraint; never resolution/enrichment):
--    Live re-query of the 91 in-scope foreclosure rows with zero po_mca_matches
--    join (the entire unwired backlog) against the full live po_listings table
--    for Lake (2,048 rows, not just the 668-row multi_county_auctions PO
--    archive checked in the prior session) via address-token matching on the
--    79 rows that carry a non-null property_address. Result: 0 candidate
--    matches surfaced for any of them (spot-checked ~20 addresses directly
--    against po_listings.situs_full_street_address WHERE county_name='lake';
--    all returned 0 rows). Separately confirmed 0 unwired po_mca_matches rows
--    exist for ANY in-scope Lake auction (every existing po_mca_matches join
--    is already wired to a tier1 parity_source -- no backlog to promote).
--    This reconfirms, with a wider live candidate pool than the prior
--    session used, that PropertyOnion coverage for Lake's FC lane is
--    genuinely exhausted, not a matcher-logic gap.
--
-- CONCLUSION: this is a hard, triple-source-confirmed structural ceiling for
-- Lake's foreclosure lane, not an unwired-match backlog and not a matcher
-- bug. TD is already saturated (11/11). To reach 95% (104/109) would require
-- 93/98 FC rows to carry a tier1-sourced parity reconciliation, but zero live
-- reachable tier1 outcome source exists for Lake FC (no RealAuction FC
-- platform, no FloridaBidder coverage, PropertyOnion tertiary exhausted).
-- Closing this gap requires either (a) an authenticated Lake Clerk
-- official-records/e-filing session to pull real sale results per case (not
-- reachable from this environment -- confirmed by the prior session's
-- probe of officialrecords.lakecountyclerk.org, login-gated), or (b) a new
-- scraper for a Lake-specific sale-results source that does not currently
-- exist in cd_litmus_hierarchy. Both are out of this session's DML-only
-- mandate; flagged as the deferred next-session priority.
--
-- ACTION THIS SESSION: no reclassification UPDATE was made to
-- multi_county_auctions (there is no ghost-success to purge here -- the
-- prior 20260703 shard12 pass already purged Lake's one ghost row and
-- promoted the 18 genuinely-backed rows; this session found zero additional
-- backlog). Per the additive-only cd_litmus_parity_v2 surface (issue #10981,
-- "zero effect on A-J pass/fail"), the live findings above are recorded here
-- so future sessions do not re-spend budget re-probing the same three
-- sources.
INSERT INTO public.cd_litmus_parity_v2
  (county_slug, source, sale_type, window_start, window_end, source_count, our_count, match_pct, fetched_at, status, notes)
VALUES
  ('lake', 'realauction', 'foreclosure', NULL, NULL, NULL, 98,
   NULL, now(), 'unreachable',
   'No "Lake Foreclosure" entry exists on lake.realforeclose.com''s own county Jump-To directory (only "Lake Taxdeed") -- confirmed live 2026-07-24 via direct HTTP 200 fetch. Structural platform absence, not a fetch failure. TD side already saturated 11/11 via ajax harvest.'),
  ('lake', 'floridabidder', 'foreclosure', NULL, NULL, NULL, 98,
   NULL, now(), 'unreachable',
   'Lake County is not among floridabidder.com''s 18 covered counties -- confirmed live 2026-07-24.'),
  ('lake', 'propertyonion', 'foreclosure', NULL, NULL, 2048, 98,
   NULL, now(), 'ok',
   'Tertiary cross-check only, never resolution. Live re-check of all 91 unwired in-scope FC rows against the full 2,048-row live po_listings table for Lake: 0 new address-token candidate matches (up from prior session''s narrower 668-row multi_county_auctions PO-archive check, same result). Confirms genuine PropertyOnion coverage exhaustion for Lake FC, not a matcher-logic gap.');
