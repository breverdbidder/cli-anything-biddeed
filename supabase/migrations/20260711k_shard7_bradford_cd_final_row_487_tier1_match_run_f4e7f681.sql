-- GOLD STANDARD CAMPAIGN shard-7, dispatch f4e7f681-ebf0-4732-af8c-ae2ace00840b, county: bradford
-- Purpose: C/D parity backfill for the last unmeasured row (case 25000487CAAXMX),
-- closing C and D from 80% (4/5) to 100% (5/5).
--
-- Live baseline before this fix (pencil_dod_evaluate_county('bradford'), 2026-07-11):
--   A pass (fc=4 td=1) -- already fixed by a prior shard-7 session (run3713, commit df6fdc75
--   ancestry + 20260711h migration), NOT touched here.
--   C fail 80.0% (matched_clean=4 of 5) -- case 25000487CAAXMX had parity_status=NULL.
--   D fail 80.0% (matched_any=4 of 5) -- same row.
--   E fail 80.0% (parcel_linked=4 of 5) -- case 25000439CAAXMX has parcel_id=NULL (NOT fixed
--   here -- see residual note below).
--
-- Independent verification performed live this session (WebFetch of bctelegraph.com, an
-- independent third-party publisher of Bradford Clerk's court-mandated legal notices --
-- NOT PropertyOnion, NOT our own scrape):
--
--   https://bctelegraph.com/legal-notices-for-7-9-26/ contains, verbatim:
--     "Case No. 04-2025-CA-487" / Plaintiffs "MICHAEL J. LEMIRE AND KARA L. LEMIRE" v.
--     Defendants "KEITH ANTHONY HILLIARD, LOIS J. HILLIARD, AND BILLY JOE WILLIAMS" /
--     Property Address "7656 SW CR 225, Starke, FL 32091" / Parcel Identification Number
--     "00868-0-01801" / sale scheduled August 13, 2026.
--
--   This is an EXACT match on BOTH property_address ("7656 SW CR 225, STARKE, FL 32091")
--   AND parcel_id ("00868-0-01801") already stored on our row for case 25000487CAAXMX.
--   The case-number format "04-2025-CA-487" is Bradford Clerk's docket-prefix format for
--   the same case as the AAXMX civil-case-number convention (25000487CAAXMX), consistent
--   with the same digit-normalization already validated for case 24000431CAAXMX ==
--   2024000431CAAXMX in the prior 20260711h migration on this county. No discrepancy found
--   between our stored row and the independent bctelegraph.com notice -> matched_clean.
--
-- Adversarial cross-check performed before writing this: a separate WebSearch snippet
-- initially appeared to attribute address "18737 Charlotte Avenue, Brooker" to case
-- 25000439CAAXMX (Barranco Pinto) -- this was VERIFIED FALSE by direct WebFetch of the
-- source bctelegraph.com page (a search-snippet blending artifact, not real page content).
-- The direct fetch confirmed 18737 Charlotte Avenue belongs to case 04-2025-CA-000457
-- (= our 25000457CAAXMX, VyStar/Ronald Adam Miller), which already matches what our DB had
-- stored correctly. No change made to that row. This near-miss is logged here as an honesty
-- note, not acted on.
--
-- NOT touched (honest residual, not fabricated):
--   - E (parcel_linked): case 25000439CAAXMX (Barranco Pinto, Planet Home Lending) has no
--     street address or parcel number published in either bctelegraph.com legal-notice
--     issue that ran it (2-5-26, 2-12-26) -- only a metes-and-bounds legal description
--     (Lot 6, NE 1/4 of Section 11, Township 7 South, Range 21 East). Bradford County
--     Property Appraiser's GIS (bradfordappraiser.com/GIS/) is a client-side ArcGIS
--     JS viewer with no owner-name search reachable via this session's tools; a direct
--     ArcGIS REST probe (bcmaps.bradfordco.org/portal/rest/services) returned HTTP 500,
--     i.e. no working endpoint found at the guessed path within this session's budget.
--     Left as parcel_id=NULL. A future session should discover the correct ArcGIS
--     MapServer path (or use an interactive/authenticated GIS search) and query by
--     Section 11 / Township 7S / Range 21E to recover the real parcel_id -- do not guess.
--   - I (card_complete): structurally capped at 0% for Bradford regardless of this fix.
--     v_zoning_gold_standard_card's source table (parcel_zones) contains only 3 rows for
--     Bradford, all with placeholder parcel_ids "BRADFORD-PARCEL-0001/0002/0003" -- not
--     real Bradford Property Appraiser parcel numbers -- so no real auction row's parcel_id
--     (format NNNNN-N-NNNNN) can ever match. This is an upstream zoning-ingestion gap
--     (Bradford has not had a real GIS zoning scrape run), out of scope for this bounded
--     pass -- requires a real per-parcel zoning ingestion build, not a data backfill.
--   - B/F: correctly unmeasurable -- all 5 Bradford rows are auction_status='upcoming'
--     with sold_amount IS NULL (no case has closed/sold yet). Not fabricated.
--
-- Applied directly via the Supabase Management API (SQL passthrough) per shard-7 session
-- instructions; included here for the historical record and to allow reapplication/audit.

UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:bctelegraph_clerknotice_live_20260711_run_f4e7f681',
    updated_at = now()
WHERE lower(county) = 'bradford'
  AND case_number = '25000487CAAXMX';
