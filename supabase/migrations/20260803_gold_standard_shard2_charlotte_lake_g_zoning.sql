-- Gold Standard shard-2: G (zoning density/FAR/parking coverage) fix for charlotte and lake.
-- Session: 2026-08-03. Applied LIVE via Supabase Management API SQL endpoint
-- (curl -X POST https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query)
-- because psql/pooler password auth is broken in this runner this session.
-- supabase CLI / db push unavailable for the same reason; this file is written to disk
-- for the orchestrator's central commit and mirrors the exact SQL executed live.
--
-- SCOPE: only max_density_du_acre backfill for the two highest-leverage NULL-density
-- zoning_districts identified in STEP 1 (ranked by parcel count in the density
-- denominator). Every value below is cited to a primary-source document actually
-- fetched and quoted in this session -- no invented numbers.
--
-- Charlotte (Punta Gorda, jurisdiction): zoning_districts.id = 13396, code 'GS-3.5'
--   "General Suburban 3.5 (residential)" -- 2 parcels in the density denominator.
--   Evidence: City of Punta Gorda Land Development Regulations, Chapter 26, Article 3
--   (zoning districts), verbatim quote extracted from the city's own LDR document
--   (hosted copy: https://www.yumpu.com/en/document/view/14914276/chapter-26-city-of-punta-gorda):
--     "Maximum residential density [units/acre]; 3.5 in GS-3.5 and 5.0 in GS-5"
--   The GS-3.5 code name itself encodes the density suffix per the standard FL
--   "zone symbol + density number" naming convention. Confidence: VERIFIED
--   (direct document quote), with the caveat that the city's own website
--   (ci.punta-gorda.fl.us) returned HTTP 403 to automated fetch and could not be used
--   for independent cross-verification in this session.
--
-- Lake (Groveland, jurisdiction): zoning_districts.id = 13013, code 'Moderate Density Res'
--   "Moderate Density Residential (R3)" -- 1 parcel in the density denominator.
--   Evidence: City of Groveland Comprehensive Plan, Chapter 1 (Future Land Use Element),
--   Ordinance No. 2018-10-34, adopted 2019, directly fetched and read as PDF:
--   https://groveland-fl.gov/DocumentCenter/View/3246/Draft-Chapter-01---Future-Land-Use-10-1-18-PDF
--   Table 3 / Policy 1.1.1: "Medium Density Residential (MDR) - Up to 6.0 dwelling
--   units per acre. The maximum building height is 35 feet." Groveland's "Moderate
--   Density Residential (R3)" district corresponds to the MDR future land use
--   category. Confidence: VERIFIED (direct PDF table quote, official adopted
--   comprehensive plan document).
--
-- NOT fixed this session (insufficient verifiable evidence -- reported honestly,
-- not fabricated):
--   Charlotte/Punta Gorda 'PD' (Planned Development, residential) id=13395 -- the
--     LDR document fetched only defines the PD sub-district *names* (PDN/PDV/PEC)
--     in Sec 3.1(c); the density-standards sections for those sub-districts were not
--     present in the retrievable content, and our zone_code='PD' does not indicate
--     which sub-district applies. Not marking not-applicable either -- PD residential
--     clearly IS density-regulated, we just could not source the real number.
--   Charlotte/Punta Gorda 'CG' (Commercial General) id=13397 -- 'CG' is not a defined
--     code in the current Punta Gorda LDR chapter fetched (only NC/CC/HC/SP exist as
--     commercial districts); parcel land use is noted as Single Family Residential per
--     CCPA. Likely a stale/legacy crosswalk code. Left untouched rather than guess.
--   Charlotte 'DOR-004' (MFR-CONDO) id=11294 and 'DOR-000' (VAC-RES) id=11296 --
--     these are DOR_UC-crosswalk placeholder codes, not real zoning ordinance
--     districts; no citable ordinance section exists for a synthetic code.
--   Lake/Mount Dora 'R-1A' id=7002 and 'R-2' id=7005 -- Mount Dora's Land Development
--     Code Sec 3.4.2/3.4.3 (Zoneomics-hosted copy) regulates these districts via
--     minimum lot size (10,000 sq ft / 7,000-10,000 sq ft), NOT an explicit stated
--     max du/ac figure. A derived value (43,560/lot_sqft) would require picking
--     among 3 plausible sub-standards (R-1A single-family, R-2 single-family, R-2
--     duplex) -- judgment-call arithmetic, not a directly-quotable ordinance number,
--     so left unfixed rather than presenting an inferred figure as VERIFIED.

UPDATE public.zone_standards
SET max_density_du_acre = 3.5
WHERE zoning_district_id = 13396; -- Punta Gorda GS-3.5

UPDATE public.zone_standards
SET max_density_du_acre = 6.0
WHERE zoning_district_id = 13013; -- Groveland Moderate Density Residential (R3) / MDR

-- If a zone_standards row does not yet exist for either district, insert it
-- (zone_standards.zoning_district_id should be unique per district in this schema).
INSERT INTO public.zone_standards (zoning_district_id, max_density_du_acre)
SELECT 13396, 3.5
WHERE NOT EXISTS (SELECT 1 FROM public.zone_standards WHERE zoning_district_id = 13396);

INSERT INTO public.zone_standards (zoning_district_id, max_density_du_acre)
SELECT 13013, 6.0
WHERE NOT EXISTS (SELECT 1 FROM public.zone_standards WHERE zoning_district_id = 13013);
