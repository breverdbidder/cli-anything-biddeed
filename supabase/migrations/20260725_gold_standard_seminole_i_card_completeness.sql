-- Gold Standard seminole I fix (property card completeness), 2026-07-25.
--
-- Context (VERIFIED live, 2026-07-25):
--   pencil_dod_evaluate_county('seminole').I BEFORE this migration: 93.0% (106/114).
--   pencil_dod_evaluate_county('seminole').I AFTER this migration:  95.6% (109/114) -- PASS.
--   8 gap rows diagnosed this session. This migration fixes 4 of the 8 (the ones with
--   real parcel_ids and fully-sourced address/geo/value/zone data). The remaining 4 are
--   GENUINELY BLOCKED for this session -- see closing report / SUMMIT return payload:
--     - 2025CA000629 (parcel_id='SYN-SEM-2025CA000629'): synthetic placeholder parcel_id,
--       generic county-centroid lat/lon, generic "address pending" placeholder address.
--       realforeclose.com source_url returns HTTP 403 to automated fetch (consistent with
--       prior-session clerk-site blocks); no clerk docket text obtainable this session.
--     - 2025CA002115 (parcel_id='ALCOHOLIC LICENSE'): no address/geo/value at all; a
--       $235,522.21 judgment tied to what the scraper captured as an alcoholic-beverage
--       license, not a real property. No BCPAO/clerk source reachable to confirm/refute.
--     - 2025CA000060 (parcel_id='MULTIPLE PARCELS'): no property_address; cannot
--       identify a single representative parcel without clerk docket access.
--     - 2024CA001701 (parcel_id='Property Appraiser', garbage scrape artifact): real
--       address "250 RAINTREE DR, CASSELBERRY, FL- 32707" but scpafl.org direct PID
--       lookup for this address was not resolved to a specific parcel_id this session
--       (time-boxed; deferred to a future session).
--
-- Fixed rows (4):
--
--   1. case_number 20260057/2024-003818, parcel_id 23-21-29-516-0000-048K
--      (725 Northlake Blvd # 48, Altamonte Springs, FL 32701 -- Hidden Ridge Condo).
--      Already had address+geo. This migration adds assessed_value/market_value and a
--      parcel_zones link.
--      SOURCE (VERIFIED): https://scpafl.org/search/parcels/details/?PID=2321295160000048K
--        (Seminole County Property Appraiser, live parcel lookup, fetched 2026-07-25)
--        quoted: "Address: 725 NORTHLAKE BLVD # 48 ALTAMONTE SPRINGS, FL 32701 |
--        Market Value: $159,600 | Assessed Value: $159,600 | Zoning Code: R-4 |
--        Tax District: Altamonte"
--      Zone code R-4 does NOT yet exist in zoning_districts for jurisdiction_id=944
--      (Altamonte Springs). This session's research into Altamonte Springs LDC Division
--      30 (Development Intensity Standards, via zoneomics.com/code/altamonte-springs-FL/
--      chapter_27) found R-4 density values are Activity-Center-specific ("R-4 | DU/Ac |
--      10 | 25 | 35" -- min/base-max/bonus-max within named activity centers only, NOT a
--      citywide flat value), and it could not be confirmed this parcel sits inside an
--      Activity Center overlay. Per HONESTY PROTOCOL, inventing a zoning_districts+
--      zone_standards row with an unverified density number risks a false-VERIFIED claim
--      and a G-criterion regression (new residential-category district defaults
--      density_applicable=true; an unpopulated max_density_du_acre would count against
--      pct_density_of_applicable). Therefore this migration does NOT insert a
--      parcel_zones row for this parcel -- ONLY the value fields are backfilled here
--      (this row alone does NOT flip to card_complete without a zone -- it remains
--      GENUINELY BLOCKED for I purposes; see rows 2-4 below for the actual I metric
--      movement). Value fields are added because they are real, sourced, and harmless
--      regardless.
--
--   2. case_number 20260026/2024-5114, parcel_id 31-20-30-501-0000-0560
--      (136 Sandalwood Way, Longwood, FL 32750).
--      SOURCE (VERIFIED): https://scpafl.org/search/parcels/details/?PID=31203050100000560
--        (Seminole County Property Appraiser, live parcel lookup, fetched 2026-07-25)
--        quoted: "Address: 136 SANDALWOOD WAY LONGWOOD, FL 32750 | Market Value: $271,781
--        | Assessed Value: $271,781 | Tax District: Longwood | Zoning: Low Density
--        Residential"
--      -> assessed_value/market_value = 271781; tax district "Longwood" = jurisdiction_id
--         810 (City of Longwood); "Low Density Residential" zoning label maps to the
--         EXISTING zoning_districts row jurisdiction_id=810, code='LDR' (id=6155,
--         name "Low density residential (LDR)"), which ALREADY has
--         max_density_du_acre=7.00 populated -- reusing this row is zero-risk to G
--         (no new unpopulated-standards district created).
--      SOURCE for lat/lon (VERIFIED): US Census Bureau geocoder
--        (geocoding.geo.census.gov/geocoder/locations/address), free public government
--        address-point data, same method as scripts/shard_escambia_i_geocode_backfill_20260724.py.
--        Query: street="136 SANDALWOOD WAY", city="LONGWOOD", state=FL, zip=32750.
--        Response matchedAddress: "136 SANDALWOOD WAY, LONGWOOD, FL, 32750",
--        coordinates: y=28.706682543587, x=-81.359030675134.
--
--   3. case_number 20260014/2024-3184, parcel_id 20-20-30-502-0C00-0090
--      (287 Acorn Dr, Longwood, FL 32750).
--      SOURCE (VERIFIED): https://www.scpafl.org/search/parcels/details/?PID=2020305020C000090
--        (Seminole County Property Appraiser, live parcel lookup, fetched 2026-07-25)
--        quoted: "Address: 287 Acorn Dr, Longwood, FL 32750 | Market Value: $159,637 |
--        Assessed Value: $159,637 | Zoning Code: R-1 | Tax District: County Tax District"
--      -> assessed_value/market_value = 159637; "County Tax District" (not "Longwood")
--         = unincorporated Seminole County, jurisdiction_id=636; zone_code='R-1' maps to
--         the EXISTING zoning_districts row jurisdiction_id=636, code='R-1' (id=11875),
--         which has density_regulated=false explicitly set -- this parcel is EXCLUDED
--         from the G density_applicable denominator entirely, making this the safest
--         possible reuse (cannot regress G under any circumstance).
--      SOURCE for lat/lon (VERIFIED): US Census Bureau geocoder, same method as above.
--        Query: street="287 ACORN DR", city="LONGWOOD", state=FL, zip=32750.
--        Response matchedAddress: "287 ACORN DR, LONGWOOD, FL, 32750",
--        coordinates: y=28.726913084962, x=-81.341753799382.
--
--   4. case_number 20260005/1716-2024, parcel_id 11-21-31-504-0B00-0150
--      (300 Roosevelt Sq, Oviedo, FL 32765).
--      SOURCE (VERIFIED): https://www.scpafl.org/search/parcels/details/?PID=1121315040B000150
--        (Seminole County Property Appraiser, live parcel lookup, fetched 2026-07-25)
--        quoted: "Address: 300 ROOSEVELT SQ OVIEDO, FL 32765 | Market Value: $239,855 |
--        Assessed Value: $118,184 | Zoning Code: R-1B | Tax District: Oviedo"
--      -> assessed_value=118184, market_value=239855; tax district "Oviedo" =
--         jurisdiction_id=862 (City of Oviedo).
--      SOURCE for lat/lon (VERIFIED): US Census Bureau geocoder, same method as above.
--        Query: street="300 ROOSEVELT SQ", city="OVIEDO", state=FL, zip=32765.
--        Response matchedAddress: "300 ROOSEVELT SQ, OVIEDO, FL, 32765",
--        coordinates: y=28.672725435978, x=-81.188688296037.
--      Zone code R-1B did NOT exist in zoning_districts for jurisdiction_id=862 prior to
--      this migration (only R-1 id=11837 and R-1C id=11838 existed there). This migration
--      creates it, following the IDENTICAL sourcing + density-derivation methodology
--      already used (and already live in prod) for the sibling R-1/R-1C rows in this same
--      jurisdiction (see migrations/20260711* Oviedo LDC work): source is the same primary
--      document, Oviedo Land Development Code Ordinance 1752 (full text obtained this
--      session via https://www.lowndes-law.com/assets/htmldocuments/Ord1752%20Ex1%20LDC%20Final%20Draft.pdf,
--      a law firm's hosted copy of the adopted ordinance, extracted with pdfplumber).
--      VERIFIED quote, Table 4.1.1 (Zoning Districts and Corresponding FLU
--      Designations), page 59: "Low Density Residential (LDR) ... R-1B / R-1BB / R-1C /
--      R-2" (R-1B is a Low/Medium Density Residential district).
--      VERIFIED quote, Table 4.2.1 (Lot Use Regulations), page 60-61: "R-1B  6,000 sf
--      60 ft. Min  Building 20 ft. Min / Garage 25 ft. Min  7 ft.  25 ft.  35 ft."
--      (min lot size 6,000 sf, min width 60 ft, front setback 20/25 ft, side 7 ft, rear
--      25 ft, max height 35 ft).
--      VERIFIED quote, Section 4.8(C), page 76: "The R-1B, R-1C, R-2, and R-3 Districts
--      are designed for medium density single-family detached, single-family attached
--      (townhome), and two-family residential development generally located in areas
--      with complete urban services."
--      max_density_du_acre: INFERRED as 43,560 sf/acre / 6,000 sf min lot = 7.26 du/acre.
--      This is NOT a directly-stated ordinance number (the LDC regulates R-1B density via
--      minimum lot size, not a stated DU/acre cap) -- it is the same lot-size-to-density
--      derivation mechanism already applied to the R-1 (8,500 sf -> 5.10... du/ac) and
--      R-1C (2,500 sf -> 17.40... du/ac) rows already live in prod for this exact
--      jurisdiction, so this is consistent with established, previously-accepted
--      methodology for this jurisdiction, not a novel guess.
--
-- Safety: rows 2 and 3 reuse existing, already-verified district rows (LDR/810 with
-- density already populated; R-1/636 with density_regulated=false) -- zero G risk. Row 4
-- creates ONE new zoning_districts+zone_standards row (R-1B/862) using the exact same
-- sourcing + derivation methodology as the two sibling rows already live in this
-- jurisdiction, with max_density_du_acre populated (not left null), so it does NOT
-- become an incomplete/unpopulated district in the pct_density_of_applicable denominator.
-- Live-verified after apply: G metric moved 97.2 -> 97.4 (density even improved slightly,
-- confirming no regression), matching the safety condition documented in
-- migrations/20260711d_gold_standard_escambia_g_unincorporated_districts.sql.

SET statement_timeout = 0;

-- ── 1. Diagnostic before update ─────────────────────────────────────────────────
DO $$
DECLARE
  v_before jsonb;
BEGIN
  SELECT public.pencil_dod_evaluate_county('seminole') INTO v_before;
  RAISE NOTICE 'Seminole I BEFORE: %', v_before->'I';
END $$;

-- ── 2. Row 1: 23-21-29-516-0000-048K -- value only (VERIFIED scpafl.org) ─────────
UPDATE multi_county_auctions
SET assessed_value = 159600,
    market_value = 159600
WHERE lower(county) = 'seminole'
  AND parcel_id = '23-21-29-516-0000-048K'
  AND case_number = '20260057/2024-003818'
  AND assessed_value IS NULL
  AND market_value IS NULL;

-- ── 3. Row 2: 31-20-30-501-0000-0560 -- value + geo + zone_code (VERIFIED) ───────
UPDATE multi_county_auctions
SET assessed_value = 271781,
    market_value = 271781,
    latitude = 28.706682543587,
    longitude = -81.359030675134
WHERE lower(county) = 'seminole'
  AND parcel_id = '31-20-30-501-0000-0560'
  AND case_number = '20260026/2024-5114'
  AND latitude IS NULL
  AND assessed_value IS NULL;

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '31-20-30-501-0000-0560', 810, 'LDR', 'gold_standard_seminole_i_20260725_scpafl_verified'
WHERE NOT EXISTS (
  SELECT 1 FROM parcel_zones pz
  JOIN jurisdictions j ON j.id = pz.jurisdiction_id
  WHERE pz.parcel_id = '31-20-30-501-0000-0560' AND j.county ILIKE '%seminole%'
);

-- ── 4. Row 3: 20-20-30-502-0C00-0090 -- value + geo + zone_code (VERIFIED) ───────
UPDATE multi_county_auctions
SET assessed_value = 159637,
    market_value = 159637,
    latitude = 28.726913084962,
    longitude = -81.341753799382
WHERE lower(county) = 'seminole'
  AND parcel_id = '20-20-30-502-0C00-0090'
  AND case_number = '20260014/2024-3184'
  AND latitude IS NULL
  AND assessed_value IS NULL;

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '20-20-30-502-0C00-0090', 636, 'R-1', 'gold_standard_seminole_i_20260725_scpafl_verified'
WHERE NOT EXISTS (
  SELECT 1 FROM parcel_zones pz
  JOIN jurisdictions j ON j.id = pz.jurisdiction_id
  WHERE pz.parcel_id = '20-20-30-502-0C00-0090' AND j.county ILIKE '%seminole%'
);

-- ── 5. Row 4: 11-21-31-504-0B00-0150 -- new R-1B district (VERIFIED, see comment) ─
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section, description, effective_date, density_regulated)
SELECT 862, 'R-1B', 'Single-Family Residential (Medium Density)', 'Residential',
       'ARTIVZODIRE Sec. 4.2, 4.8(C)',
       'R-1B District: one of the R-1B, R-1C, R-2, and R-3 Districts designed for medium density single-family detached, single-family attached (townhome), and two-family residential development generally located in areas with complete urban services. Source: Oviedo Land Development Code Ordinance 1752, Article IV, Section 4.8(C), Table 4.2.1 (min lot 6,000 sf, min width 60 ft, front setback bldg 20ft/garage 25ft, side 7ft, rear 25ft, max height 35ft).',
       '2024-11-05', true
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id=862 AND code='R-1B');

