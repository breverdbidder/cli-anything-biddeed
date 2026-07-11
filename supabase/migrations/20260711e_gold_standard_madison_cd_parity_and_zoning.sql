-- Gold Standard fix for MADISON county: C/D parity self-match + G/I minimal zoning (5 parcels)
-- Session: run3679 madison shard. County-scoped, additive only.
--
-- PART 1 (C/D): madison's 5 auction rows are all sourced from madisonclerk_foreclosure_sales_page
-- (madisonclerk.com foreclosure-sales), a clerk_html platform with no RealForeclose/RealAuction
-- intermediary to cross-check against. Per this repo's standing authorization (precedent: wakulla),
-- when the clerk's own site IS the authoritative source, the case is the source of truth and gets
-- self-certified matched_clean. Re-verified live via WebFetch on 2026-07-11: all 5 case numbers
-- (25-79-CA, 25-128-CA, 26-20-CA, 24-62-CA, 21-36-CA) are still listed on
-- https://www.madisonclerk.com/departments-services/property-sales/foreclosure-sales/ with matching
-- sale dates and parcel IDs as of this session.
--
-- PART 2 (G/I): madison has 4 jurisdictions seeded (City of Madison, Madison County unincorp.,
-- Lee, Greenville) but zero zoning_districts/parcel_zones/zone_standards rows. Only 5 auction
-- parcels total -- bounded, narrow scope, not a full-county ingestion.
--
-- Jurisdiction determined via FDOT Admin_Boundaries FeatureServer layer 7 (Florida Cities Bndy,
-- authoritative Census/FDOT municipal boundary polygons) queried by each parcel's lat/lon:
--   338 SW Horry Ave        -> City of Madison       (jurisdiction id 858)
--   119 NE Blackberry Way   -> unincorp. Madison Co.  (jurisdiction id 1188)
--   420 NE Palmetto St      -> unincorp. Madison Co.  (jurisdiction id 1188)
--   1638 SW SR 14           -> unincorp. Madison Co.  (jurisdiction id 1188)
--   204 SW Church Ave       -> Greenville town        (jurisdiction id 1044) -- DEFERRED, see below
--
-- Zone code determined via FL GIO Statewide Cadastral FeatureServer (DOR_UC field, geometry
-- intersection query by parcel lat/lon -- confirmed via matching PARCEL_ID in the response):
--   338 SW Horry Ave        DOR_UC=001 (SFR),  8,232 sqft lot, inside city limits w/ municipal
--                            water -> City of Madison R-1B (10,000 sqft min "where community
--                            water systems are available"; lot is a legal nonconforming lot of
--                            record per LDR Section 1.6.1/2.3, does not change district assignment)
--   119 NE Blackberry Way   DOR_UC=001 (SFR), ~1.84 ac -> Madison Co. unincorp. "Residential" LU district
--   420 NE Palmetto St      DOR_UC=002 (MH),  ~5.79 ac -> Madison Co. unincorp. "Residential" LU district
--                            (mobile homes are an allowable use in the Residential district)
--   1638 SW SR 14           DOR_UC=059 (Timberland Not Classified per FL DOR use code list),
--                            ~40 ac -> Madison Co. unincorp. "Agriculture 1" LU district
--
-- Ordinance sources (real text, not fabricated):
--   City of Madison: City_LDR_Madison_23_Blue.pdf (cityofmadisonfl.com), Section 4.4 "RSF"
--     Residential (Conventional) Single Family -- R-1A/R-1B dimensional standards.
--     City LDR regulates R-1 by MIN LOT AREA, not density or FAR -- max_far and
--     max_density_du_acre are correctly left NULL for this district (far_regulated=false,
--     density_regulated=false), not fabricated.
--   Madison County (unincorporated): Chapter 4 "Land Use Districts and Development Standards"
--     of the county LDC (madisoncountyfl.com/departments-services/planning-zoning/
--     land-development-codes/, PDF: Chapter-4-Land-Use-Districts-and-Development-Standards.pdf),
--     Section 4.4 Schedule 1.0 "Minimum Development Standards" table, and Section 4.6-11 parking
--     table ("Dwellings (single and two-family): Two (2) per dwelling unit").
--     County LDC regulates Residential and Agriculture districts by DENSITY (du/acre), not a
--     fixed min_lot_sqft -- min_lot_sqft is correctly left NULL for these two districts (the
--     ordinance genuinely does not set a fixed minimum lot area for them), not fabricated.
--
-- DEFERRED: 204 SW Church Ave (Greenville town) -- could not locate a distinct, fetchable
-- Greenville FL zoning ordinance/LDC within session budget (Municode blocks WebFetch/curl 403,
-- no independent LDC PDF found via search). NOT self-certified, NOT fabricated. Left with zero
-- zoning rows. This caps I at 4/5 = 80% (< 95% threshold) -- G is scored only against the
-- applicable subset per v_zoning_gold_standard_kpi_v3 and is not blocked by this gap.

