-- SHARD-4 (Gold Standard, dispatch_id 1ea48950-c02a-4f2e-9b65-8c7e8c31b025, session
-- architect-20260702T160000, continuation): hernando E fix + martin F investigation
-- (no fix). Companion to 20260702_shard4_bradford_hamilton_martin_stjohns_hernando_
-- honesty_audit.sql (same dispatch, earlier commit 685e97a3) which found zero honest
-- C/D fixes for this shard's 5 counties and left bradford/martin/hernando(B/F) flagged
-- for follow-up. This migration executes on two of those follow-ups via an
-- ULTRALOOP (Workflow/ultracode) investigate + adversarial-refute pass: one
-- diagnostic subagent per lever, one independent refuter subagent per claim before
-- any live write. Both survival votes are logged in gold_standard_ultraloop_audit
-- (ids 2891/2892).
--
-- ══════════════════════════════════════════════════════════════════════════════════
-- HERNANDO E: FIX APPLIED AND VERIFIED (survived=true, refuter independently
-- reproduced all 6 findings — including re-OCRing the source PDF with tesseract
-- rather than trusting the claimed quotes, since the PDF is a scanned fax image with
-- no text layer).
--
-- 3 rows had parcel_id=NULL (case 22000840CA, 25000578CA, 25001007CA — the
-- 2026-07-28 auction batch). Real per-case data sourced from:
--   (a) Hernando Clerk foreclosure sale-list PDF (hernandoclerk.com, official,
--       primary source, not PropertyOnion):
--       https://hernandoclerk.com/wp-content/uploads/_Documents/Foreclosures/
--       Foreclosure%20Sale%20Lists/2026/07-July/28%20JULY.pdf
--   (b) SWFWMD ArcGIS REST parcel mirror (government-hosted, SOURCEAGENT=
--       'HERNANDO COUNTY PROPERTY APPRAISER'):
--       https://www25.swfwmd.state.fl.us/arcgis10/rest/services/WebMasterLookup/
--       MapServer/3/query
--
-- BONUS FINDING: the DB's stored property_address for 22000840CA ("5187 GAINSBORO
-- AVE") does not exist — no parcel on Gainsboro Ave in Spring Hill 34609 has a house
-- number below 6170 (confirmed by both the investigating agent and independently by
-- the refuter against the full SWFWMD address range for that street). The clerk PDF
-- and the property appraiser both give 6187, matching defendant NICHOLSON MARIA to
-- owner-of-record NICHOLSON MARIA exactly. This is corrected as part of this fix
-- (typo, not a new claim requiring separate evidence).
--
-- 25000578CA's parcel_id is marked lower-confidence (INFERRED, not VERIFIED) in the
-- audit record: current owner-of-record is JENSEN SHARON L ESTATE OF, not defendant
-- Stephanie Norris — normal for foreclosure/estate turnover, and address + legal
-- description ("TIMBER PINES TR 7" / "LOT 12, TIMBER PINES TRACT 7") match exactly,
-- but there is no owner-name cross-check like the other two cases. Applied anyway —
-- the match is still strong, and E only requires a parcel_id, not a confidence tier.
--
-- SEPARATE ANOMALY FOUND, NOT FIXED HERE (out of this fix's scope, flagged for a
-- future session): judgment_amount for these 3 rows does not match the clerk PDF and
-- appears cross-shuffled across adjacent rows (e.g. DB's 22000840CA=$234,159.70 is
-- actually PDF's 25001007CA amount; DB's 25001007CA=$308,052.12 is actually PDF's
-- 25000578CA amount). Looks like a row-misalignment bug of the same class as the
-- hamilton cert-offset bug found in the companion migration. Needs its own
-- independently-verified fix, not guessed here.
UPDATE multi_county_auctions
SET parcel_id = 'R3232317520013520110',
    property_address = '6187 GAINSBORO AVE, SPRING HILL, FL 34609',
    updated_at = now()
WHERE county = 'hernando' AND case_number = '22000840CA' AND parcel_id IS NULL;

UPDATE multi_county_auctions
SET parcel_id = 'R2122317607100000120',
    property_address = '6466 TAPESTRY CIR, SPRING HILL, FLORIDA 34606',
    updated_at = now()
