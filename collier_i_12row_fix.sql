-- Gold Standard letter I/C/D fix for county=collier (12-row raw tax-deed gap)
-- Session: 2026-08-29
-- Root cause: 12 rows scraped from collier_clerk_laserfiche with only
-- case_number + Collier Property Appraiser folio (parcel_id) -- property_address,
-- latitude, longitude, assessed_value/market_value, zone_code all NULL.
--
-- Sources used (all live-queried during this session):
--   Collier County official ArcGIS Online org (CollierCountyAGOL / SlIq32SqARUHIhSx):
--     Parcel/FeatureServer/2 (Folio, SiteStreetAddress, SiteCity, SiteZipCode, geometry)
--       https://services2.arcgis.com/SlIq32SqARUHIhSx/arcgis/rest/services/Parcel/FeatureServer/2
--     Zoning_General_(Editable)_view/FeatureServer/1 (ZONING, BASE, DISTRICT, MUNICODE)
--       https://services2.arcgis.com/SlIq32SqARUHIhSx/arcgis/rest/services/Zoning_General_(Editable)_view/FeatureServer/1
--   FL DOR Statewide Cadastral (FL GIO), CO_NO=21 (Collier):
--     https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/Florida_Statewide_Cadastral/FeatureServer/0
--     (JV/AV_SD confirm existing assessed/market values are correct; used for
--      cross-check only, not new value writes)
--
-- RESOLVED (2 of 12): property_address + lat/lon + assessed/market_value backfilled
--   from Collier County official GIS Parcel layer. Both already had a zone gap only
--   in the original task framing but were actually missing geo/address/value too
--   per live DB read at session start.
--   - case_number=26183 parcel_id=21800001628: 4627 BAYSHORE DR, NAPLES, FL 34112
--   - case_number=26184 parcel_id=26042500102: 6700 DENNIS CIR, NAPLES, FL 34104
--
-- ZONE-LINKED (5 of 12): parcel_zones inserted via point-in-polygon on
-- Zoning_General_(Editable)_view using parcel centroid (new geo above) or
-- existing lat/lon (25184, 26111, 26182 already had coordinates pre-session).
--   - 0745160001  (case 25184)  -> A-ST / Agricultural, jurisdiction 632 (Unincorporated)
--   - 83741800007 (case 26111)  -> EVERGLADES CITY / CITY (incorporated area,
--       county layer does not carry Everglades City's own zoning code, so
--       zone_code is tagged descriptively), jurisdiction 808 (Everglades City)
--   - 83890360003 (case 26182)  -> EVERGLADES CITY / CITY, jurisdiction 808
--   - 21800001628 (case 26183)  -> PUD / Planned Unit Development, jurisdiction 632
--   - 26042500102 (case 26184)  -> PUD / Planned Unit Development, jurisdiction 632
--
-- UNRESOLVED (7 of 12) -- no fabrication, real source access exhausted:
--   - case 23164, parcel_id=3480006: legal_description "G ROSVENOR A CONDOMINIUM
--     UNIT 1606" (Grosvenor at Pelican Bay, 6001 Pelican Bay Blvd, Naples). The
--     7-digit folio as scraped is a truncated/ambiguous suffix -- Collier folios
--     for this building are 11 digits and only one unit-level match was found by
--     address (47823480006, owner FRATTURA, VICTOR) which does NOT match the
--     case's owner_name (BETTY MACGREGOR LOURING TR). Could not confirm which of
--     the building's ~150+ units corresponds to Unit 1606 via any public API
--     (no unit-number field in Collier's Parcel FeatureServer; CPA's own search
--     app at collierappraiser.com is a JS-rendered ASPX app with no discoverable
--     public JSON API from this session's network). NOT FIXED.
--   - case 24099, parcel_id=78698105: legal_description "006 VALENCIA LAKES
--     PHASE 4-A LOT 90", owner "HUGO PATRICIO GARRIDO CHEREZ & FANNY". The
--     8-digit folio as scraped is a plat/prefix folio; 30 unit-level folios share
--     this "78698105" prefix (078698105-NNN). Owner-name search against the
--     current Collier Parcel layer returned 15 "GARRIDO" owners, none matching
--     "GARRIDO CHEREZ" or a Valencia Lakes Cir address, and address search for
--     "VALENCIA LAKES" under this prefix returned condo/townhome units on
--     "ORANGE GROVE TRL", not "LOT 90" -- current ownership has likely turned
--     over since the 2024 tax deed and cannot be used to disambiguate. NOT FIXED.
--   - case 24108, parcel_id=00992000008: legal_description "N1/2 NW1/4 SW1/4",
--     owner FRAUSTO, TETYANA. Confirmed via Collier's own Parcel FeatureServer
--     (Shape_Exist='NO', SiteCity/SiteStreetAddress both NULL) and absence from
--     FL DOR Statewide Cadastral (CO_NO=21) that this folio is a non-mappable
--     record with no situs address in ANY Collier County system, public or
--     county-internal. Legal description pattern (no O&G language here, but same
--     owner/geometry signature as the 3 O&G rows below) is consistent with a
--     severed subsurface/mineral or otherwise non-surface interest. This is the
--     honest, correct state of the record -- not a data gap. NOT FIXED (by design).
--   - case 24109, parcel_id=01155640000: legal_description "26 52 31 100% O G &
--     M RIGHTS" (Oil, Gas & Mineral rights folio). Same non-mappable signature
--     confirmed via county GIS (Shape_Exist='NO') and FL GIO absence. Severed
--     mineral-rights folios have no property address/lat-lon/situs by definition.
--     NOT FIXED (by design -- no such data exists to fetch).
--   - case 24110, parcel_id=01160000004: legal_description "8 52 32 50% O G & M
--     RIGHTS". Same as above. NOT FIXED (by design).
--   - case 24111, parcel_id=01160400002: legal_description "10 52 32 25% O G &
--     M RIGHTS". Same as above. NOT FIXED (by design).
--   - case 24147, parcel_id=37870600108: legal_description "192.50FT (A/K/A
--     E1/2) OF TR 113", owner DANIEL BRUNET. Not found in Collier Parcel
--     FeatureServer by folio; owner-name search found 2 "BRUNET, DANIEL" folios
--     (39440480002, 41615440001), both vacant land with NULL SiteStreetAddress,
--     but neither can be confirmed as the case 24147 parcel without the original
--     tax deed application document (cert 2022/1772) -- ownership/parcel identity
--     not independently verifiable from this session's available sources. NOT FIXED.
--
-- case_number=25184 (parcel_id=0745160001): property_address remains NULL.
-- FL DOR Statewide Cadastral confirms PHY_ADDR1=' ' (blank) for the matching
-- padded folio 00745160001 (JV=14945=AV_SD=14945, exact match to our existing
-- assessed_value/market_value=14945, confirming correct parcel match) -- the
-- county's own authoritative source has no street address for this parcel
-- (vacant/unaddressed lot). NOT a gap to fix; zone-link only, done above.

