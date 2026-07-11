-- SHARD-6 (marion): C/D residual harvest — foreclosure lane match-application gap
-- + tax_deed 06/17 missed-date harvest + fresh re-diff of the 3 already-harvested
-- tax_deed dates.
-- dispatch_id: fb80bb9c-7d7d-469f-b3c0-493b5e4f9b3f
-- Session: architect-20260711T080000, loop run 3713 (continuation of
-- 20260711090000_shard6_marion_cd_realtaxdeed_and_i_hygiene.sql, which took C/D
-- from 54.2% -> 77.0% via a 3-date tax_deed harvest against marion.realtaxdeed.com).
--
-- LIVE STATE AT START OF THIS PASS (VERIFIED via pencil_dod_evaluate_county,
-- 2026-07-11): C/D = 77.0% (matched_clean=425 of 552). Residual = 127 rows:
--   110 tax_deed (10 on 2026-06-17 — a date NEVER harvested by the prior session,
--       which only covered 07-15/07-22/08-19 — plus 100 leftover unmatched rows
--       within the 3 already-harvested dates)
--   17 foreclosure (dates 07-13 through 07-20, all data_source=calendar_sweep_mca_v3,
--       never parity-checked)
--
-- ROOT CAUSE #1 (foreclosure lane, VERIFIED): marion's foreclosure calendar is
-- authoritatively served by marion.realforeclose.com (public.realauction_subdomains:
-- is_active=true, http_status=200, parity_verdict "verified re-scrape 2026-07-10")
-- — the standard RealAuction lane, NOT the Brevard-style courthouse exception.
-- ONE of the 17 residual rows (case 422025CA001791CAAXMX, id 0267258d) was found to
-- ALREADY have an exact case_number + exact parcel_id match sitting in
-- realforeclose_aids (aid=1500491, first_seen_at 2026-06-02) — i.e. a pure
-- match-application gap, not a missing-source gap. The other 16 were genuinely
-- absent from realforeclose_aids prior to this session's harvest.
--
-- ROOT CAUSE #2 (tax_deed 06-17, VERIFIED): the prior session's harvest targets
-- were taken from the unmatched rows' own auction_date column and only included
-- 07/15, 07/22, 08/19 — 2026-06-17 (10 canon rows) was never in that target list
-- and so was never scraped. Confirmed live: marion.realtaxdeed.com PREVIEW for
-- AUCTIONDATE=06/17/2026 returns real case data (not "NO CASES FOUND").
--
-- FIX: re-ran the existing Firecrawl-free direct AJAX harvester
-- (scripts/shard2_run2450_ajax_realforeclose_harvest.py, no code changes needed —
-- already supports both platform_domain='realtaxdeed.com' and the default
-- 'realforeclose.com') against BOTH marion.realtaxdeed.com (dates 06/17, and a
-- FRESH re-scrape of 07/15, 07/22, 08/19 to check for post-harvest case-status
-- drift) AND marion.realforeclose.com (dates 07/13, 07/14, 07/15, 07/16, 07/20,
-- taken from the 17 residual foreclosure rows' own auction_date column):
--   marion.realtaxdeed.com 06/17/2026: parsed=48 inserted_or_merged=48
--   marion.realtaxdeed.com 07/15/2026: parsed=62 inserted_or_merged=62 (re-scrape)
--   marion.realtaxdeed.com 07/22/2026: parsed=33 inserted_or_merged=33 (re-scrape)
--   marion.realtaxdeed.com 08/19/2026: parsed=50 inserted_or_merged=50 (re-scrape)
--   marion.realforeclose.com 07/13/2026: parsed=5  inserted_or_merged=5
--   marion.realforeclose.com 07/14/2026: parsed=5  inserted_or_merged=5
--   marion.realforeclose.com 07/15/2026: parsed=4  inserted_or_merged=4
--   marion.realforeclose.com 07/16/2026: parsed=4  inserted_or_merged=4
--   marion.realforeclose.com 07/20/2026: parsed=4  inserted_or_merged=4
--   TOTAL: parsed=215 inserted_or_merged=215 (no silent-zero failure; script's own
--   fail-loud guard would have raised RuntimeError otherwise)
--   realforeclose_aids for marion: TAXDEED 155->193, FORECLOSURE 409->431
--
-- MATCH RESULT against the fresh harvest, using the same guarded pattern as the
-- prior migration (exact case_number match, OR length-guarded substring match, OR
-- exact-digit-guarded parcel_id match): 23 of the 127 residual rows resolved —
-- 17 foreclosure (07-13 x5, 07-14 x3, 07-15 x2, 07-16 x3, 07-20 x4) + 6 tax_deed
-- (all on 06-17). Every one of the 23 has EXACT case_number agreement; 21 of 23
-- also have exact parcel_id agreement (hand-spot-checked 6 at random, all clean,
-- e.g. case 422025CA001946CAAXMX / parcel 3351053 identical both sides). The
-- remaining 2 (cases 422025CA001269CAAXMX, 422024CA002330CAAXMX) have the source
-- site's "Parcel ID" cell literally rendering the link-text "Property Appraiser"
-- instead of a parcel number (a genuine scrape-target artifact on those 2 specific
-- listing pages, not our parser's bug — same AITEM shape, empty structured field) —
-- NOT written into parcel_id (would be garbage), matched on exact case_number only,
-- which was independently sufficient and unambiguous; both mca-side rows already
-- had parcel_id NULL so nothing was overwritten.
--
-- The remaining 104 rows (100 tax_deed leftover from the 3 already-harvested
-- dates + 4 tax_deed from 06-17) were re-diffed against this SAME fresh scrape and
-- confirmed ABSENT — not a matcher gap. Spot-verified directly against the raw
-- PREVIEW HTML for 3 of these case numbers (199122017, 203302020, 69952016 against
-- AUCTIONDATE=07/15/2026): none appear in the live page body at all. Consistent
-- with the prior session's finding that the PREVIEW page reflects current
-- live-calendar state, not historical — these cases were most likely
-- pulled/resolved/redeemed since being scraped. NOT forced, NOT faked. Flagged for
-- the next marion session: closing this final ~19% gap requires either (a) a
-- historical/archival tax-deed case source (e.g. clerk-of-court sale results,
-- distinct from the live upcoming-auction calendar), or (b) accepting these as
-- permanently resolved-elsewhere and adjusting canon scope — a decision for a
-- human, not invented here.
--
-- Also backfilled property_address/assessed_value for 22 of the 23 newly-matched
-- rows (same already-cross-validated source, identical provenance to C/D fix,
-- I-criterion side effect only) — 1 row (case 422024CA002330CAAXMX) had no address
-- data on the source side either and was left NULL.
--
-- VERIFIED before/after (pencil_dod_evaluate_county, live query, 2026-07-11):
--   C: 77.0% (matched_clean=425 of 552) -> 81.2% (matched_clean=448 of 552)  FAIL->FAIL (real gain, still below 95%)
--   D: 77.0% -> 81.2% (matched_any tracks matched_clean 1:1, no divergent rows)  FAIL->FAIL
--   I: 54.0% (298/552) -> 54.2% (299/552), incidental side effect of the address/value backfill, not the target of this pass
--   A/B/E/F/G/H/J: unchanged, no regression.
--
-- Applied live 2026-07-11 via PostgREST (service role) before this file was
-- committed — this migration documents and reproduces those changes. Idempotent:
-- all UPDATE statements are guarded by parity_source IS DISTINCT FROM checks and
-- are safe to re-run; re-running will no-op on rows already stamped.

-- 1) C/D: stamp matched_clean for the 17 genuinely cross-validated foreclosure
--    residual rows (marion.realforeclose.com, exact case_number and/or exact
--    parcel_id agreement against realforeclose_aids).
UPDATE public.multi_county_auctions mca
SET parity_status = 'matched_clean',
    parity_source = 'tier1_realforeclose_marion',
    parity_checked_at = now(),
    updated_at = now()
FROM public.realforeclose_aids ra
WHERE ra.county_slug = 'marion'
  AND ra.auction_type = 'FORECLOSURE'
  AND lower(mca.county) = 'marion'
  AND mca.sale_type = 'foreclosure'
  AND (COALESCE(mca.data_source,'') <> 'propertyonion' OR COALESCE(mca.tier1_authoritative,false)=true)
  AND mca.parity_status IS DISTINCT FROM 'matched_clean'
  AND (
    normalize_case_number(mca.case_number) = normalize_case_number(ra.case_number)
    OR (
      length(normalize_case_number(mca.case_number)) >= 10
      AND length(normalize_case_number(ra.case_number)) >= 8
      AND normalize_case_number(mca.case_number) LIKE '%' || normalize_case_number(ra.case_number) || '%'
    )
    OR (
      mca.parcel_id IS NOT NULL AND ra.parcel_id IS NOT NULL AND mca.parcel_id = ra.parcel_id
      AND mca.parcel_id ~ '[0-9]' AND ra.parcel_id ~ '[0-9]'
    )
  )
  AND mca.parity_source IS DISTINCT FROM 'tier1_realforeclose_marion';

-- 2) C/D: stamp matched_clean for the 6 newly-harvested 06/17/2026 tax_deed rows
--    (the date the prior session's harvest missed entirely).
UPDATE public.multi_county_auctions mca
SET parity_status = 'matched_clean',
    parity_source = 'tier1_realtaxdeed_marion',
    parity_checked_at = now(),
    updated_at = now()
FROM public.realforeclose_aids ra
WHERE ra.county_slug = 'marion'
  AND ra.auction_type = 'TAXDEED'
  AND lower(mca.county) = 'marion'
  AND mca.sale_type = 'tax_deed'
  AND (COALESCE(mca.data_source,'') <> 'propertyonion' OR COALESCE(mca.tier1_authoritative,false)=true)
  AND mca.parity_status IS DISTINCT FROM 'matched_clean'
  AND (
    normalize_case_number(mca.case_number) = normalize_case_number(ra.case_number)
    OR (
      mca.parcel_id IS NOT NULL AND ra.parcel_id IS NOT NULL AND mca.parcel_id = ra.parcel_id
      AND mca.parcel_id ~ '[0-9]' AND ra.parcel_id ~ '[0-9]'
    )
  )
  AND mca.parity_source IS DISTINCT FROM 'tier1_realtaxdeed_marion';

-- 3) I: backfill address/value for the newly-matched rows from the same verified
--    cross-source match (identical provenance to the C/D fix above).
UPDATE public.multi_county_auctions mca
SET property_address = COALESCE(mca.property_address, ra.property_address),
    assessed_value = COALESCE(mca.assessed_value, ra.assessed_value),
    updated_at = now()
FROM public.realforeclose_aids ra
WHERE ra.county_slug = 'marion'
  AND lower(mca.county) = 'marion'
  AND mca.parity_source IN ('tier1_realforeclose_marion', 'tier1_realtaxdeed_marion')
  AND mca.parity_checked_at >= '2026-07-11 09:00:00+00'
  AND (
    normalize_case_number(mca.case_number) = normalize_case_number(ra.case_number)
    OR (mca.parcel_id IS NOT NULL AND ra.parcel_id IS NOT NULL AND mca.parcel_id = ra.parcel_id)
  )
  AND (mca.property_address IS NULL OR mca.assessed_value IS NULL);

-- ── VERIFICATION QUERIES (run after migration) ─────────────────────────────────────
-- SELECT public.pencil_dod_evaluate_county('marion');
-- SELECT count(*) FROM realforeclose_aids WHERE county_slug='marion' AND auction_type='TAXDEED';   -- expect 193
-- SELECT count(*) FROM realforeclose_aids WHERE county_slug='marion' AND auction_type='FORECLOSURE'; -- expect 431
-- SELECT parity_source, count(*) FROM multi_county_auctions WHERE lower(county)='marion' GROUP BY parity_source ORDER BY 2 DESC;
