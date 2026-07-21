-- GOLD STANDARD shard-9 (dispatch 20a33672), 5th firing, alachua C/D/E lane.
--
-- OUTCOME: structural block RE-CONFIRMED via a NEW live method (RealForeclose AJAX
-- PREVIEW/UPDATE endpoint with cookie jar + browser User-Agent + X-Requested-With
-- header, scripts/shard2_run2450_ajax_realforeclose_harvest.py) that the prior (4th)
-- firing had explicitly flagged as not-yet-attempted. This is a stronger/more direct
-- probe than plain httpx/WebFetch (which both still return HTTP 403 on the raw
-- calendar HTML page) and than Firecrawl (blocked fleet-wide by HTTP 402 insufficient
-- credits, confirmed live this session against qpublic.schneidercorp.com and
-- isol.alachuaclerk.org -- this is an account-level block, not a per-site block).
--
-- NO ROWS IN multi_county_auctions WERE CHANGED. No parcel_id, address, or
-- parity_status was fabricated. This migration only records the audit trail.
--
-- Live evidence (2026-07-21, session architect-<this run>):
--
-- 1. C/D gap (4 rows, parity_status IS NULL): case_numbers 01 2025 CC 001552,
--    01 2025 CA 003919, 01 2023 CA 004261, 01 2025 CA 003629 -- ALL auction_date
--    2026-08-18, which is IN THE FUTURE relative to today (2026-07-21). The
--    RealForeclose AJAX PREVIEW/UPDATE endpoint DOES return these exact case
--    numbers live on the 2026-08-18 calendar (re-harvested this session, aid=
--    1509516/1509514/1510233/1509513) -- but promoting parity_status to
--    'matched_clean' from that same not-yet-held calendar is the exact
--    ghost-success pattern already identified and explicitly rejected by prior
--    ULTRALOOP-audited sessions (see gold_standard_ultraloop_audit, SHARD-1
--    run3059 2nd pass commit 31460aa3, and shard13_run3059_duval_polk_alachua_
--    union_cd_e.py's own residual-gap note for alachua's July batch). These 4
--    rows cannot legitimately reach matched_clean until their auctions are
--    actually held. NOT a fixable gap this session.
--
-- 2. E gap (9 rows, parcel_id IS NULL): the same 4 rows above, PLUS
--    01 2026 CC 000399, 01 2025 CA 003110, 01 2025 CA 003156 (auction_date
--    2026-08-13, also future), PLUS 01 2025 CA 003287 (2026-05-04) and
--    01 2025 CA 001928 (2026-05-14) (both already past, already matched_clean
--    via a genuine independent tier1 source, so they do NOT count against C/D --
--    only against E). Re-harvested ALL 9 live via the RealForeclose AJAX
--    endpoint this session (written to realforeclose_aids, a staging/audit
--    table with zero DoD scoring impact): every single one carries RealForeclose's
--    OWN literal placeholder string in its Parcel ID field -- "Property Appraiser"
--    (8 rows) or "MULTIPLE PARCEL" (1 row, case 01 2025 CA 003287) -- with an
--    empty qpublic KeyValue= and an empty Clerk docid=. This is RealForeclose's
--    source data itself being incomplete, not a fetch-layer artifact: the exact
--    same AJAX call that returns a real folio (e.g. 05996-010-022) for 40+ other
--    alachua rows returns the literal placeholder for these 9. Real
--    judgment_amount values WERE recovered for all 9 (e.g. $911,614.76 for
--    01 2023 CA 004261) but that alone does not satisfy E's parcel_id requirement.
--
-- 3. Both potential secondary levers were tried live and ruled out:
--    a. qpublic.schneidercorp.com direct parcel lookup: HTTP 403 (Cloudflare
--       bot-protection), confirmed via both raw httpx and WebFetch this session
--       (re-test of the exact URL from the AJAX Parcel ID anchor).
--    b. alachuaclerk.org civil case docket search (court_records path,
--       www.alachuaclerk.org/court_records): confirmed this session to require
--       BOTH a login AND a CAPTCHA (page source: `ColdFusion.required['captcha']
--       =true`) -- a genuine, non-bypassable structural wall, not merely a
--       redirect. The separate isol.alachuaclerk.org portal (RealEstate/
--       SearchEntry.aspx) IS anonymously reachable (HTTP 200, no login) but is
--       a recorded-DOCUMENT index (deed/mortgage, searchable only by
--       Grantor/Grantee party name, Book/Page, Instrument #, or Legal
--       Description) -- it has no case-number search field at all, and we have
--       no defendant/party name for these 9 cases (RealForeclose's AITEM block
--       carries no owner/party field, verified by inspecting the raw decoded
--       HTML for case 01 2023 CA 004261 this session), so this portal cannot
--       be used to resolve them either.
--
-- pipeline.counties.foreclosure_url/taxdeed_url for alachua were verified
-- correct (realforeclose/realtaxdeed, matching the platform actually tested
-- live) -- no config defect, ruling out a "wrong URL" root cause.
--
-- Before/after pencil_dod_evaluate_county('alachua') -- UNCHANGED (no write made):
--   C: FAIL 92.2% (matched_clean=47/51)  -> FAIL 92.2% (unchanged)
--   D: FAIL 92.2% (matched_any=47/51)    -> FAIL 92.2% (unchanged)
--   E: FAIL 82.4% (parcel_linked=42/51)  -> FAIL 82.4% (unchanged)

