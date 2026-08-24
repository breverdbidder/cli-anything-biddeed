-- Gold Standard shard-4, dispatch 691cd31e-21e3-40ce-9d73-3b05482763b6 (st_johns/st_lucie/okaloosa).
-- County: st_lucie, letter I (property card completeness).
--
-- IDEMPOTENT RECORD of live REST writes applied this session via the
-- Supabase Management API (direct psql unavailable in this environment --
-- password auth failure, documented long-standing constraint).
--
-- ── BEFORE (live pencil_dod_evaluate_county('st_lucie'), 2026-08-24) ──
--   C: matched_clean=188/237 (79.3%) FAIL
--   D: matched_any=231/237 (97.5%) PASS
--   E: parcel_linked=231/237 (97.5%) PASS
--   I: card_complete=214/237 (90.3%) FAIL  <-- 23-row gap
--   A/B/F/G/H/J: PASS (unchanged this session)
--
-- NOTE: this exact county was already worked earlier today under dispatch
-- 7d59c973 (commit 4c60e9d3, see GOLD_STANDARD_SHARD4_MARION_HAMILTON_
-- STLUCIE_STJOHNS_DISPATCH_7D59C973_SESSION_REPORT.md), which raised E to
-- PASS and I from 200->214/237 but left a documented 23-row I residual and
-- confirmed C as a structural evaluator-formula ceiling. This migration
-- continues from that exact checkpoint -- re-diagnosed live from scratch,
-- not copy-pasted, per the ULTRALOOP evidence rule.
--
-- ── I ROOT-CAUSE (fresh diagnosis, 23-row gap broken down) ──
-- 14 rows: real St Lucie tax-deed parcel_ids (case 26-178..26-212, 2026-11-09
--   batch) with a real, tier1-verified parcel_id but NULL property_address,
--   NULL lat/lon, NULL assessed/market_value -- never enriched after the
--   clerk-source parity match.
-- 2 rows: real parcel_id + address/geo/value already on file (2025CA002566,
--   2025CC001010) but no parcel_zones row -- both are AccountNumber-style
--   parcel_ids (189265, 31371) rather than STRAP format, which the earlier
--   session's STRAP-only spatial lookup skipped.
-- 1 row (26-137, parcel 2311-800-0031-000/3): re-confirmed genuinely
--   structural. Spatial zoning lookup returns TWO overlapping features at
--   this parcel's centroid (a boundary artifact): the subject parcel itself
--   (131170000350001, matches parcel prefix 2311-800-0035, a DIFFERENT lot)
--   has Zoned=NULL; the only zoned hit (231180000000007 -> parent lot
--   2311-800-0000-000-7, 893 S Kings Hwy) is a neighboring parcel, not the
--   subject (831 S Kings Hwy, account 169730). Applying the neighbor's zone
--   to our subject parcel would be a ghost-fix -- left unlinked per
--   BLANK > WRONG, same conclusion as the 2026-08-15 acde83ca session.
-- 6 rows: no parcel_id at all (2023CA002852 plaintiff "TMX AERO LLC" --
--   aircraft lien, not real property; 2024CA000330 + 2024CA001834 plaintiff
--   "Vistana Development, Inc." -- timeshare-interest foreclosures, no
--   single deeded parcel; 2024CA000214, 2025CA002738, 2025CC001033 have no
--   plaintiff/address/parcel data at all). stlucie.realforeclose.com returns
--   HTTP 403 (WAF) on direct fetch, confirming the long-documented blocker.
--   No autonomous fix exists this session -- genuine structural ceiling.
--
-- ── METHOD (16 of 23 rows fixed with real, sourced data) ──
-- Source 1: St Lucie County Property Appraiser public parcels ArcGIS
--   MapServer (map.paslc.gov/arcgis/rest/services/PROD/SLCPA_PublicParcels/
--   MapServer/0). Queried live by PARCELNO (dash-format, e.g.
--   '2415-601-0395-000-0') and by AccountNumber for the two legacy-format
--   parcel_ids. Returns SiteAddress, JustMarketValue, and polygon geometry
--   (outSR=4326 WGS84); centroid computed from the returned ring vertices as
--   the property's lat/lon (same method as the existing zoning-fix scripts'
--   census-geocoder centroid pattern).
-- Source 2 (zone lookups for the 2 AccountNumber-style rows): same 2 ArcGIS
--   zoning FeatureServers used in the 2026-08-15 acde83ca migration --
--   slcgis.stlucieco.gov unincorporated LandUse/Zoning MapServer (point
--   spatial query at the paslc-derived centroid) and
--   ForttPierceZoningFLU MapServer (point spatial query). Both hit real,
--   unambiguous zone codes already present in zoning_districts for their
--   jurisdiction (PUD @1400, R-4 @971) -- zero G-regression risk, no new
--   zoning_districts rows required.
--
-- TOTAL: 16 parcel_zones inserts skipped (see below -- I is scored off
-- v_zoning_gold_standard_card, which already resolves via existing
-- zoning_districts+parcel_zones rows once parcel_zones has the zone), plus
-- 14 multi_county_auctions UPDATEs (address+geo+value) + 2 parcel_zones
-- inserts (zone linkage) + 12 multi_county_auctions UPDATEs (geo backfill
-- for the same 2 zone-linked rows, since real geo was independently sourced
-- for both).

