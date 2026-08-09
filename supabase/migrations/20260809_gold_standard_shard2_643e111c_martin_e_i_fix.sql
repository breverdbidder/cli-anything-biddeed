-- Gold Standard shard-2 (dispatch 643e111c): martin county E + I.
--
-- BEFORE (live pencil_dod_evaluate_county('martin')):
--   E: FAIL 85.4% (parcel_linked=35/41)
--   I: FAIL 85.4% (card_complete=35/41)
--   all other letters PASS (A/B/C/D/F/G/H/J), G specifically 100% (density) -- not touched.
--
-- 6 gap rows (E requires parcel_id IS NOT NULL; I additionally requires full card data):
--   23001555CCAXMX (fc, 2026-03-24), 25001634CCAXMX (fc, 2026-03-31),
--   25001632CCAXMX (fc, 2026-04-28) -- each had a placeholder property_address
--   ("Stuart, Martin County, FL 34997"), placeholder lat/lng (27.1979,-80.2516),
--   and a round assessed_value, but parcel_id was NULL.
--   26000299CAAXMX (fc, 2026-09-08), 25000496CAAXMX (fc, 2026-09-29),
--   25000102CAAXMX (fc, 2026-09-29) -- no address/geo/value/parcel_id at all.
--
-- METHOD: reused the proven scripts/shard2_run2450_ajax_realforeclose_harvest.py
-- RealForeclose AJAX harvester (documented in that file as already covering martin)
-- against martin.realforeclose.com's live PREVIEW+AJAX endpoint for all 5 target
-- auction dates (03/24, 03/31, 04/28, 09/08, 09/29/2026), decoding the retHTML
-- shorthand and reading each case's raw AITEM block directly (not the harvester's
-- summarized parse) to see the true Parcel ID field content. VERIFIED live
-- 2026-08-09 against the official RealForeclose platform (not a third-party mirror):
--
--   23001555CCAXMX: Parcel ID field = literal "PERSONAL PROPERTY" (linked to
--     https://www.pamartinfl.gov/app/search/pcn/PERSONAL%20PROPERTY), Final
--     Judgment Amount $29,716.55, no Property Address row present at all in the
--     AITEM block. This is an actual personal-property lien foreclosure -- there
--     is no real estate parcel to assign, confirmed by the clerk's own platform,
--     not an ingestion gap.
--   25001634CCAXMX: Parcel ID field = literal "TIMESHARE" (linked to
--     .../pcn/TIMESHARE), Final Judgment Amount $5,246.98, no Property Address row.
--   25001632CCAXMX: Parcel ID field = literal "TIMESHARE", Final Judgment Amount
--     $5,167.17, no Property Address row.
--     (Sibling case 25001650CCAXMX on the same 03/31 docket shows the identical
--     "TIMESHARE" signature -- not in our gap list, i.e. this is a systematic,
--     platform-wide non-parcel category for fractional timeshare-interest
--     foreclosures in Martin, not a one-off data problem.)
--   26000299CAAXMX / 25000496CAAXMX / 25000102CAAXMX: Parcel ID field = empty
--     link text "Property Appraiser" (href .../pcn/%20, i.e. genuinely blank),
--     Final Judgment Amount = $0.00 for all three. These are clerk calendar stub
--     listings for auctions ~7 weeks out (2026-09-08/09-29) where final judgment
--     has not yet been entered, so the platform itself has not yet populated a
--     parcel/address. Cross-checked KBForeclosures (kbforeclosures.com/county/5,
--     1,105 Martin records indexed) and general web search: none of these 3 case
--     numbers appear in any secondary source either -- there is no address/parcel
--     to source anywhere public right now, honestly time-blocked, not a research
--     gap.
--
-- This exactly matches and reconfirms the residual documented in
-- 20260711j_gold_standard_martin_shard5_run3713_pud_wj_and_fabrication_purge.sql:
-- "3 personal-property/timeshare liens with no assessable parcel: structurally
-- unfixable, same ceiling documented in the prior session." Per HARD GUARDRAILS
-- (never fabricate a parcel_id/address/value) and HONESTY PROTOCOL (BLANK > WRONG),
-- no parcel_id is invented for any of the 6 rows this session.
--
-- FIX APPLIED (concrete, not a no-op): the 3 personal-property/timeshare rows
-- (23001555CCAXMX/25001634CCAXMX/25001632CCAXMX) carried a placeholder
-- property_address="Stuart, Martin County, FL 34997" + lat/lng (27.1979,-80.2516,
-- identical across all 3, matching the county-seat generic centroid, not a real
-- situs) + a round assessed_value (150000/180000/180000) from an earlier session,
-- with no data_source evidence supporting those specific numbers and no
-- corresponding parcel_id (E/I already correctly failed these rows). Since the
-- live official platform confirms no real estate parcel/address exists for these
-- 3 cases at all, this placeholder data is corrected to NULL so the row honestly
-- reflects "no card data available" rather than displaying an address/value that
-- cannot be traced to any real parcel. This does not change E or I's pass/fail
-- (both metrics gate on parcel_id, already NULL, unaffected) and does not touch
-- C/D/B/F (parity_status/sold_amount unaffected, confirmed below) or G (zoning,
-- untouched -- these rows have no parcel_zones link either way).
BEGIN;

UPDATE multi_county_auctions
SET property_address = NULL,
    latitude = NULL,
    longitude = NULL,
    assessed_value = NULL,
    updated_at = now()
WHERE lower(county) = 'martin'
  AND case_number IN ('23001555CCAXMX', '25001634CCAXMX', '25001632CCAXMX')
  AND parcel_id IS NULL
  AND property_address = 'Stuart, Martin County, FL 34997'
  AND latitude = 27.1979 AND longitude = -80.2516; -- guard: only touch rows still at the exact placeholder signature

COMMIT;

-- RESIDUAL (unchanged, documented not fixed -- 6/6 rows remain E/I gaps):
--   - 23001555CCAXMX / 25001634CCAXMX / 25001632CCAXMX: structurally unfixable,
--     genuinely no assessable real-estate parcel (personal property / timeshare
--     lien foreclosures per the clerk's own platform). No future session should
--     attempt to assign a parcel_id to these without first finding a primary
--     source that overturns "PERSONAL PROPERTY"/"TIMESHARE" as the platform's
--     own classification.
--   - 26000299CAAXMX / 25000496CAAXMX / 25000102CAAXMX: time-blocked, not yet
--     assessable. Final judgment amount is $0.00 on the live platform (not yet
--     entered) for auctions dated 2026-09-08/09-29. Revisit after final judgment
--     is entered (platform typically populates Parcel ID / Property Address /
--     Assessed Value fields once judgment is final) -- likely resolvable in a
--     later session closer to the sale date, not fixable today.
--   E ceiling given the above: max achievable this campaign without new primary
--   sources = 38/41 = 92.7% (35 already linked + these 3 structurally can't be) --
--   BELOW the 95% PASS threshold even after the 3 time-blocked rows resolve
--   naturally near their sale dates (35+3=38, still <39/41). E/I remain FAIL.
--
-- VERIFICATION QUERY (run after apply):
-- SELECT public.pencil_dod_evaluate_county('martin');
-- Expected: E/I metrics unchanged (still 85.4%, FAIL) -- this migration is a data
-- -integrity correction (removing unsupported placeholder values), not a metric
-- fix; both metrics were already correctly gating on parcel_id IS NULL before and
-- after. C/D/B/F/G/H/J/A confirmed unaffected: parity_status/parity_source/
-- sold_amount/tier1_sold_amount untouched by this migration for all 3 rows
-- (pre-existing parity_status='matched_clean', parity_source='tier1:shard9_run3059_
-- ajax_harvest:...', sold_amount=NULL on all 3, confirmed live before this
-- migration and structurally unreachable by an UPDATE that only sets
-- property_address/latitude/longitude/assessed_value/updated_at).
