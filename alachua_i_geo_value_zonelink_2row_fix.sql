-- Gold Standard letter I fix for county=alachua
-- Session: 2026-08-11
-- Ground-truth predicate (from pg_get_functiondef(pencil_dod_evaluate_county)):
--   I denominator = auctions_total (same county filter as everywhere else).
--   Row counts complete only if property_address, COALESCE(lat,po_lat),
--   COALESCE(lng,po_lng), COALESCE(assessed_value,market_value) are all NOT NULL
--   AND parcel_id/tax_account resolves to a zone_code in v_zoning_gold_standard_card.
--
-- Before: I = 88.7% (63/71), 8 offending rows (per prior audit).
-- After this fix: I = 91.5% (65/71). Still FAILS (<95), 6 rows remain BLOCKED
-- (see notes at bottom -- no fabrication, real source access was unavailable).
--
-- Sources used (all live-queried during this session):
--   Alachua County GIS Hosted/ParcelsPublic FeatureServer
--     https://maps.alachuacounty.us/server/rest/services/Hosted/ParcelsPublic/FeatureServer/0
--     (parcel centroid lat/lng via returnCentroid=true,outSR=4326; justvalue = assessed value)
--   Alachua County GIS Hosted/ZoningCountyWidePublic FeatureServer
--     https://maps.alachuacounty.us/server/rest/services/Hosted/ZoningCountyWidePublic/FeatureServer/0
--     (point-in-polygon zoning lookup on parcel centroid / existing lat-lng)

SET statement_timeout = 0;

-- ---------------------------------------------------------------------
-- Row 1: case_number = '01 2024 CC 005935', parcel_id = '07242-130-305'
-- Address, lat/lng, assessed_value were all NULL. property_address was
-- already partially populated ("4411 SW 34TH ST UNIT 1305") from our own
-- data_source=calendar_sweep_mca_v3, matching GIS address1 "4411 SW 34TH
-- ST #1305" (unit variant) -- confirms correct parcel match.
-- GIS query: WHERE parcel='07242-130-305' -> justvalue=155000,
--   centroid (outSR=4326, returnCentroid=true) = (-82.36956030361496, 29.61339401554312)
-- ---------------------------------------------------------------------
UPDATE multi_county_auctions
SET latitude = 29.61339401554312,
    longitude = -82.36956030361496,
    assessed_value = 155000,
    assessed_value_source = 'alachua_county_gis_parcelspublic'
WHERE lower(county)='alachua' AND case_number = '01 2024 CC 005935'
  AND parcel_id = '07242-130-305';

-- Zoning lookup for the same parcel's centroid against ZoningCountyWidePublic:
-- geometry=-82.36956030361496,29.61339401554312 -> zonedistrict='RMF8',
-- juris=300 (=Gainesville, our jurisdiction_id 915). zoning_districts.id=12932
-- (jurisdiction_id=915, code='RMF8') ALREADY EXISTS in our schema with
-- density_regulated=false explicitly set -- so this insert does NOT add an
-- un-standardized parcel to G's density_applicable denominator (verified via
-- v_zoning_gold_standard_kpi_v3 before/after: density metric 96.1 -> 96.2, i.e.
-- it improved, did not regress).
INSERT INTO parcel_zones (jurisdiction_id, parcel_id, tax_account, zone_code, zone_name)
VALUES (915, '07242-130-305', '07242-130-305', 'RMF8', 'Multi-Family Medium Density Residential (RMF8)');

-- ---------------------------------------------------------------------
-- Row 2: case_number = '01 2025 CA 001634', parcel_id = '04321-007-000'
-- property_address, latitude/longitude, assessed_value were ALL already
-- present and correct (1123 NW 107TH TER, GAINESVILLE, FL 32606;
-- lat=29.663635, lng=-82.456068; assessed_value=437263). The ONLY gap was
-- zone-link: parcel_id had zero rows in v_zoning_gold_standard_card for
-- alachua (confirmed 0 rows pre-fix).
-- GIS query: geometry=-82.456068,29.663635 -> zonedistrict='R-1A',
-- juris=0 (=Alachua County/unincorporated, our jurisdiction_id 1404).
-- zoning_districts.id=11782 (jurisdiction_id=1404, code='R-1A') ALREADY
-- EXISTS with zone_standards populated (max_density_du_acre=4.00,
-- source: https://library.municode.com/fl/alachua_county/codes/code_of_ordinances?nodeId=PTIIIUNLADECO_TIT40LADERE_CH403ZODI,
-- ordinance Ch. 403 Art. 3 Sec. 403.07 Table 403.07.1). This insert
-- IMPROVES G's density coverage (adds a standards-complete parcel).
-- ---------------------------------------------------------------------
INSERT INTO parcel_zones (jurisdiction_id, parcel_id, tax_account, zone_code, zone_name)
VALUES (1404, '04321-007-000', '04321-007-000', 'R-1A', 'Residential Single Family (R-1A)');

