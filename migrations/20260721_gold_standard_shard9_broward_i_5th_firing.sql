-- GOLD STANDARD shard-9 (dispatch 20a33672), 5th firing, broward Letter I lane.
--
-- Starting state (re-verified live): I FAIL, card_complete=608 of 652 (93.3%).
-- All 44 gap rows individually inspected against the EXACT join logic used by
-- pencil_dod_evaluate_county (v_zoning_gold_standard_card DISTINCT parcel_id/
-- tax_account with zone_code IS NOT NULL, IN-matched against multi_county_auctions,
-- not a naive LEFT JOIN which fans out and over-counts).
--
-- ============================================================================
-- P0 FINDING (not fixed in this migration -- flagged for AI Architect / next
-- session, same severity class as the 4th firing's bid_decisions fabrication):
-- ============================================================================
-- 600 of broward's 652 filtered auction rows share the EXACT SAME lat/long
-- (26.1224, -80.1373), and this single coordinate accounts for 576 of the 618
-- rows currently counted as "card_complete" toward I's reported 93.3%. Every
-- OTHER populated coordinate in the table appears exactly once (genuine
-- per-parcel geocodes). This is a fallback/default-value geocode masquerading
-- as real per-parcel geo data across a majority of broward's dataset, spanning
-- data_source IN (NULL, 'realforeclose') and created_at 2026-03-09..2026-07-06
-- (multiple ingestion batches, not one bad run). Verified live:
--   SELECT count(*) FROM multi_county_auctions WHERE county='broward'
--     AND latitude=26.1224 AND longitude=-80.1373;  -- 600
-- This migration does NOT attempt a fleet-wide re-geocode (out of scope for
-- the I-lane of this dispatch, high blast radius). It DOES fix the two gap
-- rows below with real geocodes since they were touched anyway. The other 574
-- contaminated-but-currently-"complete" rows are untouched -- I's TRUE honest
-- pass rate is materially lower than 93.3%/95.5% once real geo is required,
-- but re-litigating already-PASS-adjacent rows is out of this lane's scope.
-- ============================================================================
--
-- Fixes applied (11 of 44 gap rows; each backed by a live-fetched source cited
-- inline; all evidence re-verifiable):
--
-- 1-2. Two "gap" parcels (503925081030, 514120150370) exist in fl_parcels'
--      immediate numeric neighborhood but are themselves ABSENT from fl_parcels
--      (confirmed: e.g. ...081020 and ...081040 exist, ...081030 does not).
--      Both are REAL, currently-active BCPA folios -- verified live via
--      https://web.bcpa.net/BcpaClient/search.aspx/getParcelInformation
--      (justValue $1,335,030 / $560,960 respectively). Their EXISTING
--      property_address + lat/long in multi_county_auctions do NOT match
--      BCPA's real situs for these folios (a symptom of the P0 fallback-geo
--      finding above) -- so this migration corrects market_value (from BCPA
--      justValue, which is the field convention already used fleet-wide:
--      market_value = fl_parcels.jv in every sampled row) AND replaces the
--      contaminated lat/long with a real independent geocode (OpenStreetMap
--      Nominatim, ODbL) of BCPA's own situs address. zone_code already existed
--      (has_zone=true pre-migration) so no zoning_districts change needed here.
--
-- 3. CACE-20-018707, "6303 BAY CLUB DR 1" -> parcel_id 494212AK1970. fl_parcels
--    has 4 units at this street address distinguished by phy_addr2 (#1/#2/#3/#4)
--    -- our source address's trailing " 1" maps unambiguously to phy_addr2='#1'.
--    Verified live via BCPA (situs "6303 BAY CLUB DRIVE # 1 FORT LAUDERDALE",
--    justValue $347,740). zone already existed for this jurisdiction.
--
-- 4. COCE-25-001068, "4953 NW 82 AVE" -- NOT FIXED, discovered live during
--    apply: parcel_id 494116AA0120 is exactly ONE fl_parcels row at this
--    address (no ambiguity) and WAS verified live via BCPA (situs "4953 NW 82
--    AVENUE # 302 LAUDERHILL", justValue $250,000) -- but multi_county_auctions
--    has a UNIQUE constraint uq_mca_county_sale_date_parcel on (county,
--    sale_type, auction_date, parcel_id), and case COCE-24-022355 (same
--    address, same auction_date 2025-08-15, same sale_type foreclosure, not
--    yet sold) ALREADY holds this exact parcel_id. This is two distinct real
--    court case numbers referencing what appears to be the same underlying
--    property on the same auction date (e.g. a second lienholder's separate
--    foreclosure action) -- assigning the identical parcel_id to
--    COCE-25-001068 as well would violate the DB's own integrity constraint
--    and was correctly rejected by Postgres on first apply attempt. Left
--    unfixed rather than forcing a constraint override; flagged for review
--    (are these genuinely two liens on one parcel, or a duplicate case-number
--    ingestion defect? -- out of this lane's scope to adjudicate).
--
-- 5-11. Seven tax-deed (TD-) rows needed real per-municipality zoning that the
--    prior firing's Broward-County-unincorporated-only fix did not cover.
--    bcgishub.broward.org/.../ZoningOfficial/FeatureServer/2 (the layer used by
--    the prior firing) is CURRENTLY returning HTTP 500 fleet-wide (re-checked
--    live this session, whole-server error page, not a query-syntax issue) --
--    so a different, cross-verified source was used instead: BCPA's own
--    per-parcel `landCalcZoning` field (web.bcpa.net getParcelInformation),
--    which was independently cross-checked against three municipalities' OWN
--    live zoning GIS layers and matched EXACTLY in all three:
--      - Fort Lauderdale: gis.fortlauderdale.gov/.../ZoningGIS/LayerList/
--        MapServer/15 (point query) -> "RS-8 - Residential Single Family/Low
--        Medium Density" == BCPA landCalcZoning for folio 494212092690.
--      - Pembroke Pines: services6.arcgis.com/OlJkQnf39yF1a7pM/.../
--        Planning_and__Zoning_WFL1/FeatureServer/0 (point query) -> (R-1B),
--        (PUD), (R-MF) == BCPA landCalcZoning for all 3 PP folios.
--      - Lauderhill: gis.lauderhill-fl.gov/server/rest/services/Zoning_1/
--        FeatureServer/0 (point query, geocoded via OSM Nominatim) -> "RM-18 -
--        MULTI-FAMILY (18) RESIDENTIAL" == BCPA landCalcZoning for
--        494126AB2090.
--    Given this 3-for-3 cross-verification, BCPA's landCalcZoning field was
--    used directly for the remaining North Lauderdale and Deerfield Beach
--    rows too (same field, same source, not re-derived from a naming
--    convention guess).
--
--    Density backing (only added where genuinely sourced, never inferred from
--    a code's numeric suffix alone per HONESTY PROTOCOL):
--      - Fort Lauderdale RS-8: WebSearch surfaced a direct quote of Fort
--        Lauderdale ULDC Sec. 47-5.31 ("maximum density of eight dwelling
--        units per net acre") -- max_density_du_acre=8.
--      - North Lauderdale RM-16: BCPA's own zoning-code glossary
--        (bcpa.net/ZoningDefinitions.htm) states explicitly, under the
--        NORTH LAUDERDALE section: "RM-16 RESIDENTIAL MULTI FAMILY (16dua)"
--        -- max_density_du_acre=16.
--      - Lauderhill RM-18: same glossary, LAUDERHILL section: "RM-18
--        MULTI-FAMILY (18) RESIDENTIAL" -- max_density_du_acre=18.
--      - Deerfield Beach RM-15: real official ordinance table (Deerfield Beach
--        Land Development Code Sec. 98-61, Schedule of Dimensional
--        Regulations, fetched live) gives "RM-15 Multi-Family: 2,900 sq.
--        ft./du" -- derived as 43,560 sqft/acre / 2,900 sqft/du = 15.02
--        du/acre (arithmetic on a real sourced ordinance number, not a
--        naming-convention guess). This ALSO backfills Deerfield Beach's
--        PRE-EXISTING RM-15 district (id 2740), which had zero zone_standards
--        rows before this migration -- so this is a genuine gap-close, not
--        just a new-parcel addition.
--      - Pembroke Pines R-1B / PUD / R-MF: verified via BCPA glossary AND
--        Pembroke Pines' own zoning layer that NONE of these three carry a
--        fixed per-district density number in the code (R-1B is a lot-size-
--        based single-family district [min 7,500 sqft, no du/acre cap per
--        codelibrary.amlegal.com Sec. 155.421]; PUD density is set per
--        development order, not a district table; R-MF density is "Consistent
--        with FLUM" per the zoning ordinance, i.e. parcel-specific, not
--        district-wide). density_regulated=false is set explicitly and
--        honestly for these three, matching the real legal structure of the
--        code -- NOT a placeholder.
--
-- Deliberately NOT fixed this session (documented, not forced -- BLANK > WRONG):
--   - Coral Springs (4 TD- rows, RD-8 x3 / RM-20 x1): zone code IS knowable via
--     the same verified BCPA landCalcZoning field, but Coral Springs' EXISTING
--     zoning_districts rows for RD-8/RM-20 (ids 2609/2611) already have
--     density_regulated=NULL and no zone_standards row. Adding parcel_zones
--     here without ALSO sourcing a verified per-district density would
--     introduce new density_applicable=true/max_density_du_acre=NULL rows into
--     broward's G KPI denominator -- the exact self-inflicted-regression
--     pattern the 4th firing hit and had to fix. No live density source was
--     found for Coral Springs RD-8/RM-20 this session (eLaws + Municode both
--     unavailable, HTTP 503, live-checked). Deferred rather than guessed.
--   - Plantation (2 TD- rows, PRD-16Q / PRD-10Q): zone code known via BCPA.
--     pgis.plantation.org is Cloudflare-bot-blocked (HTTP 403, confirmed live
--     with browser UA). Firecrawl API returned HTTP 402 insufficient credits
--     (confirmed live, fleet-wide block per alachua lane's same finding this
--     session). No live density source reachable. Deferred, not guessed.
--   - 3 rows with parcel_id IS NULL (CACE-25-001698, CACE-25-002454,
--     COCE-25-030130): no parcel reference at all in source data; would
--     require independent court-docket research out of this lane's scope.
--   - 6 rows with literal placeholder parcel_id (CACE-24-004661 "MULTIPLE
--     PARCELS", CACE-25-009971/CACE-25-010548/COWE-25-036881 "Property
--     Appraiser", CACE-25-011341/CACE-25-014151 "TIMESHARE"): structurally
--     unresolvable to one parcel, matches prior firing's diagnosis exactly.
--   - 8 rows with a truncated 6-digit parcel_id whose address maps to an
--     ambiguous multi-unit condo/HOA building with NO unit number in the
--     source address (8110 SUNRISE LAKES BLVD x2 [36 units], 101 N OCEAN DR
--     [368 units], 3080 HOLIDAY SPRINGS BLVD x2 [36 units], 1001 THREE ISLANDS
--     BLVD x2 [18 units], 901 COLONY POINT CIR [110 units], 1166 HILLSBORO
--     MILE [15 units], 6161 NW 57 CT x2 [36 units]): blind address match would
--     risk wrong-parcel assignment, explicitly prohibited by this dispatch's
--     boundaries. Left incomplete.
--
-- Net effect: 10 of 44 gap rows closed with real, cited, live-verified data
-- (COCE-25-001068 could not be fixed -- see note above, discovered live via a
-- unique-constraint rejection on first apply attempt, not guessed around).
-- 34 remain incomplete for the structural reasons documented above. Expected
-- new I metric: card_complete rises from 608 to 618 of 652 = 94.8% (still
-- FAIL, just under the 95% threshold) -- reported honestly below, not rounded
-- up. Actual number confirmed via pencil_dod_evaluate_county re-run after
-- apply, not estimated.

BEGIN;

-- ---------------------------------------------------------------------------
-- Fix 1-2: gap-parcel value + real geocode backfill (BCPA + OSM Nominatim)
-- ---------------------------------------------------------------------------
UPDATE multi_county_auctions
SET market_value = 1335030,
    latitude = 26.0719469,
    longitude = -80.4033853
WHERE county = 'broward' AND case_number = 'CACE-16-002149' AND parcel_id = '503925081030';

UPDATE multi_county_auctions
SET market_value = 560960,
    latitude = 26.0005933,
    longitude = -80.2777555
WHERE county = 'broward' AND case_number = 'CACE-22-015602' AND parcel_id = '514120150370';

-- ---------------------------------------------------------------------------
-- Fix 3-4: unambiguous address/unit match to real fl_parcels folios
-- (source multi_county_auctions.parcel_id was a truncated 6-digit prefix;
-- corrected to the real, unambiguous, BCPA-verified folio)
-- ---------------------------------------------------------------------------
UPDATE multi_county_auctions
SET parcel_id = '494212AK1970'
WHERE county = 'broward' AND case_number = 'CACE-20-018707' AND parcel_id = '494124';

-- COCE-25-001068 fix intentionally OMITTED here -- see header note above.
-- Real folio 494116AA0120 already claimed by sibling case COCE-24-022355 for
-- the same (county, sale_type, auction_date); unique constraint
-- uq_mca_county_sale_date_parcel correctly blocks a duplicate assignment.

-- ---------------------------------------------------------------------------
-- Fix 5-11: real per-parcel zoning via BCPA landCalcZoning (cross-verified
-- against 3 municipalities' own live GIS layers, see header notes)
-- ---------------------------------------------------------------------------

-- Fort Lauderdale (jurisdiction_id 913): RS-8
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated, pk1000_regulated)
VALUES (913, 'RS-8', 'Residential Single Family/Low Medium Density', 'residential', NULL, true, false)
RETURNING id;

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url)
SELECT id, 8.00, 'https://gis.fortlauderdale.gov/arcgis/rest/services/ZoningGIS/LayerList/MapServer/15 (cross-verified vs BCPA landCalcZoning + Fort Lauderdale ULDC Sec. 47-5.31)'
FROM zoning_districts WHERE jurisdiction_id = 913 AND code = 'RS-8';

UPDATE multi_county_auctions
SET latitude = COALESCE(latitude, 26.2047117), longitude = COALESCE(longitude, -80.1107986)
WHERE county = 'broward' AND case_number = 'TD-53732' AND parcel_id = '494212092690';

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
VALUES ('494212092690', 913, 'RS-8', 'Residential Single Family/Low Medium Density', 'bcpa_landCalcZoning_verified_vs_fortlauderdale_gis');

-- Pembroke Pines (jurisdiction_id 930): R-1B, PUD, R-MF
-- density_regulated=false is an HONEST reflection of the code, not a
-- placeholder: R-1B is lot-size-based (no du/acre cap), PUD density is set
-- per development order, R-MF density follows FLUM (parcel-specific).
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated, pk1000_regulated)
VALUES
  (930, 'R-1B', 'Residential Single-Family', 'residential', NULL, false, false),
  (930, 'PUD', 'Planned Unit Development', 'residential', NULL, false, false),
  (930, 'R-MF', 'Residential Multi-Family', 'residential', NULL, false, false);

UPDATE multi_county_auctions
SET latitude = COALESCE(latitude, 26.0129583), longitude = COALESCE(longitude, -80.2614488)
WHERE county = 'broward' AND case_number = 'TD-53487' AND parcel_id = '514116020110';
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
VALUES ('514116020110', 930, 'R-1B', 'Residential Single-Family', 'bcpa_landCalcZoning_verified_vs_pembrokepines_gis');

UPDATE multi_county_auctions
SET latitude = COALESCE(latitude, 25.9982349), longitude = COALESCE(longitude, -80.2831639)
WHERE county = 'broward' AND case_number = 'TD-53740' AND parcel_id = '514119060741';
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
VALUES ('514119060741', 930, 'PUD', 'Planned Unit Development', 'bcpa_landCalcZoning_verified_vs_pembrokepines_gis');

UPDATE multi_county_auctions
SET latitude = COALESCE(latitude, 25.9939111), longitude = COALESCE(longitude, -80.3070797)
WHERE county = 'broward' AND case_number = 'TD-53741' AND parcel_id = '514024030181';
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
VALUES ('514024030181', 930, 'R-MF', 'Residential Multi-Family', 'bcpa_landCalcZoning_verified_vs_pembrokepines_gis');

-- North Lauderdale (jurisdiction_id 995): RM-16, 16 dua per BCPA glossary
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated, pk1000_regulated)
VALUES (995, 'RM-16', 'Residential Multi Family (16dua)', 'residential', NULL, true, false)
RETURNING id;

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url)
SELECT id, 16.00, 'https://bcpa.net/ZoningDefinitions.htm (North Lauderdale section: "RM-16 RESIDENTIAL MULTI FAMILY (16dua)")'
FROM zoning_districts WHERE jurisdiction_id = 995 AND code = 'RM-16';

UPDATE multi_county_auctions
SET latitude = 26.2119380, longitude = -80.2010220
WHERE county = 'broward' AND case_number = 'TD-53676' AND parcel_id = '494206CK0280';

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
VALUES ('494206CK0280', 995, 'RM-16', 'Residential Multi Family (16dua)', 'bcpa_landCalcZoning');

-- Lauderhill (jurisdiction_id 990): RM-18, 18 dua per BCPA glossary,
-- cross-verified live vs gis.lauderhill-fl.gov Zoning_1 FeatureServer
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated, pk1000_regulated)
VALUES (990, 'RM-18', 'Multi-Family (18) Residential', 'residential', NULL, true, false)
RETURNING id;

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url)
SELECT id, 18.00, 'https://gis.lauderhill-fl.gov/server/rest/services/Zoning_1/FeatureServer/0 (cross-verified vs BCPA landCalcZoning + bcpa.net/ZoningDefinitions.htm)'
FROM zoning_districts WHERE jurisdiction_id = 990 AND code = 'RM-18';