INSERT INTO public.gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived, created_at)
VALUES
  (
    '20a33672-c291-4f56-a8e0-d0066b068884',
    'fallback',
    'alachua',
    'C',
    'C/D gap (4 rows, all auction_date=2026-08-18/future) re-confirmed via live RealForeclose AJAX harvest: case numbers DO appear on the live not-yet-held calendar, but promoting to matched_clean from that same future calendar is the ghost-success pattern explicitly rejected by prior ULTRALOOP-audited sessions. Not fixed -- structural, time-gated, not this-session-fixable.',
    jsonb_build_object(
      'method', 'scripts/shard2_run2450_ajax_realforeclose_harvest.py against alachua.realforeclose.com, dates 05/04/2026,05/14/2026,08/13/2026,08/18/2026',
      'blocked_case_numbers_c_d', jsonb_build_array('01 2025 CC 001552','01 2025 CA 003919','01 2023 CA 004261','01 2025 CA 003629'),
      'all_future_dated', true,
      'today', '2026-07-21',
      'aids_written_to_realforeclose_aids', jsonb_build_array(1509516,1509514,1510233,1509513)
    ),
    true,
    now()
  ),
  (
    '20a33672-c291-4f56-a8e0-d0066b068884',
    'fallback',
    'alachua',
    'E',
    'E gap (9 rows total, parcel_id IS NULL) re-confirmed live: every one of the 9 case numbers carries RealForeclose''s own literal placeholder ("Property Appraiser" x8, "MULTIPLE PARCEL" x1) in its Parcel ID field -- this is source-data incompleteness, not a fetch-layer or config defect. qpublic.schneidercorp.com direct lookup: HTTP 403 (Cloudflare), re-tested live via httpx AND WebFetch. alachuaclerk.org court_records case-docket search: confirmed login-wall AND CAPTCHA (ColdFusion.required[captcha]=true). isol.alachuaclerk.org RealEstate index: anonymously reachable but document-only (Grantor/Grantee/Book-Page/Instrument#), no case-number field, and we have no party name to search by. Firecrawl: HTTP 402 insufficient credits fleet-wide (account-level, re-confirmed live against both blocked domains), not a per-site block. No parcel_id fabricated. Real judgment_amount values recovered for all 9 (does not satisfy E on its own).',
    jsonb_build_object(
      'blocked_case_numbers_e', jsonb_build_array(
        '01 2025 CA 003287','01 2025 CA 001928','01 2026 CC 000399','01 2025 CA 003110',
        '01 2025 CA 003156','01 2025 CC 001552','01 2025 CA 003919','01 2023 CA 004261','01 2025 CA 003629'
      ),
      'realforeclose_parcel_id_placeholder', jsonb_build_object(
        '01 2023 CA 004261', 'Property Appraiser',
        '01 2024 CA 001683', 'Property Appraiser',
        '01 2025 CA 001356', 'Property Appraiser',
        '01 2025 CA 001928', 'Property Appraiser',
        '01 2025 CA 003110', 'Property Appraiser',
        '01 2025 CA 003156', 'Property Appraiser',
        '01 2025 CA 003287', 'MULTIPLE PARCEL',
        '01 2025 CA 003629', 'Property Appraiser',
        '01 2025 CA 003919', 'Property Appraiser',
        '01 2025 CC 001552', 'Property Appraiser',
        '01 2026 CC 000399', 'Property Appraiser'
      ),
      'qpublic_http_status', 403,
      'alachuaclerk_court_records_login_captcha_confirmed', true,
      'firecrawl_http_status', 402,
      'firecrawl_error', 'Insufficient credits to perform this request'
    ),
    true,
    now()
  );
