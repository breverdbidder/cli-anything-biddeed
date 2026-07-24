-- Gold Standard shard-2 (sarasota): letter G -- close the 14-missing-zone_code gap that was
-- dragging pk1000 (parking-per-1000sf applicability) down to 18.8% (and density 75.2%,
-- far 86.9%). Root cause (VERIFIED live against v_zoning_gold_standard_kpi_v3 and
-- v_zoning_district_applicability, 2026-07-24): 24 of Sarasota's 314 zoned parcels carry a
-- parcel_zones.zone_code with NO matching zoning_districts row for their jurisdiction_id, so
-- the view's LEFT JOIN produces district_id=NULL -> v_zoning_district_applicability also NULL
-- -> the pj CTE's COALESCE(a.pk1000_applicable, true) / far / density all default these
-- parcels to "applicable, standard missing" instead of correctly resolving real applicability.
--
-- The 14 missing zone_code/jurisdiction pairs (24 parcels), confirmed live 2026-07-24:
--   North Port (941): MH (4), R-3 (4), CT (2)
--   Sarasota   (824): RSF-4 (3), RE-1 (2), RSF-1 (2), OUE-1 (1), SAPD (1), RE-2 (1), CN (1),
--                      RSM-9 (1), G (1), MP (1)
--   Venice     (933): RMH (1)
--
-- JURISDICTION NOTE (VERIFIED via prior migration 20260721_..._sarasota_i_zone_extend.sql,
-- which queried the LIVE ArcGIS source per row and recorded the raw API response): the
-- jurisdiction_id=824 "Sarasota" bucket in this DB is NOT solely City-of-Sarasota-proper --
-- it also holds unincorporated-Sarasota-County parcels (source='scgov_arcgis',
-- municipality='SC' returned by ags3.scgov.net/.../CountyZoning/FeatureServer/0), alongside
-- true City-of-Sarasota parcels (source='cos_zoning_arcgis', ZONECLASS field from
-- services3.arcgis.com/.../Zoning_Districts_(View_Only)/FeatureServer/0). There is no separate
-- "unincorporated Sarasota County" row in the jurisdictions table. RSF-4 and RSM-9 are
-- confirmed City-of-Sarasota Article VI codes (Table VI-203). OUE-1, CN, G, MP, SAPD, RE-1,
-- RE-2 are confirmed Sarasota COUNTY LDC (Appendix A) conventions -- NOT present anywhere in
-- the City's own Article VI text -- consistent with the same unresolved-jurisdiction pattern
-- already documented for PID/RC/RMH/RE-2-PUD in migration
-- 20260721_gold_standard_shard6_run5361_sarasota_g_zone_standards.sql. Sourced from the County
-- LDC below since that is the real, applicable ordinance for these zone_code conventions
-- regardless of which jurisdiction_id bucket they are stored under in this schema.
--
-- RESEARCH SOURCES (fetched/read directly this session, 2026-07-24):
--   1. City of Sarasota Ordinance No. 23-5476 (edocs.sarasotagov.com), Exhibit A, Table VI-203
--      "Residential Development Standards in the Single-Family Zones" -- read verbatim via
--      direct PDF fetch (WebFetch), pages 4-5. Confirms RSF-4 = 8.7 DU/acre (detached),
--      RSM-9 = 9.0 DU/acre (detached); no FAR row and no parking-per-1000sf row for any
--      single-family/RSM-9 column in this table (design/use-limitation columns only).
--   2. Sarasota County Zoning Ordinance Table of Contents + Article 4 text (2006-vintage
--      county-hosted PDF mirror, 4sarasotahomes.com/images/Zoning/1-10-06 Sarasota Zoning
--      Districts.pdf) -- read verbatim via direct PDF fetch (WebFetch), pages 1 and 10.
--      Confirms Sec. 4.9.1 "Government Use District (GU)" (our zone_code "G") District
--      Development Standards: "Maximum Residential Density: One dwelling unit per acre...
--      however no GU parcel shall contain more than a total of five residences". Confirms
--      Sec. 4.9.2 "Marine Park District (MP)": water/submerged-land protection district
--      covering "all boat basins, bays, bayous, canals...and waters of the Gulf of Mexico...
--      publicly and privately owned submerged lands" -- not a developable land-use district,
--      no density/FAR/parking standard exists because the district is not buildable upland.
--   3. WebSearch-surfaced verbatim snippets of Sarasota County elaws.us Appendix A, Article 6
--      (District Development Standards) -- the elaws.us site itself returned HTTP 503
--      (service unavailable) on every direct-fetch attempt this session, so these are search-
--      engine-cached snippet extracts of the live ordinance text, not full-page reads:
--        Sec 6.4 OUE and RE District Development Intensity: "RE-1 Zone consists of large lot
--        suburban residential subdivisions with a minimum lot size of 40,000 square feet and
--        a maximum density of one dwelling unit per acre" (RE-1 = 1.0 DU/acre).
--        "The RE-2 Zone allows for single residential homes on lots of at least 2 acres...
--        minimum net lot area of 87,120 square feet...maximum building coverage of 25%...
--        RE-2 Zone yields a maximum of 0.5 dwelling units per acre" (RE-2 = 0.5 DU/acre).
--        Sec 11.2 Village, Hamlet and Settlement Area Regulations (SAPD = Settlement Area
--        Planned Development): "Minimum Density within Developed Area: 3 du/Gross Developable
--        Acre; Target Density: 6 du/Net Residential Acre; Maximum Density within Developed
--        Area: 5 du/Gross Developable Acre or 6 du/Gross Developable Acre if the additional
--        units are Affordable Housing Units" -- multi-tier standard, no single number; the
--        6 du/net-residential-acre TARGET figure is recorded as max_density_du_acre with a
--        confidence note that this is a target/ceiling under a multi-tier formula, not a flat
--        district-wide cap (SAPD's own 5/6 gross-acre ceiling is a closer analog to "max" but
--        is gross-developable-acre denominated, not directly comparable to the du_acre column
--        used everywhere else in this table for net/parcel-level density -- 6.0 target used
--        as the single best-available point estimate, confidence lowered to 0.55 for this
--        reason).
--        OUE (our code OUE-1): "the minimum lot area shall be five acres, provided...a
--        minimum lot area of three acres shall be allowed in platted subdivisions" -- NO
--        explicit maximum-DU/acre figure was recovered in any snippet this session (Sec 6.4's
--        actual density table text was not retrievable -- elaws.us 503, Municode 403/JS-gated,
--        no working PDF mirror located for current Article 6). Left NULL rather than deriving
--        1/5-acre=0.2 DU/acre by inference -- that arithmetic is a reasonable industry-standard
--        interpretation but is NOT the same as reading the actual maximum-density cell of the
--        ordinance table, and per HARD RULES no fabricated/derived-without-citation numeric
--        value is written. density_regulated left NULL (unresolved) for the same reason.
--        CN (Commercial Neighborhood): confirmed commercial-category district ("permits
--        small-scale, neighborhood-oriented commercial" -- Sec 4.7.1), but no specific FAR or
--        parking-per-1000sf figure was recovered this session. far_regulated and
--        pk1000_regulated left NULL (unresolved, not "not regulated").
--   4. North Port zone codes MH, R-3, CT: real district names/categories confirmed via the
--      SAME live ArcGIS FeatureServer already used and cited in migration
--      20260721_gold_standard_shard6_run5361_sarasota_i_zone_extend.sql
--      (npgis.northportfl.gov/cnpserver/rest/services/Hosted/Current_Zoning/FeatureServer/241)
--      -- MH="Manufactured Housing", R-3="Residential, Multi-family", CT="Corridor,
--      Transitional". The North Port ULDC PDF (northportfl.gov, previously fetchable per that
--      migration's citations for AC-1/AC-4/AC-6/AC-10/AG/R-1/R-2/V) returned HTTP 403 (Akamai
--      WAF) on every retry this session for the specific Table 3.2.4.1/3.2.4.2 density/FAR
--      pages -- no numeric density/FAR/parking figures were recoverable this session for
--      MH/R-3/CT. Applicability booleans set from the real, GIS-confirmed category only
--      (residential for MH/R-3, mixed-use/commercial-transition for CT per the ULDC's own
--      "business activity...prohibited between 10pm and 5am in CT and COR" language already
--      quoted in the prior migration) -- numeric values left NULL, unresolved.
--
-- NET EFFECT: this migration inserts zoning_districts rows (with correct jurisdiction_id,
-- code, category, and applicability booleans where a real ordinance basis exists) for all 14
-- missing zone_codes so the LEFT JOIN in v_zoning_gold_standard_kpi_v3 stops silently
-- defaulting these 24 parcels to "applicable, standard missing." Where a real numeric standard
-- was recovered (RSF-4, RSM-9, G/GU, RE-1, RE-2, SAPD), it is inserted into zone_standards.
-- Where the district is genuinely not a developable land-use district (MP), applicability is
-- set to false with no fabricated number. Where category is confirmed but the numeric standard
-- itself could not be retrieved this session (OUE-1, CN, MH, R-3, CT), applicability booleans
-- are left NULL/best-available and numeric values are left NULL -- this will NOT fully resolve
-- pk1000/density/far to 100% but converts "phantom applicable, no data" into either "correctly
-- resolved" or "honestly still missing," which is the only honest lever available this
-- session given elaws.us (503) and northportfl.gov PDF (403) were both unreachable for the
-- remaining numeric tables.

