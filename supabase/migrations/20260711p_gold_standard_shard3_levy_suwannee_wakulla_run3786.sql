-- GOLD STANDARD shard-3 (levy/suwannee/wakulla), dispatch b80c4c55-8ad7-41fb-86de-a1b33ecc95d5, run3786.
-- ULTRALOOP: 3 research agents fanned out via Workflow tool, each followed by an independent adversarial
-- refuter agent. 2 of 3 findings survived (levy A, wakulla E); wakulla G correctly returned UNKNOWN/no-write.
-- All 3 logged to gold_standard_ultraloop_audit (ids 5879-5881). Applied live via Supabase Management API
-- SQL endpoint (psql/pooler auth unreachable from this sandbox this session, same as several same-day
-- sessions before it) and PostgREST; this file documents the change for replay/audit.
--
-- BASELINE (pencil_dod_evaluate_county, verified live before any work):
--   levy:     9/10 -- A FAIL fc=0/td=29. Everything else already PASS.
--   suwannee: A/B/F FAIL (fc=0, closed_sold=0/9) -- everything else already PASS (shard11/run3679 fixed
--             this earlier today: I 81.8%->100%, confirmed A genuinely blocked).
--   wakulla:  A/H/C/D/J PASS. B/F FAIL (null, 0 closed sales -- all 30 rows are future auction_date, no
--             sale has occurred yet). E FAIL 76.7% (23/30). G FAIL 0.0% (zone_code linked for 20 parcels
--             via a same-day prior session's real ArcGIS ZoningWakulla fetch, but zero have a sourced
--             max_density_du_acre). I FAIL 0.0% (0/30 -- property_address/lat/lon/value all NULL).
--
-- === LEVY A -- re-verified genuinely blocked, metadata corrected, NO metric movement possible ===
-- pipeline.counties had foreclosure_platform='clerk_html', pipeline_health='inactive' with notes
-- "Auto-seeded 2026-05-20 ... never scraped" -- i.e. nobody had actually checked this lane live before.
-- This session fetched levyclerk.com/departments-services/court-services/foreclosure-sales/ directly (2x)
-- and the parent court-services page: the site explicitly states "There are no foreclosure sales available
-- at this time" and points to newspaper classifieds, not a scrapable list. A dispatched research agent then
-- tried 6 further avenues to find anything the operator missed: floridapublicnotices.com (found exactly one
-- real Levy notice site-wide, Case 2025000075CAAXMX, sale date 04/20/2026 -- already PAST relative to today
-- 2026-07-11, so not "upcoming"); a newly-discovered levy.agverso.com Auto-Graphics "Records Manager"
-- Angular/SignalR SPA (live, HTTP 200, but every probed API path returns the identical client-side shell --
-- no server-rendered data reachable without a headless browser, which this sandbox does not have); Levy's
-- Civitek OCRS instance (same JSF/PrimeFaces session-token wall documented for other counties); circuit8.org
-- procedural pages (no case list); and the Levy County Citizen newspaper chain (dead ends). An independent
-- adversarial refuter agent re-fetched every one of these sources itself and reproduced the same results
-- (one minor imprecision flagged and corrected below: the floridapublicnotices.com page is still live via
-- GET/200, only a bare HEAD request 500s -- irrelevant to the "already past" conclusion either way).
-- CONCLUSION: A remains an honest FAIL (fc=0) -- this is a real, verified zero, not a scraper gap, same
-- pattern as suwannee. pipeline_health corrected from a false 'inactive' to 'healthy' with an honest note.
-- RESIDUAL: levy.agverso.com is a genuinely new, unblocked-by-prior-sessions lead for a future session with
-- browser automation (Playwright/browser-use/Firecrawl) -- worth targeting directly, not re-probing via curl.
--
-- === WAKULLA E -- 76.7% (23/30) -> 83.3% (25/30), REAL fix ===
-- 7 wakulla rows had parcel_id IS NULL. Case 2026-TXD-097 is a REDEEMED tax deed (no deed ever issued, no
-- parcel ever attaches to the sale record) -- permanently un-linkable, left untouched. The other 6 are real
-- live foreclosure cases from wakullaclerk.org/courts/foreclosures.php, which lists case#/plaintiff/
-- defendant/date/judgment but NOT parcel/address. A same-day prior session (shard13/run3713) already tried
-- and exhausted the two authoritative Wakulla Property Appraiser hosts (qpublic.schneidercorp.com: HTTP 403
-- WAF; search.mywakullapa.com: TCP connection reset) via curl, WebFetch, AND real headless Chromium -- this
-- session's research agent was explicitly told not to re-attempt those two hosts.
-- NEW SOURCE FOUND: wakullacountytaxcollector.com (a live, unblocked ASP.NET/VisualGov tax-collector site,
-- distinct from the property appraiser) exposes a POST /Property/search owner-name lookup returning
-- PROPERTYNO + situs address. Exact-name matches were found for 2 of 6 defendants:
--   Huy Ngoc Nguyen  (case 25-CA-106) -> parcel 00-00-055-422-19932-088, 20 Springdale Dr, Crawfordville FL
--   Ciara D. Adams   (case 24-CA-105) -> parcel 25-2S-02W-000-01425-003, 180 Hilliardville Rd, Crawfordville FL
-- Both independently reproduced twice: once by an adversarial refuter agent (which also cross-checked each
-- case's plaintiff/judgment_amount against wakullaclerk.org/courts/foreclosures.php and confirmed an exact
-- match to the existing DB rows), and again by the operator via a fresh curl POST immediately before writing
-- (same PROPERTYNO/address/tax-bill-number returned both times).
-- The other 4 defendants were correctly NOT resolved and NOT written, per the same rigor:
--   Blyth (23-CA-627): tax roll only has "BLYTH DESSIE" -- first-name mismatch to defendant "Timothy Blyth",
--     rejected as not exact (plausible estate co-owner, not confirmed).
--   Sherrell (25-CA-68): 2 distinct candidate parcels under the surname, no way to disambiguate -- rejected.
--   Essman (24-CA-130): exactly one exact-name match (ESSMAN ELIZABETH E, parcel 00-00-077-014-10524-021,
--     "24 Brewster Rd") but no independent second-source corroboration of the address surfaced this session
--     (a WebSearch found only a nearby "21 Brewster Rd" listing, not the same address) -- held back.
--   West (25-CA-50): zero matches under "WEST MIRANDA" or "STORM WEST".
-- A third data point (fair-market-value figures the research agent read off the tax bill's rendered detail
-- page, ~$356K and ~$113K) was deliberately NOT written to assessed_value/market_value: the operator could
-- not independently reproduce those specific dollar figures via a plain curl replay of the same endpoint
-- (the value fields did not appear in the static HTML returned to a scripted client, unlike the owner-name
-- search JSON which did reproduce identically) -- excluded per HONESTY PROTOCOL rather than trusted secondhand.
-- pencil_dod_evaluate_county('wakulla') E: 76.7% (23/30) -> 83.3% (25/30), re-verified live post-write.
-- RESIDUAL: Blyth/Sherrell/West need a court-docket or Sunbiz estate-representative cross-reference (real-
-- world name-mismatch, not a tooling gap); Essman needs one more independent address corroboration.
--
-- === WAKULLA G -- NO WRITE, correctly held to UNKNOWN ===
-- Only gap: max_density_du_acre for districts R1/RMH1/RR1 (jurisdiction_id=1402) -- FAR/parking already
-- correctly marked not-applicable by the prior G-fix session. This session's research agent found a genuinely
-- new document host (mcclibraryfunctions.azurewebsites.us, real downloadable Wakulla ordinance PDFs, verified
-- readable via pypdf) and mined 6 real ordinances -- none amend LDC Sec. 5-27 (RR-1), 5-30 (R-1), or 5-43
-- (RMH-1) with a density figure (they cover AG, solar-facility, Crawfordville LDR/HDR districts, a 2008
-- site-specific rezoning, noise, and library-board membership -- all real, all irrelevant to these 3 codes).
-- Zoneomics.com states specific numbers (R-1=5 du/ac, RMH-1=5 du/ac, RR-1=1 du/ac) but every web-search hit
-- repeating those numbers traces back to this single aggregator page with no second independent primary
-- source -- a prior session already flagged Zoneomics as unreliable/conflicting for this exact county, so
-- this was correctly NOT written. library.municode.com and wakullacounty.elaws.us remain blocked exactly as
-- before (reCAPTCHA SPA shell / HTTP 503). NO zone_standards row was inserted. This is the correct outcome
-- per HONESTY PROTOCOL (BLANK > WRONG) -- an honest FAIL is preferred to a plausible-but-unverifiable PASS.
--
-- === SUWANNEE -- re-confirmed, no new work needed ===
-- A: fc=0 (0 foreclosure listings) and B/F: closed_sold=0 are all structurally correct, not bugs -- all 9
-- suwannee multi_county_auctions rows have a FUTURE auction_date (07/09 or 08/06/2026) and
-- auction_status='upcoming'; no sale has occurred yet so there is nothing to verify or promote. This matches
-- shard11/run3679's same-day finding (suwannee.realforeclose.com AJAX calendar genuinely empty) and
-- pipeline.counties is already correctly marked healthy. No action taken this session; re-verified live.
--
-- AFTER (pencil_dod_evaluate_county, re-verified live immediately after the writes above):
--   levy:     unchanged, 9/10 (A FAIL fc=0, metadata-only fix, no regression on the other 9 letters).
--   suwannee: unchanged, 7/10 (A/B/F FAIL, all structurally blocked on real-world zero, not fixable today).
--   wakulla:  E 76.7%->83.3% (still FAIL, below 95% threshold, but a real 2-row gain). A/C/D/H/J unchanged
--             PASS. B/F/G/I unchanged FAIL (G/I residuals documented above, B/F genuinely 0 closed sales).
-- Logged to gold_standard_ultraloop_audit: id 5879 (levy A, survived=true), id 5880 (wakulla E,
-- survived=true), id 5881 (wakulla G, survived=false / no-fix-proposed).
--
-- No SQL statements below write anything beyond what is documented above -- the actual writes for
-- multi_county_auctions and pipeline.counties were applied live via the Supabase Management API SQL
-- endpoint during this session; this file replays them verbatim for audit/replay continuity.