UPDATE multi_county_auctions
SET latitude = 26.1537101, longitude = -80.2282235
WHERE county = 'broward' AND case_number = 'TD-53726' AND parcel_id = '494126AB2090';

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
VALUES ('494126AB2090', 990, 'RM-18', 'Multi-Family (18) Residential', 'bcpa_landCalcZoning_verified_vs_lauderhill_gis');

-- Deerfield Beach (jurisdiction_id 989): backfill EXISTING RM-15 district
-- (id 2740, previously zero zone_standards rows) with real density derived
-- from Deerfield Beach LDC Sec. 98-61 (2,900 sqft/du -> 43560/2900 = 15.02
-- du/acre)
INSERT INTO zone_standards (
  zoning_district_id, min_lot_sqft, min_lot_width_ft, front_setback_ft,
  side_setback_ft, rear_setback_ft, max_lot_coverage_pct, max_height_ft,
  max_density_du_acre, source_url
)
SELECT id, 2900, 100, 25, 10, 15, 40, 75, 15.02,
  'Deerfield Beach Land Development Code Sec. 98-61 Schedule of Dimensional Regulations (2,900 sq.ft./du -> 43,560/2,900 = 15.02 du/acre)'
FROM zoning_districts WHERE jurisdiction_id = 989 AND code = 'RM-15';

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
VALUES ('484203M10070', 989, 'RM-15', 'Residence, Multi-Family', 'bcpa_landCalcZoning_verified_vs_deerfield_ldc');

COMMIT;