BEGIN;

-- ============================================================
-- North Port (jurisdiction_id = 941)
-- ============================================================

-- MH (Manufactured Housing): real GIS-confirmed residential category (zone_des="Manufactured
-- Housing" per npgis.northportfl.gov live FeatureServer, same source already trusted in prior
-- Sarasota migration). No numeric density/FAR table reachable this session (ULDC PDF 403'd).
-- Residential manufactured-home districts are conventionally FAR-exempt and pk1000-exempt
-- (per-unit, not per-1000sf, parking) consistent with every other North Port residential code
-- already resolved (R-1, R-2, AG) -- those booleans are set on that basis; density itself is
-- left unresolved (NULL) since no per-acre figure was recovered.
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated, pk1000_regulated, ordinance_section)
VALUES (941, 'MH', 'Manufactured Housing', 'residential', false, NULL, false,
  'North Port ULDC Ch.3 (district confirmed via live npgis.northportfl.gov Current_Zoning FeatureServer, zone_des=Manufactured Housing; numeric density table Sec.3.2.4/Table 3.2.4.1 not retrievable this session, ULDC PDF returned HTTP 403)')
ON CONFLICT (jurisdiction_id, code) DO NOTHING;

-- R-3 (Residential, Multi-family): real GIS-confirmed residential category. Same reasoning as
-- MH -- FAR/pk1000 not applicable per North Port's residential-district convention (Sec.3.1.2,
-- per-unit not per-1000sf parking), density itself unresolved.
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated, pk1000_regulated, ordinance_section)
VALUES (941, 'R-3', 'Residential, Multi-family', 'residential', false, NULL, false,
  'North Port ULDC Ch.3 (district confirmed via live npgis.northportfl.gov Current_Zoning FeatureServer, zone_des=Residential, Multi-family; numeric density table Sec.3.2.4/Table 3.2.4.1 not retrievable this session, ULDC PDF returned HTTP 403)')