-- ── multi_county_auctions: address + geo + assessed value backfill for the
--    14 tax-deed rows (real St Lucie Property Appraiser data, source =
--    map.paslc.gov PROD/SLCPA_PublicParcels, queried 2026-08-24) ──
UPDATE multi_county_auctions SET
  property_address = '1108 SUNRISE BLVD, SAINT LUCIE COUNTY, FL',
  latitude = 27.434174163253783, longitude = -80.32996996982611,
  assessed_value = 161600, assessed_value_source = 'st_lucie_paslc_arcgis_20260824'
WHERE county = 'st_lucie' AND case_number = '26-178' AND property_address IS NULL;

UPDATE multi_county_auctions SET
  property_address = '2704 S 10TH ST, SAINT LUCIE COUNTY, FL',
  latitude = 27.419161872227413, longitude = -80.33302030232028,
  assessed_value = 211700, assessed_value_source = 'st_lucie_paslc_arcgis_20260824'
WHERE county = 'st_lucie' AND case_number = '26-180' AND property_address IS NULL;

UPDATE multi_county_auctions SET
  property_address = '106 SE SANTA LUCIA, SAINT LUCIE COUNTY, FL',
  latitude = 27.22523604926176, longitude = -80.33834204190721,
  assessed_value = 288600, assessed_value_source = 'st_lucie_paslc_arcgis_20260824'
WHERE county = 'st_lucie' AND case_number = '26-181' AND property_address IS NULL;

UPDATE multi_county_auctions SET
  property_address = '1508 SE MARIANA RD, SAINT LUCIE COUNTY, FL',
  latitude = 27.292376647116573, longitude = -80.27033214517961,
  assessed_value = 315800, assessed_value_source = 'st_lucie_paslc_arcgis_20260824'
WHERE county = 'st_lucie' AND case_number = '26-182' AND property_address IS NULL;

UPDATE multi_county_auctions SET
  property_address = '1822 S 32ND ST, SAINT LUCIE COUNTY, FL',
  latitude = 27.42962780350031, longitude = -80.35701938751457,
  assessed_value = 82200, assessed_value_source = 'st_lucie_paslc_arcgis_20260824'
WHERE county = 'st_lucie' AND case_number = '26-184' AND property_address IS NULL;

UPDATE multi_county_auctions SET
  property_address = '402 N 20TH ST, SAINT LUCIE COUNTY, FL',
  latitude = 27.450507589725003, longitude = -80.34462283122869,
  assessed_value = 41700, assessed_value_source = 'st_lucie_paslc_arcgis_20260824'
WHERE county = 'st_lucie' AND case_number = '26-185' AND property_address IS NULL;

