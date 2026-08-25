-- St Lucie County, letter I (property card completeness) — dispatch 2ccd6cc6.
--
-- IDEMPOTENT RECORD of live REST writes applied this session via the
-- Supabase Management API (direct psql unavailable in this environment --
-- password auth failure, documented long-standing constraint).
--
-- ── CONTEXT: regression since 2026-08-24 shard-4 691cd31e session ──
-- Yesterday's supabase/migrations/20260824_shard4_691cd31e_stlucie_i_paslc_backfill.sql
-- raised I from 90.3% (214/237) to 96.6% (229/237) PASS via 16 rows fixed
-- (14 tax-deed geo/value backfills + 2 AccountNumber-format zone links) plus
-- 13 more zone_code inserts for the same 14-row batch (Round 2), leaving a
-- documented, honestly-structural 8-row residual (6 no-parcel_id foreclosure
-- rows + 26-137 boundary-artifact parcel + 26-197 condo centroid collision).
--
-- Live re-check today (2026-08-25) found I back down to 93.2% (221/237)
-- FAIL. Independent diagnosis (this session): NOT a reversion of yesterday's
-- 15 parcel_zones inserts or 14 multi_county_auctions updates — all 15
-- parcel_zones rows tagged 'st_lucie_..._20260824*' and all 14 updated
-- multi_county_auctions rows were re-queried live and confirmed still
-- intact. Instead, 8 DIFFERENT rows (26-018, 26-066, 26-068, 26-070, 26-071,
-- 26-073, 26-075, 26-085) that already had property_address + geo +
-- assessed_value populated were found with ZERO parcel_zones row (checked
-- both dash and slash STRAP formats) — these 8 were never mentioned in
-- yesterday's 23-row gap breakdown at all. Root cause of why these 8 newly
-- lack zone linkage is unknown (possible fleet-wide purge, possible gap in
-- yesterday's diagnosis) and out of scope for this fix per dispatch
-- instructions — fixed with real sourced data instead, same as every prior
-- st_lucie I session.
--
-- ── BEFORE (live pencil_dod_evaluate_county('st_lucie'), 2026-08-25) ──
--   I: card_complete=221/237 (93.2%) FAIL
--   G: density=97.0 (97.0%) PASS
--   A/B/D/E/F/H/J: PASS (unchanged), C: 79.3% FAIL (unchanged, structural)
--
-- ── METHOD (reused exactly from 20260824_shard4_691cd31e precedent) ──
-- 1. map.paslc.gov PROD/SLCPA_PublicParcels ArcGIS MapServer/0 — queried by
--    PARCELNO (dash format) for each of the 8 subject parcels. Confirmed
--    SiteAddress matches property_address on file, JustMarketValue matches
--    assessed_value on file, and DistrictGroup gives ground-truth
--    jurisdiction (avoids trusting the task brief's jurisdiction guesses).
-- 2. Zone lookup by jurisdiction:
--    - Unincorporated (DistrictGroup "0002 - Saint Lucie County",
--      jurisdiction_id 1400): slcgis.stlucieco.gov hosting/rest/services/
--      LandUse/Zoning/MapServer/0, attribute query on Parcel_num
--      (dashless STRAP) for an exact match.
--    - Fort Pierce (DistrictGroup "9022 - Fort Pierce", jurisdiction_id
--      971): slcgis.stlucieco.gov hosting/rest/services/LandUse/
--      ForttPierceZoningFLU/MapServer/0, attribute query on Hyphen_PID
--      (exact dash-format STRAP) for an exact match.
-- 3. Every zone link below was confirmed via an EXACT attribute-field match
--    against the subject STRAP (Parcel_num / Hyphen_PID), not a bare
--    spatial/proximity hit — avoids the parcel-complex centroid collision
--    failure mode documented for 26-197 (2026-08-24) and reconfirmed below
--    for 26-085.
--
-- ── RESULTS PER ROW ──
-- 26-018 (3425-706-0193-000-0, 7809 MEADOWLARK LN): DistrictGroup "0002 -
--   Saint Lucie County" (unincorporated, jurisdiction 1400, matches task
--   hint). Unincorporated Zoning layer exact match: Parcel_num
--   342570601930000 == dashless STRAP. Zoned=PUD. PUD@1400 already marked
--   density_regulated=false/far_regulated=false/pk1000_regulated=false from
--   the 2026-08-24 session (real, ordinance-researched non-uniform-PUD
--   finding) — zero G-regression risk, not re-touched.
-- 26-066 (3420-695-1461-000-1, 1985 SE DRANSON CIR): DistrictGroup "0011 -
--   Port Saint Lucie" confirmed. PSL Zoning FeatureServer
--   (services1.arcgis.com/YdUP5V6WwzeG8T8r/Zoning) queried by point (exact
--   centroid from paslc polygon geometry), by point+50ft buffer, and by
--   point+2000ft buffer: ZERO results at tight tolerance; the parcel's
--   longitude (-80.2691) falls just outside this FeatureServer layer's own
--   bounding extent (xmax -80.2746 in WGS84) — a genuine coverage gap in
--   the source layer, not a query error (verified the layer has 6810+
--   overall records and returns data for other points). NOT FIXED — left
--   unlinked, BLANK > WRONG.
-- 26-068 (2405-501-0170-000-9, 1804 N 27TH ST): DistrictGroup "0002 - Saint
--   Lucie County" (unincorporated, jurisdiction 1400 — task brief's
--   "verify jurisdiction" flag correctly resolved as unincorporated, NOT
--   Fort Pierce despite the 34947 zip). Unincorporated Zoning layer exact
--   match: Parcel_num 240550101700009 == dashless STRAP. Zoned=RS-4
--   (already has a real zone_standards row from a prior session).
-- 26-070 (2404-716-0006-000-6, 903 N 20TH ST): DistrictGroup "9022 - Fort
--   Pierce" confirmed. ForttPierceZoningFLU exact match: Hyphen_PID
--   '2404-716-0006-000-6' == subject STRAP exactly, Parcel_Num
--   240471600060006 dashless-consistent. Zoning=R-3 "Single Family
--   Moderate Density Zone" (already has a real zone_standards row).
-- 26-071 (2405-524-0007-000-7, 2603 AVENUE O): DistrictGroup "9022 - Fort
--   Pierce" confirmed. ForttPierceZoningFLU exact match: Hyphen_PID
--   '2405-524-0007-000-7' == subject STRAP exactly. Zoning=R-4 "Medium
--   Density Residential Zone" (already has a real zone_standards row).
-- 26-073 (1432-807-0085-000-6, 2601 ESSEX DR): DistrictGroup "0002 - Saint
--   Lucie County" (unincorporated, jurisdiction 1400, matches task hint).
--   Unincorporated Zoning layer exact match: Parcel_num 143280700850006 ==
--   dashless STRAP. Zoned=RS-4 (already has a real zone_standards row).
-- 26-075 (2404-516-0022-000-0, 1210 N 16TH CT): DistrictGroup "9022 - Fort
--   Pierce" confirmed. ForttPierceZoningFLU exact match: Hyphen_PID
--   '2404-516-0022-000-0' == subject STRAP exactly. Zoning=R-4 "Medium
--   Density Residential Zone" (already has a real zone_standards row).
-- 26-085 (2402-503-0089-000-1, 14 HARBOUR ISLE DR W UNIT 305): confirmed
--   PrimaryLandUse "0400 - Condo" via paslc — same failure class flagged in
--   the task brief. ForttPierceZoningFLU attribute query on exact
--   Hyphen_PID '2402-503-0089-000-1' returned ZERO features (the unit STRAP
--   is not itself a zoning-layer polygon). The only spatial hit at the
--   unit's own centroid resolves to Hyphen_PID '2402-500-0001-000-2'
--   ("805 SEAWAY DR") — a DIFFERENT parcel, the harbour complex's parent
--   parcel, not the subject unit. Confirmed same condo-centroid-collision
--   failure mode as 26-197 (2026-08-24 precedent). NOT FIXED — left
--   unlinked, BLANK > WRONG.
--
-- ── G side-effect check ──
-- All 4 distinct zone codes used below (PUD@1400, RS-4@1400, R-3@971,
-- R-4@971) already have either a real zone_standards row or an explicit
-- density_regulated=false marker from prior sessions (verified live via
-- SELECT against zoning_districts/zone_standards before writing). Zero new
-- zoning_districts rows introduced. Zero G-regression risk confirmed both
-- by pre-check and by the live before/after G value below (unchanged 97.0).
INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, future_land_use, source)
SELECT * FROM (VALUES
  ('3425-706-0193-000-0', NULL::text, 1400, 'PUD',  NULL::text, NULL::text, 'st_lucie_ultraloop_2ccd6cc6_unincorporated_20260825'),
  ('2405-501-0170-000-9', NULL,       1400, 'RS-4', NULL,       NULL,       'st_lucie_ultraloop_2ccd6cc6_unincorporated_20260825'),
  ('2404-716-0006-000-6', NULL,       971,  'R-3',  'Single Family Moderate Density Zone', NULL, 'st_lucie_ultraloop_2ccd6cc6_fortpierce_20260825'),
  ('2405-524-0007-000-7', NULL,       971,  'R-4',  'Medium Density Residential Zone',     NULL, 'st_lucie_ultraloop_2ccd6cc6_fortpierce_20260825'),
  ('1432-807-0085-000-6', NULL,       1400, 'RS-4', NULL,       NULL,       'st_lucie_ultraloop_2ccd6cc6_unincorporated_20260825'),
  ('2404-516-0022-000-0', NULL,       971,  'R-4',  'Medium Density Residential Zone',     NULL, 'st_lucie_ultraloop_2ccd6cc6_fortpierce_20260825')
) AS v(parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, future_land_use, source)
WHERE NOT EXISTS (
  SELECT 1 FROM parcel_zones pz
  WHERE pz.parcel_id = v.parcel_id AND pz.jurisdiction_id = v.jurisdiction_id AND pz.source = v.source
);

-- ── RESULT (verified live via pencil_dod_evaluate_county, 2026-08-25) ──
-- I: 93.2% (221/237) FAIL -> 95.8% (227/237) PASS.
-- G: 97.0% -> 97.0% (unchanged, zero regression).
-- All other letters (A,B,C,D,E,F,H,J): unchanged. C remains structural FAIL
--   (79.3%, unrelated to this fix — see 20260824_shard4_691cd31e migration
--   for the 5th+ independently-reconfirmed root cause).
-- Residual I gap: 10 rows (the original 8 no-parcel_id/structural rows from
--   2026-08-24 [6 no-parcel_id foreclosures + 26-137 boundary artifact +
--   26-197 condo collision] plus 26-066 [PSL zoning layer coverage gap] and
--   26-085 [condo centroid collision, same class as 26-197] from this
--   session). All 10 honestly structural or source-data gaps, not
--   autonomously fixable without fabricating data.