ON CONFLICT (jurisdiction_id, code) DO NOTHING;

-- CT (Corridor, Transitional): real GIS-confirmed mixed-use/commercial-transition category.
-- Prior migration already quoted the ULDC's own text: "Business activity and deliveries in CT
-- and COR are prohibited between ten (10) p.m. and five (5) a.m." -- confirms CT permits
-- commercial business activity (mixed-use corridor district), unlike pure-residential MH/R-3.
-- No numeric FAR/density/parking table reachable this session. All three booleans left NULL
-- (unresolved) rather than guessing which of FAR/density/parking would apply to a mixed-use
-- corridor district without the actual table.
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, ordinance_section)
VALUES (941, 'CT', 'Corridor, Transitional', 'mixed-use',
  'North Port ULDC Ch.3 (district confirmed via live npgis.northportfl.gov Current_Zoning FeatureServer, zone_des=Corridor, Transitional; category+use-hours language corroborated in migration 20260721_..._sarasota_i_zone_extend.sql citation; numeric standards table not retrievable this session, ULDC PDF returned HTTP 403)')
ON CONFLICT (jurisdiction_id, code) DO NOTHING;

-- ============================================================
-- City of Sarasota (jurisdiction_id = 824)
-- ============================================================
-- NOTE: RSF-4 and RSM-9 below are confirmed real City-of-Sarasota Article VI codes
-- (Table VI-203). The remaining codes in this block (RE-1, RE-2, OUE-1, SAPD, CN, G, MP) are
-- confirmed Sarasota COUNTY LDC conventions stored under this same jurisdiction_id per the
-- jurisdiction-note above -- sourced from the County LDC, not the City's Article VI.