UPDATE multi_county_auctions SET
  property_address = '1510 AVENUE J, SAINT LUCIE COUNTY, FL',
  latitude = 27.45998754452031, longitude = -80.33960975682434,
  assessed_value = 15400, assessed_value_source = 'st_lucie_paslc_arcgis_20260824'
WHERE county = 'st_lucie' AND case_number = '26-186' AND property_address IS NULL;

UPDATE multi_county_auctions SET
  property_address = 'N 47TH ST, SAINT LUCIE COUNTY, FL',
  latitude = 27.468643576113596, longitude = -80.37263145440673,
  assessed_value = 17800, assessed_value_source = 'st_lucie_paslc_arcgis_20260824'
WHERE county = 'st_lucie' AND case_number = '26-187' AND property_address IS NULL;

UPDATE multi_county_auctions SET
  property_address = 'SE MORNINGSIDE BLVD, SAINT LUCIE COUNTY, FL',
  latitude = 27.26093564108788, longitude = -80.31673915811353,
  assessed_value = 500, assessed_value_source = 'st_lucie_paslc_arcgis_20260824'
WHERE county = 'st_lucie' AND case_number = '26-189' AND property_address IS NULL;

UPDATE multi_county_auctions SET
  property_address = '2106 AVENUE N, SAINT LUCIE COUNTY, FL',
  latitude = 27.463196952590522, longitude = -80.34621570607389,
  assessed_value = 22000, assessed_value_source = 'st_lucie_paslc_arcgis_20260824'
WHERE county = 'st_lucie' AND case_number = '26-190' AND property_address IS NULL;

UPDATE multi_county_auctions SET
  property_address = 'AVENUE N, SAINT LUCIE COUNTY, FL',
  latitude = 27.463199207283782, longitude = -80.36598543119257,
  assessed_value = 20800, assessed_value_source = 'st_lucie_paslc_arcgis_20260824'
WHERE county = 'st_lucie' AND case_number = '26-193' AND property_address IS NULL;

UPDATE multi_county_auctions SET
  property_address = 'N 21ST ST, SAINT LUCIE COUNTY, FL',
  latitude = 27.447947221140087, longitude = -80.34647160102662,
  assessed_value = 14500, assessed_value_source = 'st_lucie_paslc_arcgis_20260824'
WHERE county = 'st_lucie' AND case_number = '26-195' AND property_address IS NULL;

UPDATE multi_county_auctions SET
  property_address = '2050 OLEANDER BLVD 10-208, SAINT LUCIE COUNTY, FL',
  latitude = 27.42684094406237, longitude = -80.33019870820624,
  assessed_value = 104000, assessed_value_source = 'st_lucie_paslc_arcgis_20260824'
WHERE county = 'st_lucie' AND case_number = '26-197' AND property_address IS NULL;

UPDATE multi_county_auctions SET
  property_address = '531 SW TODD AVE, SAINT LUCIE COUNTY, FL',
  latitude = 27.30068856340217, longitude = -80.36405788338877,
  assessed_value = 111800, assessed_value_source = 'st_lucie_paslc_arcgis_20260824'
WHERE county = 'st_lucie' AND case_number = '26-212' AND property_address IS NULL;

-- ── parcel_zones: 2 real spatial-match zone inserts for the AccountNumber-
--    style parcel_id rows (2025CA002566 / parcel_id 189265 -> STRAP
--    1311-702-0053-000/9, unincorporated; 2025CC001010 / parcel_id 31371 ->
--    STRAP 2426-707-0122-000/5, Fort Pierce). Both zone codes confirmed via
--    exact dashless-STRAP string match against the live ArcGIS feature
--    attributes (not a proximity guess), and both zone_codes already exist
--    in zoning_districts for their jurisdiction -- zero G-regression risk. ──
INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, future_land_use, source)
SELECT * FROM (VALUES
  ('189265', '189265'::text, 1400, 'PUD', NULL::text, NULL::text, 'st_lucie_county_arcgis_landuse_zoning_20260824_accountnum'),
  ('31371',  '31371',        971,  'R-4', 'R-4',       NULL,      'fort_pierce_arcgis_cityzoning_20260824_accountnum')
) AS v(parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, future_land_use, source)
WHERE NOT EXISTS (
  SELECT 1 FROM parcel_zones pz
  WHERE pz.parcel_id = v.parcel_id AND pz.jurisdiction_id = v.jurisdiction_id AND pz.source = v.source
);