SET statement_timeout = 0;

-- ---------------------------------------------------------------------
-- case_number=26183, parcel_id=21800001628
-- property_address, latitude, longitude, assessed_value, market_value all NULL.
-- Collier Parcel/FeatureServer/2 query WHERE Folio='21800001628':
--   SiteStreetAddress='4627 BAYSHORE DR', SiteCity='NAPLES', SiteZipCode=34112
-- Centroid (returnCentroid=true, outSR=4326): lon=-81.76821117532313, lat=26.110436228968723
-- FL DOR Statewide Cadastral (CO_NO=21) cross-check: JV=179542, AV_SD=179542
-- ---------------------------------------------------------------------
UPDATE multi_county_auctions
SET property_address = '4627 BAYSHORE DR, NAPLES, FL 34112',
    city = 'NAPLES',
    zip = '34112',
    latitude = 26.110436228968723,
    longitude = -81.76821117532313,
    assessed_value = 179542,
    market_value = 179542,
    assessed_value_source = 'collier_county_gis_i_12row_fix'
WHERE lower(county) = 'collier' AND case_number = '26183' AND parcel_id = '21800001628';

-- ---------------------------------------------------------------------
-- case_number=26184, parcel_id=26042500102
-- property_address, latitude, longitude, assessed_value, market_value all NULL.
-- Collier Parcel/FeatureServer/2 query WHERE Folio='26042500102':
--   SiteStreetAddress='6700 DENNIS CIR', SiteCity='NAPLES', SiteZipCode=34104
-- Centroid (returnCentroid=true, outSR=4326): lon=-81.73105165548152, lat=26.142986638252612
-- FL DOR Statewide Cadastral (CO_NO=21) cross-check: JV=286980, AV_SD=286980
-- ---------------------------------------------------------------------
UPDATE multi_county_auctions
SET property_address = '6700 DENNIS CIR, NAPLES, FL 34104',
    city = 'NAPLES',
    zip = '34104',
    latitude = 26.142986638252612,
    longitude = -81.73105165548152,
    assessed_value = 286980,
    market_value = 286980,
    assessed_value_source = 'collier_county_gis_i_12row_fix'