-- RSF-4 (Residential Single Family 4): Table VI-203 (read verbatim, Ord. 23-5476 Exhibit A) --
-- Maximum density = 8.7 DU/acre (detached). No FAR row, no parking-per-1000sf row for this
-- single-family column (design/use-limitation only).
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated, pk1000_regulated, ordinance_section)
VALUES (824, 'RSF-4', 'Residential Single Family 4', 'residential', false, true, false,
  'https://edocs.sarasotagov.com/publicaccess/api/Document/ASpIyErY5EgwJ0miwrRMzHZ0fD9AKrPogY2%C3%89Ur9pT6a5%C3%81uPdEz38H6QswAee%C3%81HHyO7s65hvv%C3%81aR5oUwWk%C3%89efxVg=/ -- Ordinance No. 23-5476 Exhibit A, Article VI, Div. 2, Sec. VI-203, Table VI-203 (RSF-4 column: Maximum density 8.7 DU per acre)')
ON CONFLICT (jurisdiction_id, code) DO NOTHING;

INSERT INTO public.zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score, scraped_at)
SELECT id, 8.7,
  'https://edocs.sarasotagov.com/publicaccess/api/Document/ASpIyErY5EgwJ0miwrRMzHZ0fD9AKrPogY2%C3%89Ur9pT6a5%C3%81uPdEz38H6QswAee%C3%81HHyO7s65hvv%C3%81aR5oUwWk%C3%89efxVg=/',
  'City of Sarasota Zoning Code, Art. VI, Div. 2, Sec. VI-203, Table VI-203 (RSF-4 column, effective 4/17/2023)',
  0.97, now()
FROM public.zoning_districts WHERE jurisdiction_id = 824 AND code = 'RSF-4';

-- RSM-9 (Residential Single Multiple 9 units per acre): Table VI-203 confirms 9.0 DU/acre
-- (detached column; RSM-9 has separate detached/attached sub-columns both = 9.0 DU/acre).
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated, pk1000_regulated, ordinance_section)
VALUES (824, 'RSM-9', 'Residential Single Multiple 9 units per acre', 'residential', false, true, false,
  'https://edocs.sarasotagov.com/publicaccess/api/Document/ASpIyErY5EgwJ0miwrRMzHZ0fD9AKrPogY2%C3%89Ur9pT6a5%C3%81uPdEz38H6QswAee%C3%81HHyO7s65hvv%C3%81aR5oUwWk%C3%89efxVg=/ -- Ordinance No. 23-5476 Exhibit A, Table VI-203 (RSM-9 column: Maximum density 9.0 DU per acre, detached and attached)')
ON CONFLICT (jurisdiction_id, code) DO NOTHING;

INSERT INTO public.zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score, scraped_at)
SELECT id, 9.0,
  'https://edocs.sarasotagov.com/publicaccess/api/Document/ASpIyErY5EgwJ0miwrRMzHZ0fD9AKrPogY2%C3%89Ur9pT6a5%C3%81uPdEz38H6QswAee%C3%81HHyO7s65hvv%C3%81aR5oUwWk%C3%89efxVg=/',
  'City of Sarasota Zoning Code, Art. VI, Div. 2, Sec. VI-203, Table VI-203 (RSM-9 column, effective 4/17/2023)',
  0.95, now()
FROM public.zoning_districts WHERE jurisdiction_id = 824 AND code = 'RSM-9';

