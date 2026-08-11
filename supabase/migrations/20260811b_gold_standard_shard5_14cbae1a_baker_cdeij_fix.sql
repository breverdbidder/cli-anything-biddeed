-- Gold Standard shard-5 baker (dispatch 14cbae1a-b1e3-4744-99c7-ffe69766ca29)
--
-- SCOPE: fresh independent research (fan-out workflow, 4 parallel agents +
-- adversarial verify per finding) on baker's 4 stuck C/D/E/I/J rows, after
-- 6+ prior sessions already exhausted RealForeclose/RealTaxDeed re-scraping
-- for these exact case numbers.
--
-- RESULTS (2 of 4 findings survived adversarial verification with real new
-- data; 2 remain genuinely source-exhausted):
--
-- 1. 022025CA000124CAAXMX -- FOUND real parcel/address/value via a NEW
--    avenue never tried in prior sessions: bakercountypress.com legal
--    notices (NOTICE OF SALE PURSUANT TO CHAPTER 45, Case No. 25000124CAMXAX
--    -- Baker Clerk's abbreviated docket serialization of the same
--    02/2025/CA/000124 tokens as our zero-padded case_number). Carrington
--    Mortgage Services LLC vs. Estate of Norman Danny Thrift et al., sale
--    8/27/2026 11:00am at www.baker.realforeclose.com (exact match to our
--    auction_date/auction_url). Cross-referenced via bakerpa.com quick
--    search on the address, one parcel match: 052S22000000000020, owner
--    THRIFT NORMAN DANNY SR (exact defendant match). bakerpa.com property
--    card: Site Address "5438 CR 23D Glen St Mary, FL", Land Size 1.50 AC,
--    Total Just Value $135,204, Assessed Value-Non School/School $53,079.
--    Lat/long: centroid computed from the Baker County GIS ArcGIS
--    FeatureServer (parcels_web2/FeatureServer/0) polygon for this PARCELNO,
--    independently recomputed by the adversarial verifier (not just trusted
--    from the research agent). REFUTER VERDICT: NOT refuted -- independently
--    re-fetched the notice URL, re-queried the ArcGIS FeatureServer for this
--    exact parcel, and got matching owner/address/value/zoning fields.
--
-- 2. Zoning gap for parcel 073S21000000000100 (case 022025CA000002CAAXMX --
--    this case's parcel/address/value were already resolved in a 2026-08-10
--    session, but that session explicitly flagged the zoning link as
--    "genuine zoning-ingestion coverage gap ... NOT fabricated"). Live
--    Baker County GIS ArcGIS FeatureServer query (parcels_web2/FeatureServer
--    /0, where PARCELNO='073S21000000000100') returns exactly one feature:
--    PIN=07-3S-21-0000-0000-0100, Zoning="AG 7.5", Deed_Acrea=13.21,
--    Descriptio="INTERSTATE RELATED COMMERCIAL", owner HOLMES MICHAEL T JR /
--    HOLMES SANDRA J -- all matching the parcel's existing DB fields.
--    REFUTER VERDICT: NOT refuted -- independently re-fetched the exact
--    ArcGIS query URL and got the same Zoning="AG 7.5" value.
--
-- 3. Same zoning gap discovered (mid-session, after fixing #1) on the newly
--    -linked case124 parcel 052S22000000000020 -- also absent from
--    parcel_zones. Same ArcGIS FeatureServer, same PARCELNO query:
--    Zoning="AG 7.5", Deed_Acrea=1.5, Descriptio="AG B". Applied live,
--    verified via v_zoning_gold_standard_card immediately after.
--
-- NOT RESOLVED (source-exhausted, zero fabrication):
--   - 022025CA000117CAAXMX: 7th independent session to reach this
--     conclusion. Clerk OCRS (civitekflorida.com/ocrs/county/02) case-search
--     is gated by a mandatory Cloudflare Turnstile checkbox (verified via
--     Playwright screenshot of the reset-on-submit behavior); bakerclerk.com
--     and Trellis.law are both Cloudflare-blocked (403); PropertyOnion.com's
--     Baker County listing search found zero text match for this case
--     number among its 106 visible listings (6 more are paywalled, could not
--     verify); a plain web search for the case number returned zero
--     relevant hits. No parcel/address/coordinates fabricated.
--   - 022025CC000132CCAXMX: legitimacy re-assessed this session against the
--     official 8th Judicial Circuit AO 9.02 case-type-assignment PDF --
--     "CC" (County Court civil) IS a valid case type for small-dollar
--     ($5,001-$15,000) Baker foreclosures, so the case-type code alone does
--     NOT disqualify it. However this remains the ONLY Baker row with a
--     CC-suffixed case number AND the only row with judgment_amount=$0.00
--     (every genuine foreclosure row has $95,618-$330,375; the one genuine
--     tax-deed row correctly has null, not zero), and it exactly matches
--     this county's twice-already-fixed calendar_sweep_mca_v3
--     mislabeled-duplicate signature (source_platform='realtaxdeed' but
--     sale_type='foreclosure'). This is circumstantial-pattern evidence
--     (INFERRED), not a positive docket confirmation -- every independent
--     court-record source (OCRS login wall, bakerclerk.com 403, UniCourt
--     WAF challenge, Trellis.law 403, RealAuction detail page login wall,
--     PropertyOnion JS-rendered page) was blocked. Per BLANK > WRONG, this
--     row was left untouched rather than guess-deleted on inference alone --
--     flagged for a follow-up session with a dedicated (paid, if needed)
--     docket lookup.
--
-- SEPARATE FINDING -- ACTIVELY RECURRING DUPLICATE-ROW BUG (escalated, not
-- fixed at the root this session): the sale_type='tax_deed',
-- source_platform='realtaxdeed', all-NULL duplicate row for case
-- 022025CA000148CAAXMX (already documented recurring twice on 2026-08-10 in
-- 20260810_..._baker_cdeij_mislabel_dedup.sql and 20260810c_..._recurrence_
-- cleanup.sql) recurred FOUR MORE TIMES live during this single session
-- (2026-08-11, roughly every 10-25 minutes: 16:15, 16:30 [pre-existing at
-- session start], then again at 16:15 and 16:25 after each delete) --
-- materially faster than the prior ~daily cadence. New evidence this
-- session: the phantom row's tier1_source_run_id is a STABLE value (55009)
-- across multiple recurrences with fresh tier1_verified_at/scraped_at
-- timestamps each time, while the row's genuine foreclosure sibling gets a
-- DIFFERENT, incrementing tier1_source_run_id (90855) -- strongly suggesting
-- the write path is a tier1-verification/promotion process re-touching a
-- stale batch identity, NOT a fresh calendar_sweep_mca_v3 AJAX scrape as
-- previously hypothesized. Could not confirm further: no calendar-sweep-
-- dark-counties.yml run or gha_dispatch_log row for baker exists in the
-- matching time window (checked live via `gh run list` and the
-- gha_dispatch_log table), and this session's DB pooler credentials
-- (aws-0-us-west-2.pooler.supabase.com, postgres.<project_ref> user) failed
-- password auth, so cron.job could not be listed directly. NEXT SESSION:
-- get cron.job / pg_cron listing via Supabase dashboard or Management API
-- (not the stale pooler password) and check for an hourly/frequent tier1
-- promotion job touching baker -- do not re-guess a calendar_sweep_mca.py
-- fix, the evidence now points elsewhere. Deleted the row 4 times live this
-- session (FK-safety re-verified against auction_enrichment_queue,
-- auction_schedule_history, court_case_metadata, po_mca_matches,
-- shapira_outcome_scorecard each time, all zero); it may well be present
-- again by the time this migration is reviewed -- that is expected and is
-- the open finding, not a mistake in this file.
--
-- BEFORE (VERIFIED live via pencil_dod_evaluate_county('baker'), session
-- start, loop_run_id=10589): auctions_total=11
--   C=FAIL(63.6, matched_clean=7) D=FAIL(63.6, matched_any=7)
--   E=FAIL(63.6, parcel_linked=7) I=FAIL(54.5, card_complete=6 of 11)
--   J=FAIL(90.9, deal_complete=10 of 11)
--
-- AFTER (VERIFIED live via pencil_dod_evaluate_county('baker'), immediately
-- after this session's final delete of the recurring phantom row):
-- auctions_total=10 (denominator-honesty corrected: 10 genuine distinct
-- baker case numbers, matching the county's real docket count)
--   C=FAIL(80.0, matched_clean=8) D=FAIL(80.0, matched_any=8)
--   E=FAIL(80.0, parcel_linked=8) I=FAIL(80.0, card_complete=8 of 10)
--   J=FAIL(90.0, deal_complete=9 of 10)
-- Still 4/10 pass (A,B,F,G,H already passing, unchanged). C/D/E/I moved
-- +16.4 points each (63.6->80.0); I moved the most (+25.4, 54.5->80.0).
-- J's apparent -0.9 is NOT a regression -- it is the same denominator-
-- honesty correction (the phantom row's case_number already had a
-- bid_decisions match via case-number lookup, so it was being double-counted
-- as "complete" while also inflating the denominator; removing it removes
-- one artificial pass from both sides of the ratio). Residual gap on all
-- five letters is now exactly 2 case numbers (117, 132), both genuinely
-- source-exhausted this session.
--
-- ADVERSARIAL AUDIT: 4 findings run through an independent refuter agent
-- (separate context, instructed to default to refuted=true unless it
-- independently re-fetched the source itself). All 2 positive findings
-- (case124, zoning parcel 073S21000000000100) survived (refuted=false); the
-- 2 negative findings (case117, case132) made no claim to refute. Rows
-- logged to gold_standard_ultraloop_audit as part of this session's
-- close-out.

BEGIN;

-- 1. Backfill 022025CA000124CAAXMX with real bakerpa.com + ArcGIS-verified
--    parcel/address/geo/value (see narrative above for sourcing).
UPDATE public.multi_county_auctions
SET
  parcel_id = '052S22000000000020',
  property_address = '5438 COUNTY ROAD 23 D (CR 23D), GLEN ST MARY, FL 32040',
  city = 'Glen St Mary',
  zip = '32040',
  latitude = 30.3552,
  longitude = -82.1320,
  assessed_value = 53079,
  market_value = 135204,
  parity_status = 'matched_clean',
  parity_source = 'tier1_baker_realforeclose_bakerpa_v1:baker:20260811_shard5_14cbae1a',
  parity_confidence = 0.95,
  parity_checked_at = now(),
  updated_at = now()
WHERE county = 'baker' AND case_number = '022025CA000124CAAXMX'
  AND (parcel_id IS NULL OR parity_status IS NULL);

-- 2. J: Shapira Formula per CLAUDE.md, (ARV*70%)-Repairs-$10K-MIN($25K,15%*ARV),
--    applied to the VERIFIED Total Just Value ($135,204) as ARV, repairs
--    estimate $25,000 (same convention as the most recent baker J-generator
--    migration, 20260810b_..._case002_cdeij_backfill.sql).
INSERT INTO public.bid_decisions
  (case_number, county_slug, parcel_id, address, auction_date, arv, repairs,
   final_judgment, max_bid, bid_judgment_ratio, recommendation, confidence,
   ml_score, factors, arv_source, pipeline_version)
SELECT
  '022025CA000124CAAXMX', 'baker', '052S22000000000020',
  '5438 COUNTY ROAD 23 D (CR 23D), GLEN ST MARY, FL 32040', auction_date,
  135204.00, 25000.00, 195558.74, 39362.20,
  round(39362.20 / NULLIF(195558.74, 0), 4),
  'BID', 0.50, 0.75,
  jsonb_build_object(
    'model', 'shapira_v14',
    'distress_location', jsonb_build_object('score', 5.0, 'note', 'baker county FL', 'honesty_marker', 'INFERRED'),
    'distress_property', jsonb_build_object('score', 5.0, 'note', 'foreclosure distress', 'honesty_marker', 'INFERRED'),
    'distress_owner', jsonb_build_object('score', 7.0, 'note', 'judicial action filed', 'honesty_marker', 'INFERRED'),
    'cma_distressed', jsonb_build_object('value', round(135204.00 * 0.85, 2), 'note', 'distressed comp arm', 'honesty_marker', 'INFERRED'),
    'cma_resale', jsonb_build_object('value', 135204.00, 'note', 'retail resale arm -- Total Just Value, bakerpa.com', 'honesty_marker', 'INFERRED')
  ),
  'shapira_formula_baker_bakerpa_total_just_value_verified',
  'baker_j_gen_dispatch14cbae1a_v1'
WHERE NOT EXISTS (SELECT 1 FROM public.bid_decisions WHERE case_number = '022025CA000124CAAXMX');

-- 3. parcel_zones: AG 7.5 for 073S21000000000100 (verified live via Baker
--    County GIS ArcGIS FeatureServer parcels_web2 Zoning field -- this
--    parcel's own parcel/address/value data was resolved in a prior
--    session, 2026-08-10, which explicitly left the zoning link unresolved).
INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT '073S21000000000100', 1664, 'AG 7.5',
       'Agricultural District: AG 7.5 (Sec. 24-191) - Baker County GIS parcels_web2 layer',
       'baker_county_gis_arcgis_parcels_web2_live_2026-08-11'
WHERE NOT EXISTS (SELECT 1 FROM public.parcel_zones WHERE parcel_id = '073S21000000000100');

-- 4. parcel_zones: AG 7.5 for 052S22000000000020 (this session's newly
--    -linked case124 parcel -- verified live via the same ArcGIS layer).
INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT '052S22000000000020', 1664, 'AG 7.5',
       'Agricultural District: AG 7.5 (Sec. 24-191) - Baker County GIS parcels_web2 layer',
       'baker_county_gis_arcgis_parcels_web2_live_2026-08-11'
WHERE NOT EXISTS (SELECT 1 FROM public.parcel_zones WHERE parcel_id = '052S22000000000020');

-- 5. Recurring phantom-duplicate stopgap (3rd/4th occurrence this session
--    alone -- see narrative above). Idempotent: only deletes an exact,
--    still-empty duplicate for this specific case/sale_type pair, and only
--    if it carries zero enrichment (parcel_id AND property_address both
--    NULL) so a genuine future second sale for this case is never touched.
DELETE FROM public.multi_county_auctions
WHERE county = 'baker'
  AND case_number = '022025CA000148CAAXMX'
  AND sale_type = 'tax_deed'
  AND parcel_id IS NULL
  AND property_address IS NULL;

COMMIT;
