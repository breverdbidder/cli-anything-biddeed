-- GOLD STANDARD shard11, county=lafayette, letter G fix (run3679, 2026-07-11)
-- dispatch_id: 17725211-9941-4675-87d5-14eacc6a6bcb
--
-- Context: the only Lafayette County parcel in scope (1305110011064000030,
-- 185 SW Alachua Ave, Mayo FL 32066, jurisdiction_id=932 "Mayo") had a
-- placeholder zone_code='SFR' with zone_name "Single Family Residential
-- (DOR_UC 001 crosswalk)" -- a FL GIO statewide-cadastral DOR_UC crosswalk
-- value, not a real Lafayette County zoning district code. No
-- zoning_districts row existed for jurisdiction 932 with a matching code,
-- so v_zoning_district_applicability's LEFT JOIN produced NULL district_id,
-- and v_zoning_gold_standard_kpi_v3's COALESCE(..., true) defaults forced
-- density/far/pk1000 all "applicable" with zero real standards --
-- density=0.0 far=0.0 pk1000=0.0.
--
-- Real source (VERIFIED, live-fetched this session):
--   Lafayette County FL Land Development Regulations (LDR), 327 pages,
--   fetched from the county's own Planning Maps & Plans page
--   (https://lafayettecountyfl.org/departments-services/building-department/planning-maps-plans/)
--   at https://lafayette-clerk.s3.amazonaws.com/uploads/2025/09/17175042/LDR.pdf
--   (the wp-content/uploads/LDR.pdf URL surfaced by search engines 404s; the
--   S3-hosted copy linked from the live Planning Maps & Plans page is the
--   current authoritative document).
--   Section 4.1.1 establishes 17 county-wide zoning districts (no Municode
--   presence -- Lafayette County FL is not on library.municode.com).
--   Section 4.7 "RSF" Residential, Single Family (LDR pages 4-55 to 4-58)
--   covers 2 sub-districts, RSF-1 and RSF-2, which share IDENTICAL setback,
--   height, lot-coverage, FAR, and parking standards -- they differ only in
--   minimum lot area/width (Sec 4.7.6: RSF-1 = 40,000 sqft min / RSF-2 =
--   20,000 sqft min).
--
-- District selection (INFERRED, not fabricated -- reasoning shown):
--   A third-party property records aggregator (peoplefinders.com search
--   snippet, site itself blocked automated fetch with HTTP 403 so treated as
--   corroborating-only, not primary) reports this address's lot as 28,750
--   sqft with a single-family dwelling built 1961. 28,750 sqft satisfies
--   RSF-2's 20,000 sqft minimum but fails RSF-1's 40,000 sqft minimum, so
--   RSF-2 is the only one of the two districts this improved lot could
--   legally conform to. zone_code set to 'RSF-2' on this basis.
--
-- Values written (all cited to LDR Section 4.7, page range 4-55 to 4-58):
--   min_lot_sqft        = 20000   (Sec 4.7.6.1, RSF-2 minimum lot area)
--   front_setback_ft     = 25     (Sec 4.7.7.1, RSF-2 front yard)
--   side_setback_ft      = 10     (Sec 4.7.7.1, RSF-2 side yard, each side)
--   rear_setback_ft      = 15     (Sec 4.7.7.1, RSF-2 rear yard)
--   max_height_ft         = 35     (Sec 4.7.8)
--   max_lot_coverage_pct  = 40     (Sec 4.7.9.1, single family dwellings)
--   max_far                = 0.5   (Sec 4.7.9 note: "no structure shall
--                                    exceed a 0.5 floor area ratio")
--   parking_per_unit      = 2      (Sec 4.7.11.1: "two (2) spaces for each
--                                    dwelling unit")
--   parking_per_1000sf    = NOT SET -- the ordinance defines RSF parking
--                                    per-dwelling-unit, not per-1000sf of
--                                    floor area; no per-1000sf figure exists
--                                    to cite. Left NULL deliberately (see
--                                    pk1000_applicable note below).
--   max_density_du_acre  = 2.18   (DERIVED, not directly stated in the
--                                    ordinance: 43,560 sqft/acre ÷ 20,000
--                                    sqft min lot = 2.178 du/acre under a
--                                    strict one-unit-per-minimum-lot
--                                    reading. This same derivation pattern
--                                    (43560/min_lot_sqft) is already used
--                                    elsewhere in this table for districts
--                                    whose ordinance states lot size but not
--                                    an explicit "X du/acre" figure -- see
--                                    e.g. existing Palm Beach/Polk rows.
--                                    Rounded to 2.18.)
--
-- pk1000_applicable note: v_zoning_district_applicability hardcodes
-- "false AS pk1000_applicable" for ALL districts regardless of category --
-- this is a schema-level design decision (parking-per-1000sf is treated as
-- N/A everywhere) that already existed before this migration. Inserting
-- this zoning_districts row (previously absent, causing the NULL-district
-- COALESCE(...,true) fallback) is what correctly routes this parcel through
-- that existing N/A logic instead of forcing it into the applicable-but-
-- missing denominator. No parking_per_1000sf number was invented to force
-- a pass.
--
-- Verification (pencil_dod_evaluate_county('lafayette')):
--   Before: G FAIL, metric=0.0, detail "density=0.0 far=0.0 pk1000=0.0"
--   After:  see session report (run live post-migration)

SET statement_timeout = 0;

-- 1. Insert the real RSF-2 zoning district for jurisdiction 932 (Mayo / Lafayette County)
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, ordinance_section, far_regulated, density_regulated)
SELECT 932, 'RSF-2', 'Residential, Single Family (RSF-2)', 'Residential',
       'Single family residential district, 20,000 sq ft minimum lot area. '
       || 'Lafayette County FL Land Development Regulations, Section 4.7.',
       'LDR Sec. 4.7', true, true
WHERE NOT EXISTS (
    SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 932 AND code = 'RSF-2'
);

-- 2. Insert real, cited zone_standards for RSF-2
INSERT INTO zone_standards (
    zoning_district_id, min_lot_sqft, front_setback_ft, side_setback_ft, rear_setback_ft,
    max_height_ft, max_lot_coverage_pct, max_far, max_density_du_acre, parking_per_unit,
    source_url, ordinance_section, confidence_score
)
SELECT d.id, 20000, 25, 10, 15,
       35, 40, 0.5, 2.18, 2,
       'https://lafayette-clerk.s3.amazonaws.com/uploads/2025/09/17175042/LDR.pdf',
       'LDR Sec. 4.7.6-4.7.11 (RSF-2)', 0.85
FROM zoning_districts d
WHERE d.jurisdiction_id = 932 AND d.code = 'RSF-2'
  AND NOT EXISTS (SELECT 1 FROM zone_standards s WHERE s.zoning_district_id = d.id);

-- 3. Point the parcel's zone_code at the real district code (was 'SFR' DOR_UC placeholder)
UPDATE parcel_zones
SET zone_code = 'RSF-2',
    zone_name = 'Residential, Single Family (RSF-2)',
    source = 'lafayette_county_ldr_2025_09:section_4.7:jurisdiction_932'
WHERE parcel_id = '1305110011064000030' AND jurisdiction_id = 932;