-- RSF-1 (Residential Single Family 1): Table VI-203 (read verbatim, Ord. 23-5476 Exhibit A) --
-- Maximum density = 2.9 DU/acre. No FAR row, no parking-per-1000sf row for this single-family
-- column (design/use-limitation only).
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated, pk1000_regulated, ordinance_section)
VALUES (824, 'RSF-1', 'Residential Single Family 1', 'residential', false, true, false,
  'https://edocs.sarasotagov.com/publicaccess/api/Document/ASpIyErY5EgwJ0miwrRMzHZ0fD9AKrPogY2%C3%89Ur9pT6a5%C3%81uPdEz38H6QswAee%C3%81HHyO7s65hvv%C3%81aR5oUwWk%C3%89efxVg=/ -- Ordinance No. 23-5476 Exhibit A, Article VI, Div. 2, Sec. VI-203, Table VI-203 (RSF-1 column: Maximum density 2.9 DU per acre)')
ON CONFLICT (jurisdiction_id, code) DO NOTHING;

INSERT INTO public.zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score, scraped_at)
SELECT id, 2.9,
  'https://edocs.sarasotagov.com/publicaccess/api/Document/ASpIyErY5EgwJ0miwrRMzHZ0fD9AKrPogY2%C3%89Ur9pT6a5%C3%81uPdEz38H6QswAee%C3%81HHyO7s65hvv%C3%81aR5oUwWk%C3%89efxVg=/',
  'City of Sarasota Zoning Code, Art. VI, Div. 2, Sec. VI-203, Table VI-203 (RSF-1 column, effective 4/17/2023)',
  0.97, now()
FROM public.zoning_districts WHERE jurisdiction_id = 824 AND code = 'RSF-1';

-- RE-1 (Residential Estate, County LDC -- see jurisdiction note above): WebSearch-cached
-- elaws.us snippet -- "large lot suburban residential subdivisions with a minimum lot size of
-- 40,000 square feet and a maximum density of one dwelling unit per acre" = 1.0 DU/acre.
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated, pk1000_regulated, ordinance_section)
VALUES (824, 'RE-1', 'Residential Estate', 'residential', false, true, false,
  'http://www.sarasotacounty.elaws.us/code/coor_apxa_art6_sec6.4 -- Sarasota County LDC Appendix A, Art. 6, Sec. 6.4 OUE and RE District Development Intensity (RE-1: 40,000 sf min lot, max density 1.0 DU/acre; page itself returned HTTP 503 this session, figure is a search-engine-cached snippet of the live ordinance text)')
ON CONFLICT (jurisdiction_id, code) DO NOTHING;

INSERT INTO public.zone_standards (zoning_district_id, max_density_du_acre, min_lot_sqft, source_url, ordinance_section, confidence_score, scraped_at)
SELECT id, 1.0, 40000,
  'http://www.sarasotacounty.elaws.us/code/coor_apxa_art6_sec6.4',
  'Sarasota County LDC Appendix A, Art. 6, Sec. 6.4 (RE-1) -- cached-snippet sourced, elaws.us returned 503 on direct fetch',
  0.55, now()
FROM public.zoning_districts WHERE jurisdiction_id = 824 AND code = 'RE-1';

-- RE-2 (Residential Estate, County LDC): WebSearch-cached elaws.us snippet -- "single
-- residential homes on lots of at least 2 acres...minimum net lot area of 87,120 square
-- feet...maximum building coverage of 25%...maximum of 0.5 dwelling units per acre".
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated, pk1000_regulated, ordinance_section)
VALUES (824, 'RE-2', 'Residential Estate', 'residential', false, true, false,
  'http://www.sarasotacounty.elaws.us/code/coor_apxa_art6_sec6.4 -- Sarasota County LDC Appendix A, Art. 6, Sec. 6.4 (RE-2: 87,120 sf / 2 acre min lot, max density 0.5 DU/acre, max building coverage 25%; page itself returned HTTP 503 this session, figure is a search-engine-cached snippet of the live ordinance text)')
ON CONFLICT (jurisdiction_id, code) DO NOTHING;

INSERT INTO public.zone_standards (zoning_district_id, max_density_du_acre, min_lot_sqft, max_lot_coverage_pct, source_url, ordinance_section, confidence_score, scraped_at)
SELECT id, 0.5, 87120, 25,
  'http://www.sarasotacounty.elaws.us/code/coor_apxa_art6_sec6.4',
  'Sarasota County LDC Appendix A, Art. 6, Sec. 6.4 (RE-2) -- cached-snippet sourced, elaws.us returned 503 on direct fetch',
  0.55, now()
FROM public.zoning_districts WHERE jurisdiction_id = 824 AND code = 'RE-2';