WHERE county = 'hernando' AND case_number = '25000578CA' AND parcel_id IS NULL;

UPDATE multi_county_auctions
SET parcel_id = 'R3212221121400000990',
    property_address = '6882 REDBAY DR., BROOKSVILLE, FL 34602',
    updated_at = now()
WHERE county = 'hernando' AND case_number = '25001007CA' AND parcel_id IS NULL;

-- VERIFIED live before/after via pencil_dod_evaluate_county('hernando'):
--   BEFORE: E 87.0% FAIL (parcel_linked=20 of 23) | hernando 4/10 (A,G,H,J)
--   AFTER:  E 100.0% PASS (parcel_linked=23 of 23) | hernando 5/10 (A,E,G,H,J)
-- I unaffected (still 43.5%, card_complete=10 of 23) — I additionally requires a
-- zoned parcel (parcel_zones linkage), which these 3 rows still lack; out of this
-- fix's scope.
--
-- ══════════════════════════════════════════════════════════════════════════════════
-- MARTIN F: NO FIX — investigated, not fabricated. Real, live endpoints exist
-- (or.martinclerk.com/LandmarkWeb HTTP 200; www.martinclerk.com HTTP 200 — the
-- companion migration's "or.martin.fl.us NXDOMAIN" finding was a wrong-hostname
-- guess, not a genuine dead end). But every reachable endpoint is either
-- reCAPTCHA-gated (LandmarkWeb document/case search, court.martinclerk.com) or, for
-- the anonymous RealAuction AJAX feed (martin.realforeclose.com), exposes only the
-- plaintiff's Final Judgment Amount (the reserve/opening-bid basis) — never a
-- winning-bid/sale amount. Checked across 4 auction dates including dates already
-- past the site's own server clock; every item remains in AUCTION_ITEM PREVIEW state
-- with empty SOLDTO fields, and the live results-refresh AJAX call returns
-- ADATA.COUNT=0. Root cause, independently confirmed via direct Supabase query: all
-- 29 martin rows are auction_status='upcoming' (26) or 'cancelled' (3) — zero are
-- sold/completed/redeemed, so there is no closed-case denominator for F to honestly
-- measure yet, regardless of source access.
-- No DB write. Refuter vote: survived=false (2 of 7 evidence citations did not
-- independently reproduce byte-for-byte — LandmarkWeb captcha-check URL and one
-- volatile JSON field — but the load-bearing conclusion, that no sale data is
-- exposed anywhere, held up under independent re-fetch). BLANK > WRONG.
--
-- ══════════════════════════════════════════════════════════════════════════════════
-- HERNANDO B/F: investigated, no fix, no fabrication (claims_found=false — the
-- investigating agent returned zero findings rather than a weak or guessed one).
-- 3 hernando foreclosure cases closed 2026-06-30 (25000637CA, 23001588CA,
-- 25000967CA) and are stale in our DB (still 'upcoming', sold_amount NULL), but no
-- outcome data was reachable: hernando.realforeclose.com and hernando.realtaxdeed.com
-- are pure client-side JS SPAs that return an empty, byte-identical HTML shell to
-- curl/WebFetch regardless of path or query params (a structural wall, not a
-- transient/path-specific 403 — confirmed by diffing 4 different request variants).
-- hernandoclerk.com's sale-list page is forward-looking only. or.hernandoclerk.com
-- LandmarkWeb and civitekflorida.com/ocrs (Hernando's Civitek docket search) both
-- have real search forms but require stateful session/viewstate interaction beyond a
-- single GET. No public/indexed source has any of the 3 case numbers. Left honestly
-- FAIL/null pending either an authenticated session or a stateful-form-capable
-- scraper — not attempted here to avoid guessing.
--
-- VERIFICATION QUERIES (run after apply):
-- SELECT public.pencil_dod_evaluate_county('hernando');
-- SELECT public.pencil_dod_evaluate_county('martin');
-- Audit rows: SELECT * FROM gold_standard_ultraloop_audit WHERE id IN (2891, 2892);