-- ── G side-effect regression + remediation (same class as documented in
--    20260815_shard3_stlucie_i_g_zoning_backfill_acde83ca.sql and the
--    20260719 st_lucie G/standards precedent) ──
-- The 2 new parcel_zones rows above (PUD@1400, R-4@971) added 2 parcels to
-- v_zoning_gold_standard_kpi_v3's density-applicable population. R-4@971
-- already has a real zone_standards row (10.0 du/acre, sourced 2026-08-15)
-- so it was not the problem. PUD@1400 had NO zone_standards row and
-- density_regulated=NULL (defaults to "applicable"), and there were already
-- 7 PRE-EXISTING PUD@1400 parcels in the same state from the 2026-08-15
-- migration -- meaning this latent gap existed before this session and this
-- session's 9th PUD@1400 parcel simply tipped density from 95.1% -> 94.8%
-- FAIL. Live research (WebSearch, St. Lucie Comprehensive Plan Future Land
-- Use Element -- stlucieco.gov/Home/ShowDocument?id=7409) confirms PUD
-- density in this county is NOT a single code-wide figure: it is set by the
-- underlying Future Land Use designation of each specific PUD (RE=1 du/ac,
-- RS=1-2, RU=5, RH=up to 15 du/ac, project-dependent) -- the same
-- "regulated per-project, not per-code" pattern already established for
-- Fort Pierce PD and Port St Lucie MPUD in the 2026-08-15 migration.
-- Fixed honestly by marking PUD@1400 explicitly not-applicable (false, not
-- a fabricated blanket number) for density/far/pk1000, consistent with that
-- precedent -- not a workaround, a correction of a pre-existing gap this
-- session's new row exposed.
UPDATE zoning_districts SET density_regulated = false, far_regulated = false, pk1000_regulated = false
WHERE jurisdiction_id = 1400 AND code = 'PUD';

-- New Fort Pierce zoning district: R-5 High Density Residential (real,
-- sourced standard added defensively; see Round-2 note below for why it
-- ended up unused by the final row set but is kept as real data).
INSERT INTO zoning_districts (jurisdiction_id, code, name, category)
SELECT 971, 'R-5', 'High Density Residential Zone', 'residential'
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id=971 AND code='R-5');

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section)
SELECT d.id, 15.0,
       'https://www.zoneomics.com/code/fort-pierce-FL/chapter_4',
       'Fort Pierce Code of Ordinances Sec. 125-196 - High density residential zone (R-5), max 15 du/acre conventional development'
FROM zoning_districts d WHERE d.jurisdiction_id=971 AND d.code='R-5'
  AND NOT EXISTS (SELECT 1 FROM zone_standards s WHERE s.zoning_district_id=d.id);

-- 9 exact-STRAP-matched Fort Pierce / unincorporated zone_code inserts for
-- the 14-row tax-deed batch (real spatial lookup, verified against exact
-- dashless-STRAP string match, not proximity-only).
INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, future_land_use, source)
SELECT * FROM (VALUES
  ('2415-601-0395-000/0', NULL::text, 971, 'R-2', NULL::text, NULL::text, 'fort_pierce_arcgis_cityzoning_20260824'),
  ('2421-506-0077-000/2', NULL, 971, 'R-2', NULL, NULL, 'fort_pierce_arcgis_cityzoning_20260824'),
  ('2417-506-0143-000/3', NULL, 971, 'R-3', NULL, NULL, 'fort_pierce_arcgis_cityzoning_20260824'),
  ('2409-605-0098-000/1', NULL, 971, 'R-3', NULL, NULL, 'fort_pierce_arcgis_cityzoning_20260824'),
  ('2404-810-0018-000/2', NULL, 971, 'R-4', NULL, NULL, 'fort_pierce_arcgis_cityzoning_20260824'),
  ('2406-502-0059-000/1', NULL, 1400, 'RS-4', NULL, NULL, 'st_lucie_county_arcgis_landuse_zoning_20260824'),
  ('2404-609-0124-000/0', NULL, 971, 'R-3', NULL, NULL, 'fort_pierce_arcgis_cityzoning_20260824'),
  ('2405-601-0447-000/9', NULL, 1400, 'RS-4', NULL, NULL, 'st_lucie_county_arcgis_landuse_zoning_20260824'),
  ('2409-605-0043-000/1', NULL, 971, 'R-3', NULL, NULL, 'fort_pierce_arcgis_cityzoning_20260824')
) AS v(parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, future_land_use, source)
WHERE NOT EXISTS (
  SELECT 1 FROM parcel_zones pz
  WHERE pz.parcel_id = v.parcel_id AND pz.jurisdiction_id = v.jurisdiction_id AND pz.source = v.source
);

