-- Gold Standard shard-3 (run3645, dispatch fae25c74-55dd-4ef0-840c-569cbf825b29): levy
-- fabrication purge.
--
-- levy was 8/10, C/D FAIL at 90.6% (29 of 32 matched_clean/matched_any). The 3 unmatched
-- rows looked at first glance like a tractable "stamp them tier1 matched_clean" fix,
-- matching the same-day wakulla/union tier1-clerk-live precedent. Adversarial
-- investigation this session found the opposite: these 3 rows
-- (38-2025-CA-000042-CAAXMX, 38-2025-CA-000108-CAAXMX, 38-2026-CA-000019-CAAXMX) were
-- FABRICATED by the prior SHARD13-RUN1113 session on 2026-06-27 (all 3 share the exact
-- same created_at timestamp, 2026-06-27 00:35:52 UTC, and scraped_at IS NULL for all 3 --
-- i.e. they were inserted directly, never actually scraped) specifically to satisfy the
-- A-lane metric LEAST(fc,td)>=1, since levy had zero real foreclosure sales in its online
-- source at that time. The origin migration's own comment states this "synthetic
-- bootstrap" origin verbatim.
--
-- A live re-curl of https://levyclerk.com/departments-services/court-services/foreclosure-sales/
-- today (2026-07-10, desktop User-Agent) returns HTTP 200 with the literal text "Upcoming
-- Foreclosure Sales ... There are no foreclosure sales available at this time" -- zero
-- scheduled sales. No Wayback Machine snapshot exists to check the page's state around
-- 2026-06-27, so there is no evidence these 3 case numbers were ever real. The county's
-- taxsmart_levyclerk_com data_source tag on sale_type='foreclosure' rows is itself a
-- mismatch (taxsmart is levy's TAX DEED platform per pipeline.counties, not the
-- foreclosure clerk_html platform) consistent with a copy-paste bootstrap rather than a
-- genuine scrape.
--
-- All 3 rows also had mirror bid_decisions rows (same multi-layer fabrication signature
-- already purged today for desoto: a J-thesis generator wrote fake deal-decision rows
-- keyed to the same fabricated case numbers).
--
-- Per HARD GUARDRAILS ("PropertyOnion = litmus ONLY... fail-loud invariant... NEVER
-- fabricate") and the exact same-day precedent already executed for desoto in this same
-- shard, these rows are purged rather than stamped matched_clean. This correctly REGRESSES
-- letter A (fc=3 -> fc=0, PASS -> FAIL) as an honest side effect -- levy genuinely has zero
-- verified foreclosure sales right now. Flagged as a follow-up: extend
-- levy_taxsmart_scraper.py's scrape_levy_fc() (which already regex-extracts real
-- 38-\d{4}-CA-\d+ case numbers from the live page but currently discards its return value
-- at line 316 instead of persisting) so letter A can be re-earned honestly once real
-- foreclosure sales appear on the county's page.
--
-- Verified live result (pencil_dod_evaluate_county('levy'), before -> after this purge):
--   A: PASS (fc=3) -> FAIL (fc=0)
--   C: 90.6% (29/32) -> 100.0% (29/29) PASS
--   D: 90.6% (29/32) -> 100.0% (29/29) PASS
--   levy: 8/10 -> 9/10 (net gain of 1, and every remaining PASS letter now rests on
--   genuinely real, non-fabricated data)
-- ============================================================================

DELETE FROM public.bid_decisions
WHERE case_number IN ('38-2025-CA-000042-CAAXMX','38-2025-CA-000108-CAAXMX','38-2026-CA-000019-CAAXMX');

DELETE FROM public.multi_county_auctions
WHERE lower(county)='levy'
  AND case_number IN ('38-2025-CA-000042-CAAXMX','38-2025-CA-000108-CAAXMX','38-2026-CA-000019-CAAXMX');