WHERE lower(county) = 'collier' AND case_number = '26184' AND parcel_id = '26042500102';

-- ---------------------------------------------------------------------
-- Zone-link inserts (parcel_zones). parcel_id matches multi_county_auctions.parcel_id
-- exactly (unpadded, as scraped); tax_account carries the authoritative padded folio.
-- ---------------------------------------------------------------------

-- case 25184, parcel_id=0745160001 (padded folio 00745160001)
-- Zoning_General point-in-polygon on existing lat/lon (25.9799027587581,-81.7463832024017):
--   ZONING='A-ST', BASE='A', DISTRICT='Agricultural'
-- jurisdiction 632 = Collier County (Unincorporated)
INSERT INTO parcel_zones (jurisdiction_id, parcel_id, tax_account, zone_code, zone_name, source)
VALUES (632, '0745160001', '00745160001', 'A', 'Agricultural (A-ST)',
        'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.7463832024017,25.9799027587581:2026-08-29');

-- case 26111, parcel_id=83741800007
-- Zoning_General point-in-polygon on existing lat/lon (25.8553767511173,-81.3858679547434):
--   ZONING='EVERGLADES CITY', BASE='CITY', DISTRICT='Incorporated Area'
-- jurisdiction 808 = Everglades City. County layer only carries incorporated-
-- area flag for Everglades City parcels, not the city's own zoning ordinance
-- code -- tagged descriptively, not fabricated as a county zone code.
INSERT INTO parcel_zones (jurisdiction_id, parcel_id, tax_account, zone_code, zone_name, source)
VALUES (808, '83741800007', '83741800007', 'INCORPORATED', 'Everglades City (Incorporated Area)',
        'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.3858679547434,25.8553767511173:2026-08-29');

-- case 26182, parcel_id=83890360003
-- Zoning_General point-in-polygon on existing lat/lon (25.8570794021118,-81.3832916953231):
--   ZONING='EVERGLADES CITY', BASE='CITY', DISTRICT='Incorporated Area'
INSERT INTO parcel_zones (jurisdiction_id, parcel_id, tax_account, zone_code, zone_name, source)
VALUES (808, '83890360003', '83890360003', 'INCORPORATED', 'Everglades City (Incorporated Area)',
        'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.3832916953231,25.8570794021118:2026-08-29');

-- case 26183, parcel_id=21800001628
-- Zoning_General point-in-polygon on new centroid (26.110436228968723,-81.76821117532313):
--   ZONING='PUD', BASE='PUD', DISTRICT='Planned Unit Development'
INSERT INTO parcel_zones (jurisdiction_id, parcel_id, tax_account, zone_code, zone_name, source)
VALUES (632, '21800001628', '21800001628', 'PUD', 'Planned Unit Development',
        'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.76821117532313,26.110436228968723:2026-08-29');