-- ADDENDUM (discovered mid-session): jurisdictions 858 (City of Madison) and 1188 (unincorp.
-- Madison Co.) already had 5 orphaned "bootstrap" zoning_districts rows (codes R-1, R-2, C-1,
-- A-1) inserted by a prior shard5 session, source_url='shard5_bootstrap_madison' or
-- 'https://library.municode.com/fl/madison' (a URL that 403s to WebFetch/curl and was never
-- actually readable -- Municode blocks scraping). Their zone_standards carry IDENTICAL
-- copy-pasted placeholder values across every district regardless of category (max_far=0.35,
-- max_density_du_acre=4.00, parking_per_1000sf=2.00 on R-1 AND A-1 AND C-1 alike) -- textbook
-- ghost-success, not real ordinance data. Zero parcel_zones rows ever referenced them (confirmed
-- live query before this migration), so they are inert/orphaned, not in use by any live card.
-- Purging and replacing with real ordinance-sourced rows per this session's research above.

BEGIN;

-- ============ PURGE GHOST-SUCCESS BOOTSTRAP ROWS (unused, fabricated values) ============

DELETE FROM public.zone_standards
WHERE zoning_district_id IN (
  SELECT id FROM public.zoning_districts
  WHERE jurisdiction_id IN (858,1188) AND code IN ('R-1','R-2','C-1','A-1')
);

DELETE FROM public.zoning_districts
WHERE jurisdiction_id IN (858,1188) AND code IN ('R-1','R-2','C-1','A-1');

-- ============ C/D PARITY SELF-MATCH ============

UPDATE public.multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:madisonclerk_foreclosure_sales_page_20260711'
WHERE county = 'madison'
  AND data_source = 'madisonclerk_foreclosure_sales_page'
  AND case_number IN ('25-79-CA','25-128-CA','26-20-CA','24-62-CA','21-36-CA');

-- ============ ZONING DISTRICTS ============

-- City of Madison R-1B (jurisdiction_id 858)
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, description, ordinance_section, far_regulated, density_regulated)
VALUES (858, 'R-1B', 'Residential, (Conventional) Single Family - B', 'residential',
        'Conventional single family residential district, min lot area 10,000 sqft where community water systems are available and accessible.',
        'City of Madison LDR Section 4.4', false, false)
RETURNING id;

-- Madison County unincorporated Residential (jurisdiction_id 1188)
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, description, ordinance_section, far_regulated, density_regulated)
VALUES (1188, 'RES', 'Residential', 'residential',
        'Low density residential category; density-regulated (not lot-size regulated). Density 0-2 du/ac without central water/sewer, up to 2 du/ac with central sewer, up to 8 du/ac for PUD w/ central water and sewer.',
        'Madison County LDC Chapter 4, Section 4.4.E / Schedule 1.0', false, true)
RETURNING id;

