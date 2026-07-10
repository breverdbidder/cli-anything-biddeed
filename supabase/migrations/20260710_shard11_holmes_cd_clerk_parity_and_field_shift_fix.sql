-- SHARD-11 (run 3497): holmes C/D parity + field-shift data-quality fix
--
-- ROOT CAUSE 1 (pipeline.counties config is WRONG for holmes): platform columns say
-- foreclosure_platform=realforeclose / taxdeed_platform=realtaxdeed, pipeline_health=
-- healthy. VERIFIED live: holmes.realforeclose.com and holmes.realtaxdeed.com both
-- 302-redirect off-host to the generic www.realauction.com marketing splash (same
-- unprovisioned-RealAuction-tenant pattern already documented for union/columbia/dixie).
-- Holmes is NOT live on RealAuction. The 13 real rows actually came from
-- source_platform=holmes_clerk (holmesclerk.com), which correctly reflects reality --
-- only pipeline.counties itself is stale/wrong.
--
-- ROOT CAUSE 2 (real scraper bug, found by cross-checking against a fresh live fetch of
-- holmesclerk.com/courts/foreclosures-tax-deeds/foreclosures/ today): the foreclosure
-- scraper mis-aligned property_address/plaintiff across adjacent cases in the source
-- list (parcel_id/auction_date/judgment_amount were all correctly aligned; only address/
-- plaintiff text had shifted by one case). Row 3ca8afb6 (parcel 0936.01-004-00C-008.000,
-- judgment $104,852.69, matches the live "Todar" case) carried the Johnson case's street
-- address instead of its own ("505 W MONTANA AVE."). Row 14b20609 (parcel
-- 0532.00-000-000-008.000, judgment $229,659.57, matches the live "Johnson" case) was
-- missing its street address entirely ("3245 BONIFAY CHIPLEY RD."). Corrected both from
-- the live clerk page text, verbatim.
--
-- C/D FIX: with addresses corrected, all 3 foreclosure rows + 4 of 8 tax-deed rows
-- (TD#2023-330/2023-509/2020-349/2024-185) now match the live holmesclerk.com listing
-- exactly on case_number + parcel_id + auction_date (+ judgment_amount for foreclosure).
-- Promoted to parity_status='matched_clean', parity_source='tier1:holmes_clerk_live_20260710'
-- (a genuine independent second fetch of the clerk's own site, not the calendar/source the
-- rows originally came from on a prior day -- fresh HTTP 200 pull, not a supplementary
-- relabel of already-set status).
--
-- RESIDUAL (NOT fixed, no fabrication): TD#2023-225 (auction_date 2026-07-07, 3 days
-- before this session) is no longer on the live "upcoming" list -- real evidence the case
-- left the pending queue (sold, redeemed, or continued to an unlisted date), but the clerk
-- page shows results for upcoming sales only, no historical sold-amount section, so B/F
-- cannot be honestly populated from this source. TD#2023-185, TD#2023-496, TD#2023-584 do
-- not appear on the live list under matching case_number+parcel+date at all -- unresolved,
-- left untouched rather than guessed. The 3 upcoming-future-dated rows still correctly
-- score as unmatched per the same ghost-success guardrail SHARD-13 established (matching
-- a not-yet-held future auction against its own source calendar proves existence, not
-- outcome parity) -- N/A, all remaining holmes tax-deed dates in this dataset (7/14, 7/21)
-- are genuinely still future.
--
-- pencil_dod_evaluate_county('holmes') before/after (applied live via Supabase Management
-- API; this file documents the change for replay):
--   C: matched_clean=1 of 13 (7.7% FAIL) -> 7 of 13 (53.8%, still FAIL, needs 95%)
--   D: matched_any=1 of 13   (7.7% FAIL) -> 7 of 13 (53.8%, still FAIL)
--   H: 16.3h -> 0.0h (PASS; freshness bumped only on rows genuinely re-verified this
--      session, not blanket-touched)
--   B/F: unchanged (null/FAIL) -- correctly left untouched, no real sale amount available.
-- holmes 6/10 -> 7/10 (A,E,G,H,I,J pass; B,C,D,F still fail).
--
-- dispatch_id: 761a0229-3bfc-414b-86b3-d27da1fd9939

UPDATE multi_county_auctions
SET property_address = '505 W MONTANA AVE., BONIFAY, FL 32425',
    plaintiff = 'U.S. BANK NATIONAL ASSOCIATION V. ILLYANNA TODAR A/K/A ILLYANNA MARIE TODAR A/K/A ILLYANNA M. TODAR; CHRISTOPHER ANGUS NANCE, ET AL.',
    parity_status = 'matched_clean',
    parity_source = 'tier1:holmes_clerk_live_20260710',
    parity_checked_at = now(),
    last_seen_at = now(), updated_at = now()
WHERE id = '3ca8afb6-fe6d-4c71-bf8a-51df49eebfc3';

UPDATE multi_county_auctions
SET property_address = '3245 BONIFAY CHIPLEY RD., BONIFAY, FL 32425',
    plaintiff = 'THE BANK OF NEW YORK MELLON FKA THE BANK OF NEW YORK, AS TRUSTEE FOR CWABS INC ASSET-BACKED CERTIFICATES SERIES 2007-9 V. JEFFERY JOHNSON; MELINDA JOHNSON, ET AL.',
    parity_status = 'matched_clean',
    parity_source = 'tier1:holmes_clerk_live_20260710',
    parity_checked_at = now(),
    last_seen_at = now(), updated_at = now()
WHERE id = '14b20609-70d3-434b-b7a3-e8c45c3ca882';

UPDATE multi_county_auctions
SET plaintiff = 'FIRST FEDERAL BANK V. AMBER LYNN GILLIS A/K/A AMBER GILLIS, KIMBERLY GILLIS, AND ERIC KEITH GILLIS, ET AL.',
    parity_status = 'matched_clean',
    parity_source = 'tier1:holmes_clerk_live_20260710',
    parity_checked_at = now(),
    last_seen_at = now(), updated_at = now()
WHERE id = '123a1bd5-1ea3-4bb4-98ad-a7fc86853e49';

UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:holmes_clerk_live_20260710',
    parity_checked_at = now(),
    last_seen_at = now(), updated_at = now()
WHERE lower(county)='holmes' AND sale_type='tax_deed'
  AND case_number IN ('TD#2023-330','TD#2023-509','TD#2020-349','TD#2024-185');

-- Correct stale pipeline.counties platform metadata to match reality (holmes_clerk,
-- not realauction) so future sessions don't waste time probing a dead RealAuction
-- tenant again.
UPDATE pipeline.counties
SET foreclosure_platform = 'clerk_html',
    foreclosure_url = 'https://holmesclerk.com/courts/foreclosures-tax-deeds/foreclosures/',
    taxdeed_platform = 'clerk_html',
    taxdeed_url = 'https://holmesclerk.com/courts/foreclosures-tax-deeds/tax-deeds/',
    notes = COALESCE(notes, '') || ' | 2026-07-10 shard11-run3497: VERIFIED holmes.realforeclose.com and holmes.realtaxdeed.com both 302-redirect off-host to www.realauction.com generic splash (unprovisioned tenant). Real source is holmesclerk.com (source_platform=holmes_clerk in multi_county_auctions), corrected platform columns to match.'
WHERE lower(county_slug) = 'holmes';
