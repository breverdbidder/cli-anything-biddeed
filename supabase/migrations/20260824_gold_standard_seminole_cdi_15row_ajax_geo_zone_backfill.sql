-- Gold Standard seminole C/D/I fix, 2026-08-24.
--
-- Idempotent reflection of live PostgREST PATCH/POST writes made this session
-- (direct psql/pooler auth confirmed DEAD this session -- "password
-- authentication failed for user postgres" -- all writes executed via REST,
-- this file documents them for replay/audit).
--
-- BEFORE (VERIFIED live, pencil_dod_evaluate_county('seminole'), 2026-08-24):
--   C: matched_clean=133 of 148 = 89.9%  FAIL
--   D: matched_any=133   of 148 = 89.9%  FAIL
--   E: parcel_linked=145 of 148 = 98.0%  PASS (unchanged, not a target letter)
--   G: density=97.9 far=100.0 pk1000=100.0  PASS
--   I: card_complete=133 of 148 = 89.9%  FAIL
--
-- ROOT CAUSE: auctions_total grew 137->148 (11 net new rows) since the last
-- seminole session (20260807d migration). All 15 non-matched-clean/tier1 rows
-- had parity_status=NULL / parity_source=NULL -- genuinely new
-- calendar_sweep_mca_v3 rows (auction dates 2026-08-25 through 2026-10-15)
-- that had not yet been reconciled against the live RealForeclose/
-- RealTaxDeed calendar. This is NOT the PARITY_OK vocabulary trap seen in
-- other counties (sumter/highlands) -- these rows were simply never checked
-- yet.
--
-- FIX METHOD (C/D): ran scripts/shard2_run2450_ajax_realforeclose_harvest.py
-- (the proven RealForeclose/RealTaxDeed AJAX harvester, reused verbatim)
-- against seminole.realforeclose.com for auction dates 08/25, 08/27, 09/03,
-- 09/10, 09/15/2026 and seminole.realtaxdeed.com for 10/15/2026 -- the exact
-- 6 unique dates spanned by the 15 gap rows. Harvest succeeded cleanly: 34
-- items parsed, 34 inserted/merged into realforeclose_aids, zero silent
-- failures. All 15 gap case_numbers were looked up against the harvest by
-- exact case_number match:
--   - 12 matched exactly, with parcel_id/property_address/assessed_value
--     from the live harvest agreeing byte-for-byte (or, for the tax_deed
--     case, closely enough to promote -- see below) with what was already in
--     our DB -- confirms genuine live data, not fabricated. Promoted to
--     parity_status='matched_clean', parity_source='tier1:...'.
--   - 3 (2016CA000953, 2025CA002908, 2024CA002388) matched to harvest items
--     with garbage/non-property parcel_id values ("Property Appraiser" scrape
--     artifact, "LIQUORE LICENSE", "MULTIPLE PARCELS") and no real address --
--     same shape as the already-documented genuinely-blocked rows from the
--     2026-07-25/2026-08-07 seminole I sessions. NOT promoted to
--     matched_clean here (parity fix requires a genuine property match, not
--     just a case-number-only match against a non-property record) -- these
--     remain in whatever parity state they were in; they are NOT part of the
--     15-row C/D promotion below (confirmed: only 12 case_numbers appear in
--     the UPDATE below, not 15).
--
-- AFTER C/D (VERIFIED live): matched_clean=145 of 148 = 98.0% PASS.
--   matched_any=145 of 148 = 98.0% PASS.
--
-- FIX METHOD (I): of the 15 pre-existing I-gap rows, 4 were already
-- documented genuinely-blocked in migrations/20260725_gold_standard_seminole_i_card_completeness.sql
-- (2025CA000629 synthetic parcel, 2025CA002115 "ALCOHOLIC LICENSE",
-- 2025CA000060 "MULTIPLE PARCELS", 2024CA001701 -- NOTE: 2024CA001701 was
-- separately re-confirmed fixed by the 2026-08-07 migration and is NOT in
-- this session's gap list; the 2016CA000953 in this session's gap list is a
-- DIFFERENT, newly-arrived case with the same "Property Appraiser" garbage
-- parcel_id artifact). 2 more (2025CA002908 "LIQUORE LICENSE",
-- 2024CA002388 "MULTIPLE PARCELS") are new rows with the identical
-- non-property garbage-parcel shape as the already-established blocked
-- pattern -- confirmed via direct query: multi_county_auctions.parcel_id is
-- NULL for both live (never backfilled with the harvest's garbage string),
-- property_address/assessed_value/geo all NULL. Per HARD GUARDRAILS #3
-- (BLANK > WRONG), these are left honestly I-blocked, not fabricated.
--
-- The remaining 9 rows had real parcel_ids and were missing only
-- lat/lon, assessed/market value, and/or a parcel_zones link (zone_code):
--
--   case_number             parcel_id                    jurisdiction  zone  gap
--   2025CA001300  01-20-29-504-0000-0330      County Tax District (636)  PD    zone only
--   2025CA001862  02-20-30-5GJ-0000-1000      Sanford (904)              MR-2  zone only
--   2025CA002318  03-21-30-518-0000-0920      Winter Springs (921)       PUD   geo + zone
--   202600007/2024-002033  13-21-29-522-5320-0220  Altamonte (944)       R-3   value + zone
--   2026CA000237  20-19-30-514-0000-5930      County Tax District (636)  PD    zone only
--   2025CC005197  21-21-30-501-0200-0020      Casselberry (850)          CG    geo + zone
--   2025CA002400  31-19-31-501-0C00-0130      Sanford (904)              SR-1  geo + zone
--   2024CA001546  31-21-31-504-0000-0090      County Tax District (636)  R-1A  geo + zone
--   2025CC004562  33-19-31-522-0000-2060      County Tax District (636)  PD    zone only
--
-- SOURCE for parcel_id/zoning code/value (VERIFIED, scpafl.org, live parcel
-- detail pages, fetched 2026-08-24, e.g.
-- https://scpafl.org/search/parcels/details/?PID=0220305GJ00001000 quoted
-- "Market $258,546 Assessed $258,546 ... Tax District Sanford ... Zoning
-- MR2"): all 9 confirmed by direct scpafl.org parcel lookup.
--
-- ZONE CODE NORMALIZATION: scpafl.org renders zoning codes without hyphens
-- for some jurisdictions (e.g. "SR1", "MR2") while our zoning_districts table
-- already stores the canonical hyphenated codes for Sanford ("SR-1", id=6316;
-- "MR-2", id=6319 -- both ALREADY EXIST, already extensively used live: 7+
-- other Sanford parcels already link to SR-1, at least 1 to MR-2). Per the
-- view definition (pg_get_viewdef('v_zoning_gold_standard_card'): LEFT JOIN
-- zoning_districts d ON d.code = pz.zone_code, exact string match required),
-- parcel_zones.zone_code was set to the DB's existing hyphenated code
-- (SR-1/MR-2), NOT scpafl's unhyphenated label, so the join resolves
-- correctly. No new zoning_districts rows were created for Sanford -- both
-- codes already existed.
--
-- All other zone codes (PD/636, PUD/921, R-3/944, CG/850, R-1A/636) also
-- ALREADY EXISTED in zoning_districts prior to this migration (ids 11881,
-- 11872, 11800, 6365, 11876 respectively) -- zero new zoning_districts rows
-- inserted this session, only parcel_zones LINK rows. This is the safest
-- possible I-fix shape: v_zoning_district_applicability's
-- far_applicable/pk1000_applicable/density_applicable flags are a per-district
-- (not per-parcel) property already baked in for every one of these district
-- ids from prior verified sessions, so adding more parcels to them changes
-- letter G's numerator/denominator identically regardless of how many
-- parcels link to them -- confirmed live: G metric IMPROVED slightly
-- (97.9 -> 98.0) after this migration, not regressed.
--
-- SOURCE for lat/lon (VERIFIED): US Census Bureau public geocoder
-- (geocoding.geo.census.gov/geocoder/locations/address), same method used in
-- every prior seminole I session (20260725, 20260807d):
--   2025CA002400  1324 S SUMMERLIN AVE, SANFORD, FL 32771
--     -> matchedAddress "1324 S SUMMERLIN AVE, SANFORD, FL, 32771"
--        y=28.800989994797, x=-81.252404303592
--   2025CA002318  411 GREEN SPRINGS CIR, WINTER SPRINGS, FL 32708
--     -> matchedAddress "411 GREEN SPRING CIR, WINTER SPRINGS, FL, 32708"
--        (Census normalizes "Springs"->"Spring" -- same street, confirmed by
--        ZIP+city+house-number match) y=28.695102868444, x=-81.298868628492
--   2024CA001546  5975 SHERLY ANITA ST, OVIEDO, FL 32765
--     -> matchedAddress "5975 SHERYL ANITA ST, OVIEDO, FL, 32765" (Census
--        corrects our DB's "Sherly"->"Sheryl" typo -- same street, confirmed
--        by ZIP+city+house-number match) y=28.612367312807, x=-81.24695642753
--   2025CC005197  750 E STTE RD 436, CASSELBERRY, FL 32707
--     -> matchedAddress "750 STATE HWY 436, CASSELBERRY, FL, 32707" (Census
--        normalizes "E STTE RD 436"->"STATE HWY 436" -- same street/ZIP/city)
--        y=28.652059759651, x=-81.328890370005
--
-- assessed_value for 202600007/2024-002033 (13-21-29-522-5320-0220): scpafl.org
-- shows Market=Assessed=Taxable=$158,595. Row previously had assessed_value
-- and market_value both NULL live; backfilled both to 158595.
--
-- AFTER I (VERIFIED live): card_complete=142 of 148 = 95.9% PASS (>=95%).
-- 6 residual gap rows (148-142) are the genuinely-blocked non-property rows
-- listed above (2025CA000629, 2025CA002115, 2025CA000060, 2016CA000953,
-- 2025CA002908, 2024CA002388) -- honestly reported, not fabricated.
--
-- REGRESSION CHECK (all VERIFIED via fresh pencil_dod_evaluate_county call
-- immediately after all writes, same session):
--   A: fc=124 td=24 PASS (unchanged)
--   B: verified=63 closed_sold=63 100.0% PASS (unchanged)
--   E: parcel_linked=145 of 148 98.0% PASS (unchanged -- not touched this
--      session; the 12 C/D-promoted rows and 9 I-fixed rows already had
--      parcel_id populated before this migration)
--   F: tier1_sold=63 closed_sold=63 100.0% PASS (unchanged)
--   G: density=98.0 far=100.0 pk1000=100.0 PASS (IMPROVED from 97.9,
--      confirming zero regression from the 9 new parcel_zones inserts)
--   H: 0.0 hours since last_seen PASS (unchanged)
--   J: deal_complete=148 of 148 100.0% PASS (unchanged)

-- ── 1. Diagnostic before update ─────────────────────────────────────────────
DO $$
DECLARE
  v_before jsonb;
BEGIN
  SELECT public.pencil_dod_evaluate_county('seminole') INTO v_before;
  RAISE NOTICE 'Seminole BEFORE: C=% D=% I=%', v_before->'C', v_before->'D', v_before->'I';
END $$;

-- ── 2. C/D promotion: 11 foreclosure rows, live-harvest-confirmed genuine ──
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:seminole_ajax_harvest_20260824:foreclosure'
WHERE county = 'seminole'
  AND case_number IN (
    '2025CA002834', '2025CA000923', '2025CA001533', '2026CA000237',
    '2025CA001862', '2025CA002400', '2025CA001300', '2025CA002318',
    '2024CA001546', '2025CC005197', '2025CC004562'
  )
  AND (parity_status IS DISTINCT FROM 'matched_clean'
       OR parity_source NOT LIKE 'tier1%');

-- ── 3. C/D promotion: 1 tax_deed row, live-harvest-confirmed genuine ───────
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:seminole_ajax_harvest_20260824:tax_deed'
WHERE county = 'seminole'
  AND case_number = '202600007/2024-002033'
  AND (parity_status IS DISTINCT FROM 'matched_clean'
       OR parity_source NOT LIKE 'tier1%');

-- ── 4. I fix: lat/lon backfill (US Census geocoder, VERIFIED) ──────────────
UPDATE multi_county_auctions
SET latitude = 28.800989994797, longitude = -81.252404303592
WHERE lower(county) = 'seminole' AND case_number = '2025CA002400'
  AND parcel_id = '31-19-31-501-0C00-0130' AND latitude IS NULL;

UPDATE multi_county_auctions
SET latitude = 28.695102868444, longitude = -81.298868628492
WHERE lower(county) = 'seminole' AND case_number = '2025CA002318'
  AND parcel_id = '03-21-30-518-0000-0920' AND latitude IS NULL;

UPDATE multi_county_auctions
SET latitude = 28.612367312807, longitude = -81.24695642753
WHERE lower(county) = 'seminole' AND case_number = '2024CA001546'
  AND parcel_id = '31-21-31-504-0000-0090' AND latitude IS NULL;

UPDATE multi_county_auctions
SET latitude = 28.652059759651, longitude = -81.328890370005
WHERE lower(county) = 'seminole' AND case_number = '2025CC005197'
  AND parcel_id = '21-21-30-501-0200-0020' AND latitude IS NULL;

-- ── 5. I fix: assessed/market value backfill (scpafl.org, VERIFIED) ───────
UPDATE multi_county_auctions
SET assessed_value = 158595, market_value = 158595
WHERE lower(county) = 'seminole' AND case_number = '202600007/2024-002033'
  AND parcel_id = '13-21-29-522-5320-0220' AND assessed_value IS NULL;

-- ── 6. I fix: parcel_zones links, all reusing PRE-EXISTING zoning_districts
--    rows (zero new districts created, zero G risk) ────────────────────────
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT v.parcel_id, v.jurisdiction_id, v.zone_code, 'gold_standard_seminole_i_20260824_scpafl_verified'
FROM (VALUES
  ('01-20-29-504-0000-0330', 636, 'PD'),
  ('02-20-30-5GJ-0000-1000', 904, 'MR-2'),
  ('03-21-30-518-0000-0920', 921, 'PUD'),
  ('13-21-29-522-5320-0220', 944, 'R-3'),
  ('20-19-30-514-0000-5930', 636, 'PD'),
  ('21-21-30-501-0200-0020', 850, 'CG'),
  ('31-19-31-501-0C00-0130', 904, 'SR-1'),
  ('31-21-31-504-0000-0090', 636, 'R-1A'),
  ('33-19-31-522-0000-2060', 636, 'PD')
) AS v(parcel_id, jurisdiction_id, zone_code)
WHERE NOT EXISTS (
  SELECT 1 FROM parcel_zones pz WHERE pz.parcel_id = v.parcel_id
);

-- ── 7. Diagnostic after update (regression check on ALL letters) ──────────
DO $$
DECLARE
  v_after jsonb;
BEGIN
  SELECT public.pencil_dod_evaluate_county('seminole') INTO v_after;
  RAISE NOTICE 'Seminole AFTER: %', v_after;
END $$;
