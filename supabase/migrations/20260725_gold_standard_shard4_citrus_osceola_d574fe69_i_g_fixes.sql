-- Gold Standard shard-4 (citrus, osceola) — dispatch d574fe69-df23-47c4-8c12-db32796f2235
-- Fixes citrus I (card completeness) and osceola I (card completeness) using
-- adversarially-verified findings from an 8-agent research + verify workflow
-- (Citrus Clerk TaxSmartWeb + Citrus County GIS; Osceola County GIS ArcGIS
-- FeatureServer; Osceola Clerk case search). Every value below traces to a
-- source_url captured in the workflow run and independently spot-checked
-- against the live source by the orchestrating session before being applied.
--
-- NOT included: osceola G (zoning FAR/parking/density standards for
-- Kissimmee RA-3/T3/T5-M/SRPUD, St. Cloud R-3, Osceola County E-1/CR/CT) —
-- Municode and American Legal Publishing both returned HTTP 403 (Cloudflare)
-- to automated fetch, firecrawl CLI is not installed in this environment,
-- and the Firecrawl API key is out of credits (HTTP 402). No FAR/density/
-- parking numbers were found from an authoritative ordinance source, so none
-- are written here — guessed standards are BANNED per campaign policy.
--
-- AUDIT FLAG (informational, not fixed by this migration): 405 of osceola's
-- 504 parcel_zones rows carry source='shard4_run5153_osceola_i_default:
-- INCORP_or_nomatch' with zone_code='PD' — a blanket "unmatched" default
-- from a prior session, not researched zoning. The PD district has
-- far_regulated=false, density_regulated=false and category
-- 'planned_development' (excluded from pk1000 applicability), so this does
-- NOT inflate the G pass rate — but it does mean ~80% of osceola's E/I
-- "zone-linked" status rests on a placeholder, not a real zone
-- determination. Flagged for the next session, not touched here.

BEGIN;

-- ============================================================
-- CITRUS: 2 of 14 failing I rows resolved via Citrus Clerk TaxSmartWeb
-- (case-specific tax deed detail pages) + Citrus County GIS (parcel/zoning
-- layers, maps.citrusbocc.com). The other 12 cases are foreclosure
-- calendar entries with no accessible defendant/address key — Citrus
-- Clerk SCORSS case search is CAPTCHA-gated, citrus.realforeclose.com /
-- bid4assets.com return HTTP 403 to automated fetch, and citruspa.org was
-- down for maintenance. Left as-is (UNKNOWN), not fabricated.
-- ============================================================

-- 2026-0134TD: real parcel identified (Cert 23-5450, Parcel ID
-- 18E19S28004A 00730 0085 / PRCLKEY 79073). Confirmed genuinely landlocked
-- (Citrus GIS address-points layer has zero features for this PRCLKEY,
-- while all neighboring parcels have assigned situs addresses) — the
-- existing DB address field's "0 NO ACCESS" portion is correct county
-- data; the "$6,223.00" suffix was a scraper artifact bleeding in from an
-- unrelated field and is removed. Clean address confirmed via
-- https://search.citrusclerk.org/TaxSmartWeb/Home/Details?id=12385
UPDATE multi_county_auctions
SET property_address = '0 NO ACCESS, HOMOSASSA, FL',
    parcel_id = 'CITRUS-PRCLKEY-79073'
WHERE lower(county) = 'citrus' AND case_number = '2026-0134TD';

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT 'CITRUS-PRCLKEY-79073', 1327, 'RUR MH',
       'gold_standard_shard4_d574fe69_citrus_taxdeed_gis_live_verified_20260725'
WHERE NOT EXISTS (
  SELECT 1 FROM parcel_zones WHERE parcel_id = 'CITRUS-PRCLKEY-79073'
);

-- 2026-0147TD: parcel_id 1199611 / address already correct in DB. The gap
-- was purely a missing parcel_zones linkage row. Zone confirmed via
-- spatial intersection of the address-point centroid (Citrus GIS Address
-- Points layer) against the Citrus GIS Zoning polygon layer — resolves to
-- RUR MH (same district as above, id 11957, jurisdiction 1327 Unincorp.
-- Citrus County). A naive attribute join returned a false-positive second
-- district (GNC) caused by PRCLKEY recycling; ruled out via geometry match.
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '1199611', 1327, 'RUR MH',
       'gold_standard_shard4_d574fe69_citrus_taxdeed_gis_live_verified_20260725'
WHERE NOT EXISTS (
  SELECT 1 FROM parcel_zones WHERE parcel_id = '1199611'
);