INSERT INTO zone_standards (zoning_district_id, min_lot_sqft, min_lot_width_ft, front_setback_ft, side_setback_ft, rear_setback_ft, max_height_ft, max_density_du_acre, source_url, ordinance_section, effective_date, confidence_score)
SELECT zd.id, 6000, 60.00, 20.00, 7.00, 25.00, 35, 7.26,
       'https://www.lowndes-law.com/assets/htmldocuments/Ord1752%20Ex1%20LDC%20Final%20Draft.pdf',
       'Table 4.2.1 (Lot Use Regulations), min lot size 6,000 sf for R-1B Single-Family Residential (Medium Density). Max density computed as 43,560 sf/acre / 6,000 sf min lot = 7.26 du/acre (same lot-size-based density mechanism already used for R-1/R-1C in this jurisdiction; district explicit purpose is medium-density single-family/townhome per Sec 4.8(C)). Source PDF confirmed via direct WebFetch + pdfplumber text extraction, page 60-61.',
       '2024-11-05', 0.80
FROM zoning_districts zd
WHERE zd.jurisdiction_id=862 AND zd.code='R-1B'
  AND NOT EXISTS (SELECT 1 FROM zone_standards zs WHERE zs.zoning_district_id = zd.id);

UPDATE multi_county_auctions
SET assessed_value = 118184,
    market_value = 239855,
    latitude = 28.672725435978,
    longitude = -81.188688296037
WHERE lower(county) = 'seminole'
  AND parcel_id = '11-21-31-504-0B00-0150'
  AND case_number = '20260005/1716-2024'
  AND latitude IS NULL
  AND assessed_value IS NULL;

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '11-21-31-504-0B00-0150', 862, 'R-1B', 'gold_standard_seminole_i_20260725_scpafl_verified'
WHERE NOT EXISTS (
  SELECT 1 FROM parcel_zones pz
  JOIN jurisdictions j ON j.id = pz.jurisdiction_id
  WHERE pz.parcel_id = '11-21-31-504-0B00-0150' AND j.county ILIKE '%seminole%'
);

-- ── 6. Diagnostic after update ──────────────────────────────────────────────────
DO $$
DECLARE
  v_after jsonb;
BEGIN
  SELECT public.pencil_dod_evaluate_county('seminole') INTO v_after;
  RAISE NOTICE 'Seminole I AFTER: %', v_after->'I';
  RAISE NOTICE 'Seminole G AFTER (regression check): %', v_after->'G';
END $$;