BEGIN;

UPDATE public.multi_county_auctions
SET parcel_id = '00-00-055-422-19932-088',
    property_address = '20 Springdale Dr, Crawfordville, FL 32327'
WHERE id = 'd0444c61-f56e-49f2-94dc-9c7c82b8f059'
  AND county = 'wakulla' AND case_number = '25-CA-106' AND parcel_id IS NULL;

UPDATE public.multi_county_auctions
SET parcel_id = '25-2S-02W-000-01425-003',
    property_address = '180 Hilliardville Rd, Crawfordville, FL 32327'
WHERE id = '72decea5-51f7-497a-8fdd-2c0f4b743d07'
  AND county = 'wakulla' AND case_number = '24-CA-105' AND parcel_id IS NULL;

UPDATE pipeline.counties
SET pipeline_health = 'healthy',
    notes = 'Verified 2026-07-11 (dispatch b80c4c55/run3786): foreclosure lane genuinely empty. levyclerk.com/foreclosure-sales explicitly states no sales at this time. Additional sources checked and exhausted: floridapublicnotices.com (only 1 Levy notice site-wide, Case 2025000075CAAXMX, sale date 04/20/2026 already past -- page still live via GET, only HEAD requests 500); levy.agverso.com Auto-Graphics Records Manager SPA (new lead, live, but Angular/SignalR client-side app with no discoverable REST endpoint via curl -- would need a headless browser, unavailable in this sandbox); civitekflorida.com/ocrs/county/38 (same JSF/PrimeFaces session-token wall as other counties); circuit8.org procedural pages (no case data); Levy County Citizen newspaper chain (dead ends). No fabricated case numbers.'
WHERE county_slug = 'levy';

COMMIT;