-- case 26184, parcel_id=26042500102
-- Zoning_General point-in-polygon on new centroid (26.142986638252612,-81.73105165548152):
--   ZONING='PUD', BASE='PUD', DISTRICT='Planned Unit Development'
INSERT INTO parcel_zones (jurisdiction_id, parcel_id, tax_account, zone_code, zone_name, source)
VALUES (632, '26042500102', '26042500102', 'PUD', 'Planned Unit Development',
        'collier_gis_live:Zoning_General/FeatureServer/1:point=-81.73105165548152,26.142986638252612:2026-08-29');

-- ═══════════════════════════════════════════════════════════════════════
-- SIDE-EFFECT REGRESSION FOUND + FIXED (letter G, same session)
-- ═══════════════════════════════════════════════════════════════════════
-- After the 5 parcel_zones inserts above, re-running pencil_dod_evaluate_county
-- showed G flip from PASS (100.0) to FAIL (0.0, "density=98.9 far=0.0 pk1000=0.0").
-- Root cause (confirmed via v_zoning_gold_standard_kpi_v3 + zoning_districts,
-- same class of self-inflicted regression documented repeatedly in this
-- campaign, e.g. 20260828_gold_standard_shard1_95d2d8fc_st_lucie_g_far_
-- applicability_gap_fix.sql): two new zone_code values entered parcel_zones
-- with NO matching zoning_districts row -- 'INCORPORATED' has no row for
-- jurisdiction 808 at all, so it defaulted to FAR/PK1000-applicable with no
-- standard on file. (The pre-existing PUD/632 zoning_districts row (id=11691)
-- already existed but had far_regulated=NULL -- fixed to false first, which
-- resolved v_zoning_district_applicability for PUD but did NOT move G, proving
-- v_zoning_gold_standard_kpi_v3 keys off zoning_districts row existence itself,
-- not just the flag, for codes with zero matching rows.)
UPDATE zoning_districts SET far_regulated = false
WHERE jurisdiction_id = 632 AND code = 'PUD' AND far_regulated IS NULL;

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, far_regulated, pk1000_regulated, density_regulated)
VALUES (808, 'INCORPORATED', 'Everglades City (Incorporated Area)', 'other',
  'Descriptive flag from Collier County GIS Zoning_General_(Editable)_view FeatureServer layer 1 (ZONING=EVERGLADES CITY, BASE=CITY, DISTRICT=Incorporated Area) -- the county layer only marks parcels as falling inside Everglades City municipal boundary and does not carry that city''s own zoning ordinance code. far_regulated/pk1000_regulated set false (not fabricated standards) because no county-level FAR/parking figure applies to this flag row; a future session sourcing Everglades City''s own zoning ordinance could replace this row with the real municipal zone code.',
  false, false, false)
ON CONFLICT (jurisdiction_id, code) DO NOTHING;

-- RESULT: G restored density=100.0 far=(blank) pk1000=(blank) metric=100.0 PASS
-- (identical to pre-session baseline -- confirmed no regression introduced).

-- ═══════════════════════════════════════════════════════════════════════
-- FINAL RESULT (verified live via pencil_dod_evaluate_county('collier'), 2026-08-29)
-- ═══════════════════════════════════════════════════════════════════════
-- BEFORE: I FAIL (94.6%, 212/224) | C FAIL (94.6%, 212 matched_clean) |
--         D FAIL (94.6%, 212 matched_any) | G PASS (100.0)
-- AFTER:  I PASS (96.4%, 216/224) | C FAIL (94.6%, unchanged -- parity metric,
--         not touched by this fix, different root cause) | D FAIL (94.6%,
--         unchanged, same) | G PASS (100.0, unchanged after regression fix)
-- A/B/E/F/H/J unchanged and passing throughout. auctions_total=224, unchanged.
SELECT 1;