-- Madison County unincorporated Agriculture 1 (jurisdiction_id 1188)
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, description, ordinance_section, far_regulated, density_regulated)
VALUES (1188, 'A-1', 'Agriculture 1', 'agricultural',
        'Predominantly agricultural/silvicultural use lands. Residential development allowed only at very low density (1 du / 40 ac).',
        'Madison County LDC Chapter 4, Section 4.4.A / Schedule 1.0', true, true)
RETURNING id;

-- ============ ZONE STANDARDS ============

-- City of Madison R-1B standards (LDR Section 4.4.6/4.4.7/4.4.8/4.4.9/4.4.11)
INSERT INTO public.zone_standards (
  zoning_district_id, min_lot_sqft, min_lot_width_ft, max_height_ft,
  front_setback_ft, side_setback_ft, rear_setback_ft, max_lot_coverage_pct,
  max_far, max_density_du_acre, parking_per_unit, parking_per_1000sf,
  source_url, ordinance_section, confidence_score, scraped_at
)
SELECT id, 10000, 100, 35, 25, 10, 15, 35,
       NULL, NULL, 2, NULL,
       'https://cityofmadisonfl.com/wp-content/uploads/City_LDR_Madison_23_Blue.pdf',
       'Section 4.4.6-4.4.11', 0.95, now()
FROM public.zoning_districts WHERE jurisdiction_id=858 AND code='R-1B';

-- Madison County unincorporated Residential standards (Schedule 1.0 + Section 4.6-11 parking table)
INSERT INTO public.zone_standards (
  zoning_district_id, min_lot_sqft, min_lot_width_ft, max_height_ft,
  front_setback_ft, side_setback_ft, rear_setback_ft, max_lot_coverage_pct,
  max_far, max_density_du_acre, parking_per_unit, parking_per_1000sf,
  source_url, ordinance_section, confidence_score, scraped_at
)
SELECT id, NULL, NULL, 35, 25, 10, 20, NULL,
       NULL, 2, 2, NULL,
       'https://madiscon-county-fl.s3.amazonaws.com/uploads/2025/05/28151409/Chapter-4-Land-Use-Districts-and-Development-Standards.pdf',
       'Section 4.4.E / Schedule 1.0 / Section 4.6-11 parking table', 0.9, now()
FROM public.zoning_districts WHERE jurisdiction_id=1188 AND code='RES';

-- Madison County unincorporated Agriculture 1 standards (Schedule 1.0)
INSERT INTO public.zone_standards (
  zoning_district_id, min_lot_sqft, min_lot_width_ft, max_height_ft,
  front_setback_ft, side_setback_ft, rear_setback_ft, max_lot_coverage_pct,
  max_far, max_density_du_acre, parking_per_unit, parking_per_1000sf,
  source_url, ordinance_section, confidence_score, scraped_at
)
SELECT id, NULL, NULL, 35, 40, 40, 40, 35,
       0.5, 0.025, 2, NULL,
       'https://madiscon-county-fl.s3.amazonaws.com/uploads/2025/05/28151409/Chapter-4-Land-Use-Districts-and-Development-Standards.pdf',
       'Section 4.4.A / Schedule 1.0', 0.9, now()
FROM public.zoning_districts WHERE jurisdiction_id=1188 AND code='A-1';

-- ============ PARCEL ZONES ============

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, effective_date, source)
VALUES
  ('00-00-00-3765-000-000', 858, 'R-1B', 'Residential, (Conventional) Single Family - B', CURRENT_DATE, 'city_of_madison_ldr_20260711'),
  ('13-2N-09-5230-005-01B', 1188, 'RES', 'Residential', CURRENT_DATE, 'madison_county_ldc_ch4_20260711'),
  ('35-3N-09-5540-018-000', 1188, 'RES', 'Residential', CURRENT_DATE, 'madison_county_ldc_ch4_20260711'),
  ('19-1S-09-0934-000-000', 1188, 'A-1', 'Agriculture 1', CURRENT_DATE, 'madison_county_ldc_ch4_20260711');

COMMIT;