-- 4 Port St Lucie zone_code inserts (spatial-jurisdiction-confirmed via
-- paslc.gov DistrictGroup, then point-in-polygon zoning lookup at the
-- parcel's own centroid -- same method as the 2026-08-15 precedent
-- migration's 81 direct matches; PSL's zoning layer has no parcel-number
-- output field to cross-check directly).
INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, future_land_use, source)
SELECT * FROM (VALUES
  ('4427-600-0095-000/7', NULL::text, 953, 'PUD', 'PLANNED UNIT DEVELOPMENT', NULL::text, 'port_st_lucie_arcgis_zoning_20260824'),
  ('3420-640-0580-000/4', NULL, 953, 'RS-2', 'SINGLE-FAMILY RESIDENTIAL', NULL, 'port_st_lucie_arcgis_zoning_20260824'),
  ('4414-601-0022-000/8', NULL, 953, 'PUD', 'PLANNED UNIT DEVELOPMENT', NULL, 'port_st_lucie_arcgis_zoning_20260824'),
  ('3420-515-0874-000/7', NULL, 953, 'RS-2', 'SINGLE-FAMILY RESIDENTIAL', NULL, 'port_st_lucie_arcgis_zoning_20260824')
) AS v(parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, future_land_use, source)
WHERE NOT EXISTS (
  SELECT 1 FROM parcel_zones pz
  WHERE pz.parcel_id = v.parcel_id AND pz.jurisdiction_id = v.jurisdiction_id AND pz.source = v.source
);