-- ============================================================
-- OSCEOLA: real address/geo/value enrichment via Osceola County GIS
-- ArcGIS FeatureServer (gis.osceola.org/hosting/rest/services/Parcels).
-- Existing DB values were a useless placeholder ("Osceola County, FL
-- 34741") for all of these, not real scraper output for the specific
-- parcel — a data-quality bug upstream of this session. 3 of ~21 distinct
-- parcels resolved this session (endpoint/field discovery consumed most
-- of the research budget); remaining 18 need a per-case tax-deed-detail
-- lookup (same method as the successful citrus-taxdeed fixes above), not
-- a bare parcel-prefix match against the county-wide parcel layer — our
-- MCA parcel_id for those rows is a non-unique section-level prefix
-- shared by dozens of real parcels, so prefix matching would be a guess.
-- ============================================================

-- Parcel 262630061300 (cases 48482022 and 52562018 — two tax certificates
-- issued against the same parcel in different years). Confirmed via
-- ArcGIS FeatureServer PARCELNO=262630061300011310 AND independently
-- recomputed centroid from the returned polygon geometry by this session
-- (matches to 4 decimal places).
UPDATE multi_county_auctions
SET property_address = '3630 ALLEGRA CIR, SAINT CLOUD, FL 34772',
    latitude = 28.192651,
    longitude = -81.290980,
    assessed_value = 38000
WHERE lower(county) = 'osceola' AND parcel_id = '262630061300';

-- Parcel 133234278000 (case 77492018). Vacant unaddressed lot on State Rd
-- 60 — Okeechobee, FL mailing address is genuinely correct (Osceola
-- County borders Okeechobee County; rural ZIP crosses county lines).
-- Confirmed via ArcGIS FeatureServer PARCELNO=1332342780000C0210, centroid
-- independently recomputed by this session.
UPDATE multi_county_auctions
SET property_address = '0 STATE RD 60, OKEECHOBEE, FL 34972',
    latitude = 27.692137,
    longitude = -80.885533,
    assessed_value = 9600
WHERE lower(county) = 'osceola' AND parcel_id = '133234278000';

-- Parcel 19252900 (case 35192022). Vacant commercial lot. Confirmed via
-- ArcGIS FeatureServer PARCELNO=19252900U001860000.
UPDATE multi_county_auctions
SET property_address = '0 W VINE ST, KISSIMMEE, FL 34746',
    latitude = 28.301722,
    longitude = -81.453740,
    assessed_value = 34600
WHERE lower(county) = 'osceola' AND parcel_id = '19252900';

-- Case 2025 CA 002509 MF: real parcel resolved via Osceola Clerk case
-- search cross-referenced with Osceola County GIS. The DB's prior
-- parcel_id ("OSC-B3906706FDC6") was an internal scraper fallback token,
-- not a real parcel number. Note: this parcel is not yet in parcel_zones,
-- so the zone-linkage component of card_complete remains unresolved for
-- this row (not fabricated — see AUDIT FLAG above re: PD defaults).
UPDATE multi_county_auctions
SET parcel_id = '252628610006000090',
    property_address = '1008 DEDDINGTON PL, KISSIMMEE, FL 34758',
    latitude = 28.17820282512031,
    longitude = -81.49295023766331,
    assessed_value = 121257
WHERE lower(county) = 'osceola' AND case_number = '2025 CA 002509 MF';

-- Case 2025 CA 001061 MF: same pattern, real parcel resolved via Osceola
-- Clerk case search + Osceola County GIS.
UPDATE multi_county_auctions
SET parcel_id = '242528105500010240',
    property_address = '226 MARCELLO BLVD, KISSIMMEE, FL 34746',
    latitude = 28.294221357649597,
    longitude = -81.45772442857948,
    assessed_value = 613200
WHERE lower(county) = 'osceola' AND case_number = '2025 CA 001061 MF';

-- Case 2025 CA 001721 MF: NOT resolved this session (no source found the
-- real parcel behind placeholder "OSC-2CEAE2B1037A") — left untouched.

COMMIT;

-- ============================================================
-- REGRESSION FIX: the 2 new citrus RUR MH parcel_zones rows above (plus 2
-- pre-existing ones) linked to zoning_districts.id=11957, which had ZERO
-- zone_standards on file. Every RUR MH parcel therefore counted as
-- "density-applicable but missing", and adding 2 more pushed citrus G from
-- 95.6% to 94.8% (below threshold) in the same session that was supposed
-- to fix I. Caught by live re-verification before commit, not by luck.
-- Fixed with a REAL, cited value from Citrus County's own official LDC PDF
-- (Chapter Two, Section 2402 "Rural Residential District (RUR)" — "MH" is
-- a manufactured-housing-allowed suffix on the base district per LDC p.
-- 2-43, not a separately standardized district, so RUR MH inherits RUR's
-- Area Requirements verbatim): max density 1.0 unit/10 acres = 0.1 du/acre.
-- FAR at this district is explicitly "non-residential uses only" per the
-- same section, so far_regulated is set false (matches how far_applicable
-- already defaults for residential districts elsewhere in this schema).
-- Result: citrus G returns to PASS at 96.4% (better than the original
-- 95.6% baseline, since it's now backed by a real standard instead of an
-- empty district).
-- ============================================================

BEGIN;

UPDATE zone_standards
SET max_density_du_acre = 0.1,
    ordinance_section = 'Citrus County LDC Ch. 2 Sec. 2402 (RUR)',
    source_url = 'https://cms5.revize.com/revize/citrusfl/document_center/Department/Growth%20Management/LDD/Chapter%202%20-%20Land%20Use%20Districts%202024A12%20rem.pdf',
    confidence_score = 1.0
WHERE zoning_district_id = 11957;

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, ordinance_section, source_url, confidence_score)
SELECT 11957, 0.1, 'Citrus County LDC Ch. 2 Sec. 2402 (RUR)',
  'https://cms5.revize.com/revize/citrusfl/document_center/Department/Growth%20Management/LDD/Chapter%202%20-%20Land%20Use%20Districts%202024A12%20rem.pdf', 1.0
WHERE NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id = 11957);

UPDATE zoning_districts SET far_regulated = false WHERE id = 11957;

COMMIT;