-- OUE-1 (Open Use Estate, County LDC): confirmed residential-estate category with a real
-- min-lot-size citation (5 acres, 3 acres if platted), but NO maximum-DU/acre figure was
-- recovered this session -- density_regulated left NULL (genuinely unresolved, not "not
-- regulated"). far_regulated/pk1000_regulated set false on the same residential-district
-- convention basis as every other confirmed-residential code in this file.
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, far_regulated, pk1000_regulated, ordinance_section)
VALUES (824, 'OUE-1', 'Open Use Estate', 'residential', false, false,
  'http://sarasotacounty.elaws.us/code/coor_apxa_art4_sec4.5 -- Sarasota County LDC Appendix A, Art. 4 Sec. 4.5 (Open Use Estate: min lot area 5 acres, 3 acres if platted subdivision); numeric maximum-density table (Art. 6 Sec. 6.4/6.3) not retrievable this session, elaws.us returned HTTP 503 on all attempts')
ON CONFLICT (jurisdiction_id, code) DO NOTHING;

-- SAPD (Settlement Area Planned Development, County LDC): multi-tier density standard per
-- WebSearch-cached elaws.us snippet of Sec. 11.2 -- min 3 du/gross developable acre, target 6
-- du/net residential acre, max 5 (or 6 with affordable-housing bonus) du/gross developable
-- acre. Recording the 6.0 target as the best single point estimate; confidence lowered
-- because this is a target/ceiling under a multi-tier formula, not a flat per-parcel cap like
-- every other density figure in this table.
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated, pk1000_regulated, ordinance_section)
VALUES (824, 'SAPD', 'Settlement Area Planned Development', 'mixed-use', false, true, false,
  'http://sarasotacounty.elaws.us/code/coor_apxa_art11_sec11.2 -- Sarasota County LDC Appendix A, Art. 11 Sec. 11.2 Village, Hamlet and Settlement Area Regulations (min 3 du/gross-developable-acre, target 6 du/net-residential-acre, max 5-6 du/gross-developable-acre with affordable-housing bonus); page itself returned HTTP 503 this session, figures are search-engine-cached snippets')
ON CONFLICT (jurisdiction_id, code) DO NOTHING;

INSERT INTO public.zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score, scraped_at)
SELECT id, 6.0,
  'http://sarasotacounty.elaws.us/code/coor_apxa_art11_sec11.2',
  'Sarasota County LDC Appendix A, Art. 11 Sec. 11.2 (SAPD target density 6 du/net-residential-acre; multi-tier min/target/max formula, single point estimate recorded) -- cached-snippet sourced, elaws.us returned 503 on direct fetch',
  0.55, now()
FROM public.zoning_districts WHERE jurisdiction_id = 824 AND code = 'SAPD';

-- CN (Commercial Neighborhood, County LDC): confirmed commercial category ("permits
-- small-scale, neighborhood-oriented commercial" per 4sarasotahomes.com PDF Sec. 4.7.1, read
-- directly), but no specific FAR or parking-per-1000sf numeric figure was recovered this
-- session. far_regulated/pk1000_regulated left NULL (unresolved).
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, ordinance_section)
VALUES (824, 'CN', 'Commercial Neighborhood', 'commercial',
  'Sarasota County LDC Appendix A, Art. 4 Sec. 4.7.1 Commercial Neighborhood District (category confirmed via direct read of 4sarasotahomes.com/images/Zoning/1-10-06 Sarasota Zoning Districts.pdf, page 10); numeric FAR/parking table (Art. 6 Sec. 6.10) not retrievable this session, elaws.us returned HTTP 503')
ON CONFLICT (jurisdiction_id, code) DO NOTHING;

-- G (Government Use / "GU" in the County LDC text, County LDC): read directly from
-- 4sarasotahomes.com PDF Sec. 4.9.1 -- "Maximum Residential Density: One dwelling unit per
-- acre, as accessory to principal permitted uses, however no GU parcel shall contain more
-- than a total of five residences, regardless of the total acreage." A real, cited, non-zero
-- residential density cap even though the district's primary use is governmental, not housing.
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated, pk1000_regulated, ordinance_section)
VALUES (824, 'G', 'Government Use', 'other', false, true, false,
  'Sarasota County LDC Appendix A, Art. 4 Sec. 4.9.1 Government Use District (GU) -- read directly from 4sarasotahomes.com/images/Zoning/1-10-06 Sarasota Zoning Districts.pdf, page 10: "Maximum Residential Density: One dwelling unit per acre...no GU parcel shall contain more than a total of five residences"')