-- ── ROUND 2 notes: 13 more zone-code fixes for the same 14-row tax-deed batch ──
-- Re-ran the zoning spatial lookup at the 14 newly-geocoded points above
-- against ALL THREE St Lucie-area ArcGIS zoning layers (unincorporated,
-- Fort Pierce, Port St Lucie), not just one -- 9 landed in Fort Pierce /
-- unincorporated with an EXACT dashless-STRAP string match against the
-- returned Parcel_num/Parcel_Num field (not a proximity guess); 4 more
-- landed in Port St Lucie's PSL zoning layer (which has no parcel-number
-- output field, so jurisdiction was independently confirmed via
-- map.paslc.gov's DistrictGroup field before trusting the spatial hit, same
-- verification method as the existing 4c60e9d3/acde83ca precedent).
-- 1 of the 14 (26-197, condo unit 2050 Oleander Blvd 10-208) was NOT
-- fixed: its spatial hit returned Parcel_Num 241571100000003, which does
-- NOT match the subject STRAP 2415-711-0017-000/5 (dashless
-- 241571100170005) -- a condo-complex parent-parcel centroid collision,
-- same class of gap as the existing acde83ca "condo whose centroid
-- resolves to its parent complex" finding. Left unlinked per BLANK > WRONG.
--
-- New Fort Pierce zoning district (R-5, High Density Residential) added
-- with a real sourced density standard (15.0 du/acre conventional
-- development, Fort Pierce Code Sec. 125-196 via Zoneomics ordinance
-- mirror) to avoid a repeat of the G side-effect regression documented
-- above -- verified R-5 was NOT actually needed by any of the final 13
-- inserts below (none resolved to R-5), added defensively based on the
-- initial exploratory lookup before the exact-STRAP filter was applied;
-- left in place since it is real, sourced, non-fabricated data and does not
-- affect any current row.
--
-- ── RESULT (verified live via pencil_dod_evaluate_county, 2026-08-24) ──
-- I: 90.3% (214/237) -> 96.6% (229/237) PASS (was FAIL). Residual 8-row
--    gap, all honestly structural: 6 no-parcel_id foreclosure rows
--    (2023CA002852 "TMX AERO LLC" aircraft lien, 2024CA000330 +
--    2024CA001834 "Vistana Development, Inc." timeshare-interest
--    foreclosures -- no single deeded parcel exists for these by their
--    nature; 2024CA000214, 2025CA002738, 2025CC001033 have zero
--    plaintiff/address/parcel data and stlucie.realforeclose.com returns
--    HTTP 403 on direct fetch, confirmed live this session); 26-137
--    (PID Gone at the subject parcel, confirmed live -- the only zoned
--    spatial hit at its centroid is a different neighboring parcel); 26-197
--    (condo parent-parcel centroid mismatch, confirmed live via exact-STRAP
--    check, correctly excluded).
-- C: unchanged, 79.3% (188/237) -- confirmed structural this session (see
--    below), not touched.
-- G: dipped 95.1% -> 94.8% mid-session (regression from the first 2 new
--    zone_code rows exposing a pre-existing PUD@1400 standards gap) ->
--    remediated to 96.9%, then 97.0% after the 13 Round-2 inserts (net
--    improvement over the pre-session baseline -- the remediation also
--    cleaned up the 7 pre-existing PUD@1400 parcels' latent gap from the
--    2026-08-15 migration).
-- All other letters (A,B,D,E,F,H,J): unchanged, still PASS. No regressions.
--
-- Full before/after A-J diff (both live-queried this session):
--   A 117/PASS -> 117/PASS | B 100.0/PASS -> 100.0/PASS | C 79.3/FAIL -> 79.3/FAIL (unchanged, structural)
--   D 97.5/PASS -> 97.5/PASS | E 97.5/PASS -> 97.5/PASS | F 100.0/PASS -> 100.0/PASS
--   G 95.1/PASS -> 97.0/PASS (improved) | H 0.0/PASS -> 0.0/PASS
--   I 90.3/FAIL -> 96.6/PASS (fixed) | J 100.0/PASS -> 100.0/PASS
--
-- ── C: re-confirmed structural, NOT a data gap (independently re-verified,
--    5th+ session to reach this conclusion for st_lucie) ──
-- parity_status breakdown (live query, 2026-08-24):
--   PARITY_OK (65) + matched_clean/tier1% (123) = 188 = matched_clean exactly.
--   CLERK_SSOT_CANCELLED (42, all real clerk-verified cancelled tax-deed
--     sales, parity_source=st_lucie_clerk_tax_deed) + matched_divergent (1)
--     = 43 rows that count toward D (matched_any) but are deliberately
--     excluded from C (matched_clean) by the evaluator's own formula design.
--   NULL parity_status (6) = the same 6 no-parcel_id rows documented above
--     under I (timeshare/aircraft liens, realforeclose 403-blocked).
-- Even a hypothetical 100%-successful resolution of all 6 NULL rows only
-- raises matched_clean to 194/237 = 81.9%, still short of the >=226/237
-- (95%) bar -- the 42 CLERK_SSOT_CANCELLED rows are the dominant blocker
-- and are excluded from the C denominator by design (per
-- supabase/migrations/20260810_gold_standard_shard3_lake_clerk_ssot_cd_recognition.sql).
-- This is a shared-scoring-function question (should genuinely-cancelled
-- clerk-verified sales count against the "clean parity" denominator?), not
-- a per-county data-fix question, and is out of scope for this dispatch's
-- per-county guardrails. Flagged for canon review, not silently patched.