-- ---------------------------------------------------------------------
-- RESULT (verified via public.pencil_dod_evaluate_county('alachua')):
--   Before: I = 88.7% (63/71 complete)
--   After:  I = 91.5% (65/71 complete)   <- still FAILS (threshold 95%)
--   G (side effect, not the target letter): 96.1% -> 96.2% (improved, not regressed)
--   E unchanged (94.4%, out of scope for this letter/session)
--
-- REMAINING 6 OFFENDING ROWS -- BLOCKED, not fixed this session:
--   1. '01 2025 CA 001928' -- parcel_id/address/geo/value all NULL.
--      No case-docket source accessible: Municode 403s WebFetch, Alachua
--      Clerk court-records portal requires login, alachuaforeclosures.com
--      403s, alachua.realforeclose.com auction-detail pages return a JS/
--      session-gated splash page (not the case detail) to unauthenticated
--      curl/WebFetch, and no browser-automation tool (browser-use CLI) is
--      installed in this environment. BLOCKED -- no real source found.
--   2. '01 2025 CA 002643' -- same as above (parcel_id/address/geo/value
--      NULL, data_source NULL, no accessible docket). BLOCKED.
--   3. '01 2025 CA 003919' -- same as above; has a direct realforeclose
--      AID=1509514 detail URL but it also resolves to the login/session
--      splash page for unauthenticated fetch. BLOCKED.
--   4. '01 2025 CA 003287' -- property_address is a placeholder string
--      "ALACHUA COUNTY FL" (not a real street address), lat/lng
--      (29.6516,-82.3248) is a generic county-seat centroid, not the
--      actual property location. Reverse-geocoding that placeholder
--      point against Hosted/ParcelsPublic returns parcel '14621-000-000'
--      (12 SE 1ST ST, justvalue=$10.48M -- clearly a downtown/government
--      commercial parcel, not this residential foreclosure). Assigning
--      that parcel would be fabrication. Real case-docket lookup is
--      required and is blocked for the same reasons as rows 1-3.
--   5. '01 2025 CA 003415' (parcel_id='05900-903-016') -- address/geo/
--      value present and correct. GIS zoning lookup returns
--      zonedistrict='PUD' in the City of Alachua (jurisdiction_id=973).
--      No 'PUD' zoning_districts row exists for jurisdiction 973 (only
--      PD-COMM/PD-EC/PD-R/PD-TND, none of which have max_density_du_acre
--      populated either). Inserting a new parcel_zones row with an
--      unmapped zone_code would add an un-standardized parcel to G's
--      density_applicable denominator and could regress G (currently
--      passing at 96.2%, margin is thin: 49/51 -> would become fewer
--      than 95% if 2 more unregulated parcels are added without real
--      density data). Verifying whether City-of-Alachua PUD density is
--      code-regulated vs. set per master development plan requires the
--      Municode ordinance text, which 403s all available fetch tools in
--      this session. BLOCKED -- would require fabricating either the
--      zone_code mapping or the density-applicability claim.
--   6. '01 2026 CA 000211' (parcel_id='07332-200-004') -- address/geo/
--      value present and correct. GIS zoning lookup returns
--      zonedistrict='U7' in Gainesville (jurisdiction_id=915). No 'U7'
--      zoning_districts row exists (Gainesville only has U2/U3/U4/U9
--      mapped). Same G-regression risk and same Municode-access block
--      as row 5. BLOCKED for the same reason.
--
-- NEVER-LIE: rows 1-6 above are reported BLOCKED, not silently skipped or
-- fabricated. No PropertyOnion data was used or counted as authoritative.
-- No cron jobs, other counties, or other letters' scoring logic were
-- touched.