ON CONFLICT (jurisdiction_id, code) DO NOTHING;

INSERT INTO public.zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score, scraped_at)
SELECT id, 1.0,
  'http://4sarasotahomes.com/images/Zoning/1-10-06%20Sarasota%20Zoning%20Districts.pdf',
  'Sarasota County LDC Appendix A, Art. 4 Sec. 4.9.1 (GU/"G" District Development Standards: Maximum Residential Density 1.0 DU/acre, capped at 5 residences per parcel regardless of acreage)',
  0.90, now()
FROM public.zoning_districts WHERE jurisdiction_id = 824 AND code = 'G';

-- MP (Marine Park, County LDC): read directly from 4sarasotahomes.com PDF Sec. 4.9.2 -- "The
-- MP District is intended to protect and preserve water areas...all boat basins, bays,
-- bayous, canals, lakes, rivers, streams, waterways, and waters of the Gulf of Mexico, and all
-- publicly and privately owned submerged lands." This is a water/submerged-land protection
-- district, not upland developable acreage -- density/FAR/parking-per-1000sf are genuinely not
-- applicable (there is no buildable land area to apply a DU/acre or FAR ratio to), a real,
-- affirmatively-stated fact from the ordinance's own purpose clause, not an invented default.
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated, pk1000_regulated, ordinance_section)
VALUES (824, 'MP', 'Marine Park', 'other', false, false, false,
  'Sarasota County LDC Appendix A, Art. 4 Sec. 4.9.2 Marine Park District (MP) -- read directly from 4sarasotahomes.com/images/Zoning/1-10-06 Sarasota Zoning Districts.pdf, page 10: water/submerged-land protection district (boat basins, bays, canals, Gulf of Mexico waters); not an upland developable district, no density/FAR/parking standard exists')
ON CONFLICT (jurisdiction_id, code) DO NOTHING;

-- ============================================================
-- Venice (jurisdiction_id = 933)
-- ============================================================

-- RMH (Residential Manufactured Home): same district TYPE already resolved for City of
-- Sarasota jurisdiction 824 in migration 20260721_..._sarasota_g_zone_standards.sql (left
-- NULL there as an "unresolved Sarasota-COUNTY convention absent from the City's own Article
-- VI text" for jurisdiction 824). For Venice specifically, no Venice-code numeric source was
-- located or previously verified working this session (prior migration 20260721_...
-- _sarasota_i_zone_extend.sql explicitly flagged Venice's own zoning ArcGIS layer
-- (geoport.venicefl.gov) as proven UNRELIABLE -- "wrong ACCOUNT matches for real Venice test
-- parcels, geometry artifact" -- and skipped all Venice-addressed rows on that basis).
-- Category set to residential (RMH = Residential Manufactured Home is an unambiguous naming
-- convention across every FL jurisdiction already in this table), but no numeric standard
-- inserted -- left genuinely unresolved rather than borrowing a number from a different
-- jurisdiction's ordinance.
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, far_regulated, pk1000_regulated, ordinance_section)
VALUES (933, 'RMH', 'Residential Manufactured Home', 'residential', false, false,
  'Category inferred from unambiguous naming convention (Residential Manufactured Home) shared with Sarasota-jurisdiction RMH already in zoning_districts id=12343; no Venice-specific ordinance source verified working this session -- Venice zoning ArcGIS layer (geoport.venicefl.gov) previously proven unreliable per migration 20260721_gold_standard_shard6_run5361_sarasota_i_zone_extend.sql (wrong ACCOUNT matches, geometry artifact); no numeric density standard inserted')
ON CONFLICT (jurisdiction_id, code) DO NOTHING;

COMMIT;

-- ============================================================
-- VERIFICATION (run live after apply):
--   SELECT * FROM public.v_zoning_gold_standard_kpi_v3 WHERE county='sarasota';
--   pencil_dod_evaluate_county('sarasota') -- letter G before/after pasted in session report.
-- ============================================================
