-- SHARD-9 (this session's assigned county: holmes): pipeline.counties taxdeed metadata
-- correction + full C/D/B/F re-verification audit (no score-moving fix found honest to make).
-- dispatch_id: ddbb047c-3aca-44b8-821a-58a26d127732
--
-- BASELINE (re-verified live via pencil_dod_evaluate_county('holmes') before any change):
--   6/10 -- A,E,G,H,I,J PASS. B=null (verified=0 closed_sold=0), C=61.5% (matched_clean=8 of 13),
--   D=61.5% (matched_any=8 of 13), F=null (tier1_sold=0 closed_sold=0).
--
-- C/D INVESTIGATION (independently re-verified, not just trusted from prior session notes):
-- Live-fetched https://holmesclerk.com/courts/foreclosures-tax-deeds/tax-deeds/ (HTTP 200,
-- "Updated 7/9/2026") today (2026-07-11). Current live TD listing: TD#2023-330, TD#2023-509,
-- TD#2020-349, TD#2023-753, TD#2024-185 -- exactly the 5 already carrying
-- parity_source='tier1:holmes_clerk_live_%%' in our DB (4 from the 2026-07-10 shard11-run3497
-- fix + 1 from the same-day shard12-run3534 harvest). The 5 still-unmatched rows
-- (TD#2023-185, TD#2020-589, TD#2023-496, TD#2023-225, TD#2023-584) do NOT appear on the live
-- page at all -- genuinely rolled off, not a matching-key bug. holmesclerk.com has no
-- case-search or disposition/results tool (confirmed by listing every <a href> on both pages:
-- only qpublic.schneidercorp.com property-appraiser links, no results page). "Lands Available
-- for Taxes" page re-checked live: still explicitly "NO LOLA FILES AT THIS TIME". Conclusion:
-- C/D cannot honestly move further from this source today. RESIDUAL, not a scraper bug.
--
-- B/F INVESTIGATION: all 13 holmes rows have sold_amount IS NULL (closed_sold=0), which is why
-- B and F both report a null metric (0/0 denominator) rather than a real percentage. The one
-- 'completed' auction_status row (HOLMES-LEGACY-123a1bd5-1ea3-4bb4-98ad-a7fc86853e49, foreclosure,
-- auction_date 2026-06-11) DOES have a real, previously-vetted foreclosure_outcomes row
-- (data_source='holmes_clerk_direct', source_url=holmesclerk.com/.../foreclosures/, kept as
-- genuine by the 2026-07-04 shard9 ghost-success-revert migration after 11 sibling rows were
-- purged as fabricated) -- but that outcome row's winning_bid is NULL, and multi_county_auctions
-- .sold_amount is also NULL for this case. Independently re-fetched the live foreclosure page
-- this session: the Gillis case (parcel 1626.00-000-000-011.000) is STILL listed under
-- "Upcoming Foreclosure Sales" (last "UPDATED: 06/16/2026"), a full month after its own
-- 2026-06-11 sale date, with no SOLD/disposition marker anywhere on the page. holmesclerk.com
-- structurally has no results/disposition page for any case (verified again this session,
-- same conclusion as 2026-07-10 shard12-run3534). Whether outcome='sold' (set 2026-06-25) on
-- the existing foreclosure_outcomes row is even accurate cannot be independently confirmed from
-- any source available in this pass, and no real winning_bid/sold_amount exists anywhere to
-- backfill. Per the fail-loud invariant and this county's own documented fabrication history
-- (2026-07-04 ghost-success purge of 11 rows), sold_amount/winning_bid are NOT written here.
-- B/F remain a genuine, currently-unmeasurable gap for holmes -- not fixed, not fabricated.
--
-- WIRING GAP (found, documented, NOT built in this bounded pass): the C/D harvest script
-- scripts/shard12_run3534_holmes_clerk_cd_bf_harvest.py is not referenced by any GHA workflow
-- (grepped .github/workflows/ for the script name and for "holmes" inside gold-standard-shard12
-- .yml -- zero matches) and cron.job has zero rows matching '%%holmes%%' (confirmed via live
-- SQL). It has only ever been run ad hoc. Given today's live re-fetch shows there is currently
-- nothing further for it to harvest (all 5 unmatched TD# cases have rolled off with no
-- disposition source), scheduling it this pass would not move any score -- sized here as a
-- residual for a future session: wire it into gold-standard-shard12.yml (or a new
-- holmes-specific job) on a daily/weekly cadence so future roll-ons to the live TD/FC pages are
-- picked up automatically instead of relying on ad hoc runs.
--
-- REAL FIX APPLIED THIS SESSION (metadata hygiene, does not move any pencil_dod letter):
-- pipeline.counties.taxdeed_platform/taxdeed_url for holmes were still stale
-- ('realtaxdeed' / https://holmes.realtaxdeed.com) despite the 2026-07-10 shard11-run3497
-- migration's stated intent to correct both foreclosure_platform AND taxdeed_platform to
-- clerk_html/holmesclerk.com -- live DB showed only the foreclosure_platform side had actually
-- persisted. Independently re-verified holmes.realtaxdeed.com live this session: HTTP 403
-- (dead/unprovisioned RealAuction tenant), confirming the stale value was wrong. Corrected
-- taxdeed_platform/taxdeed_url to match reality (clerk_html / holmesclerk.com tax-deeds page),
-- consistent with foreclosure_platform, so future sessions don't re-waste time probing a dead
-- RealAuction subdomain for tax deeds specifically.
--
-- AFTER (re-verified live via pencil_dod_evaluate_county('holmes') post metadata fix):
-- unchanged, 6/10 -- A,E,G,H,I,J PASS; B,C,D,F still FAIL. Confirmed expected: this fix touches
-- pipeline.counties only, a metadata table not read by the evaluator.
--
-- No multi_county_auctions rows were modified. No outcome rows were modified. No case numbers,
-- parcel IDs, sale amounts, or timestamps were fabricated.

UPDATE pipeline.counties
SET taxdeed_platform = 'clerk_html',
    taxdeed_url = 'https://holmesclerk.com/courts/foreclosures-tax-deeds/tax-deeds/',
    notes = COALESCE(notes, '') || ' | 2026-07-11 shard9-run(db7f8292): VERIFIED live holmes.realtaxdeed.com returns HTTP 403 (dead/unprovisioned RealAuction tenant, confirmed again). taxdeed_platform/taxdeed_url were still stale post the 2026-07-10 shard11 fix (foreclosure side updated, taxdeed side did not persist) -- corrected taxdeed_platform/taxdeed_url to clerk_html/holmesclerk.com tax-deeds page to match foreclosure_platform and reality. No pencil_dod letter affected (metadata-only, not read by evaluator).'
WHERE lower(county_slug) = 'holmes';

-- ── ULTRALOOP audit trail ──
INSERT INTO public.gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
VALUES
  ('ddbb047c-3aca-44b8-821a-58a26d127732', 'fallback', 'holmes', 'C',
   'holmes C: matched_clean=8 of 13 (61.5%), unchanged this session -- 5 unmatched TD# cases confirmed genuinely rolled off the live holmesclerk.com tax-deed page, not a matching-key bug',
   '{"verdict":"CONFIRMED_RESIDUAL","method":"independent live HTTP fetch of https://holmesclerk.com/courts/foreclosures-tax-deeds/tax-deeds/ this session (HTTP 200, page marked Updated 7/9/2026)","live_td_cases":["TD#2023-330","TD#2023-509","TD#2020-349","TD#2023-753","TD#2024-185"],"unmatched_db_cases_checked":["TD#2023-185","TD#2020-589","TD#2023-496","TD#2023-225","TD#2023-584"],"result":"zero overlap between live page and unmatched DB cases -- confirmed rolled off, not fixable from this source today"}'::jsonb,
   true),
  ('ddbb047c-3aca-44b8-821a-58a26d127732', 'fallback', 'holmes', 'D',
   'holmes D: matched_any=8 of 13 (61.5%), unchanged -- same root cause as C',
   '{"verdict":"CONFIRMED_RESIDUAL","evidence":"same live re-fetch as C finding"}'::jsonb,
   true),
  ('ddbb047c-3aca-44b8-821a-58a26d127732', 'fallback', 'holmes', 'B',
   'holmes B: verified=0 closed_sold=0 (null metric), unchanged -- no real sold_amount/winning_bid obtainable from any available source, not written',
   '{"verdict":"CONFIRMED_RESIDUAL","evidence":"the one completed-status case (HOLMES-LEGACY-123a1bd5) has a genuine foreclosure_outcomes row (data_source=holmes_clerk_direct, kept as real by the 2026-07-04 ghost-success-revert migration after 11 sibling rows were purged as fabricated) but winning_bid is NULL; independently re-fetched holmesclerk.com/courts/foreclosures-tax-deeds/foreclosures/ live this session -- the case is STILL listed under Upcoming Foreclosure Sales a month after its 2026-06-11 sale date, no disposition/results page exists anywhere on the site (checked every link). Fabricating a sold_amount was explicitly avoided given this countys documented 2026-07-04 fabrication history."}'::jsonb,
   true),
  ('ddbb047c-3aca-44b8-821a-58a26d127732', 'fallback', 'holmes', 'F',
   'holmes F: tier1_sold=0 closed_sold=0 (null metric), unchanged -- same root cause as B',
   '{"verdict":"CONFIRMED_RESIDUAL","evidence":"same live re-fetch as B finding; tier1_sold_amount requires sold_amount to be non-null first, which is not honestly obtainable"}'::jsonb,
   true),
  ('ddbb047c-3aca-44b8-821a-58a26d127732', 'fallback', 'holmes', 'H',
   '[metadata-only, no letter-score impact] pipeline.counties.taxdeed_platform/taxdeed_url for holmes corrected from stale realtaxdeed/holmes.realtaxdeed.com to clerk_html/holmesclerk.com tax-deeds page; scripts/shard12_run3534_holmes_clerk_cd_bf_harvest.py confirmed NOT wired to any GHA workflow or cron.job -- flagged as residual for a future session, not built this pass since no further data is currently harvestable',
   '{"verdict":"REAL_METADATA_FIX_NO_SCORE_IMPACT","evidence":"holmes.realtaxdeed.com returned HTTP 403 when curled live this session (dead RealAuction tenant, same conclusion as shard11-run3497 2026-07-10 for the foreclosure subdomain); confirmed via grep of .github/workflows/ and a live cron.job query (SELECT ... WHERE command ILIKE %holmes% OR jobname ILIKE %holmes% returned zero rows) that the harvest script has no scheduled execution path"}'::jsonb,
   true);
