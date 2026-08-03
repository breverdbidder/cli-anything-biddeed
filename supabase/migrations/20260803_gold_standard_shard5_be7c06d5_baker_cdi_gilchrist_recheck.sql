-- Gold Standard shard-5 (gilchrist/baker), dispatch be7c06d5-73b3-45b5-9c8f-
-- a86ce79202bf, session architect-20260803T080000, loop run 8415.
--
-- ULTRALOOP native mode (Workflow tool): 3 parallel research/fix agents
-- (baker-parity-c-d, baker-zoning-i, gilchrist-baker-newangle-recheck),
-- each followed by an independent adversarial verifier before any write.
--
-- Writes already applied LIVE during the session (via PostgREST, service_role
-- key) before this file was written -- this documents exactly what ran.
--
-- RESULT SUMMARY (pencil_dod_evaluate_county, before -> after, verified live):
--   gilchrist: unchanged, 8/10 (E,I fail). No write -- 6th independent session
--     confirms the 6 remaining unlinked cases are structurally blocked
--     (RealForeclose placeholder-only parcel link, qpublic/gilchristclerk 403,
--     Civitek OCRS Turnstile-gated with no case-number search field). This
--     session's new angle (Florida legal-notice aggregators, e.g.
--     floridapublicnotices.com) found zero indexed notices for any of the 6
--     cases -- correctly reported BLANK, nothing fabricated.
--   baker: C 20.0%->46.7%, D 20.0%->46.7%, I 20.0%->46.7% (still FAIL, real
--     forward progress, not certified). E unchanged 46.7% (4 cases remain
--     structurally blocked, same new-angle recheck as gilchrist, same BLANK
--     result). Still 6/10 overall (A,B,F,G,H,J pass; C,D,E,I fail) but three
--     of the four failing metrics moved for the first time across 5+ prior
--     baker sessions.
--
-- ADVERSARIAL VERIFICATION CAUGHT A REAL BUG: the first-pass baker C/D
-- proposal used case_number values WITHOUT the 'CAAXMX' suffix (e.g.
-- '022026CA000018' instead of the actual stored '022026CA000018CAAXMX').
-- The refuter independently queried the live table and proved the proposed
-- WHERE clause matched zero rows -- a silent no-op that would have shipped
-- as a false "fixed" claim. The underlying data match itself (Baker parcel/
-- address/value confirmed against Baker County's own ArcGIS parcels_web2
-- FeatureServer, the same authority backing bakerpa.com which was HTTP 521
-- at the time) was accurate; only the SQL was wrong. Corrected case_number
-- values (independently re-confirmed against live multi_county_auctions
-- before executing) are used below. See gold_standard_ultraloop_audit rows
-- for the full claim/refuter trail (dispatch_id above, county_slug in
-- ('baker','gilchrist')).

BEGIN;

-- 1. Unincorporated Baker County jurisdiction (did not exist -- only
--    Macclenny id=920 and Glen St. Mary id=982 existed for county='Baker').
INSERT INTO public.jurisdictions (name, county, state, co_no, active, data_source)
SELECT 'Unincorporated Baker County', 'Baker', 'FL', 2, true,
       'baker_county_gis_arcgis_parcels_web2_live_query_2026-08-03'
WHERE NOT EXISTS (
  SELECT 1 FROM public.jurisdictions WHERE county = 'Baker' AND name = 'Unincorporated Baker County'
);
-- Applied live as jurisdiction id=1664.

-- 2. AG 7.5 zoning district under the new jurisdiction. Verbatim from Baker
--    County Code of Ordinances Sec. 24-191 (via Zoneomics-hosted municode
--    text; library.municode.com itself 403'd), cross-confirmed as a real,
--    common code (3553 parcels) in Baker's own live ArcGIS parcels_web2
--    FeatureServer, not a one-off/fabricated value.
INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated, ordinance_section)
SELECT j.id, 'AG 7.5', 'Agricultural District: AG 7.5 (Sec. 24-191)', 'Agricultural', false, true, 'Sec. 24-191'
FROM public.jurisdictions j
WHERE j.county = 'Baker' AND j.name = 'Unincorporated Baker County'
  AND NOT EXISTS (
    SELECT 1 FROM public.zoning_districts zd WHERE zd.jurisdiction_id = j.id AND zd.code = 'AG 7.5'
  );
-- Applied live as zoning_districts id=13420.

-- 3. Real numeric standards for AG 7.5, sourced verbatim from Sec. 24-191(f):
--    min lot width 200ft / area 7.5 acres, setbacks front 50/side 30/rear 25
--    ft, max height 35ft, density "one unit per 7.5 acres to one unit per 19
--    acres" -> max_density_du_acre = 1/7.5 = 0.1333 (most-permissive end).
--    No FAR standard (agricultural, not FAR-regulated) and no parking
--    standard (not commercial) -- both left NULL, not invented.
INSERT INTO public.zone_standards (
  zoning_district_id, min_lot_sqft, min_lot_width_ft, max_height_ft,
  front_setback_ft, side_setback_ft, rear_setback_ft, max_density_du_acre,
  source_url, ordinance_section, confidence_score
)
SELECT zd.id, 326700, 200.00, 35.00, 50.00, 30.00, 25.00, 0.1333,
       'https://www.zoneomics.com/code/baker-county-unincorporated-FL/chapter_4',
       'Sec. 24-191', 0.85
FROM public.zoning_districts zd
JOIN public.jurisdictions j ON j.id = zd.jurisdiction_id
WHERE j.county = 'Baker' AND j.name = 'Unincorporated Baker County' AND zd.code = 'AG 7.5'
  AND NOT EXISTS (SELECT 1 FROM public.zone_standards zs WHERE zs.zoning_district_id = zd.id);
-- Applied live as zone_standards id=5672.

-- 4. parcel_zones row for parcel 121S20000000000021 (13735 O C Horne Rd,
--    Sanderson) -- address-matched live against Baker's ArcGIS parcels_web2
--    FeatureServer (Zoning='AG 7.5'), confirmed 2026-08-03, unincorporated.
INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT '121S20000000000021', j.id, 'AG 7.5',
       'Agricultural District: AG 7.5 (Sec. 24-191) - Baker County GIS parcels_web2 layer',
       'baker_county_gis_arcgis_parcels_web2_live_2026-08-03'
FROM public.jurisdictions j
WHERE j.county = 'Baker' AND j.name = 'Unincorporated Baker County'
  AND NOT EXISTS (SELECT 1 FROM public.parcel_zones WHERE parcel_id = '121S20000000000021');
-- Applied live as parcel_zones id=852183.

-- 5. parcel_zones row for parcel 073S22023800000290 (8696 Lake George Cir W,
--    Macclenny) -- same FeatureServer query shows Zoning='CITY',
--    Descriptio='INCORPORATED AREAS' -- inside Macclenny city limits, using
--    the existing CITY delegation-marker pattern already registered under
--    jurisdiction_id=920 (same as precedent parcel 043S22000000000540).
INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT '073S22023800000290', 920, 'CITY',
       'City-managed zoning (Macclenny) - Baker County GIS parcels_web2 layer',
       'baker_county_gis_arcgis_parcels_web2_live_2026-08-03'
WHERE NOT EXISTS (SELECT 1 FROM public.parcel_zones WHERE parcel_id = '073S22023800000290');
-- Applied live as parcel_zones id=852184.

-- 6. Parity backfill for the 2 baker cases that already had full parcel/
--    address/geo/value data but had never been parity-checked. Verified
--    (both by the research agent and independently by this session's
--    refuter/orchestrator, using the CORRECTED case_number with its
--    'CAAXMX' suffix) against Baker County's ArcGIS parcels_web2
--    FeatureServer -- PARCELNO, address, and assessed_value all match
--    exactly. Affects both duplicate rows per case (foreclosure + tax_deed
--    sale_type).
UPDATE public.multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1_baker_realforeclose_bakerpa_v1:baker:20260803_cdgap',
    parity_confidence = 0.95,
    parity_checked_at = '2026-08-03T08:08:58Z',
    last_parity_check = '2026-08-03T08:08:58Z'
WHERE county = 'baker' AND case_number IN ('022026CA000018CAAXMX', '022025CA000148CAAXMX');

COMMIT;

-- SQL VERIFICATION (run 2026-08-03, this session, live Management API/REST):
--
-- SELECT public.pencil_dod_evaluate_county('baker');
--   BEFORE: C=20.0 (matched_clean=3), D=20.0 (matched_any=3), I=20.0
--           (card_complete=3 of 15), E=46.7 (parcel_linked=7) [unchanged]
--   AFTER:  C=46.7 (matched_clean=7), D=46.7 (matched_any=7), I=46.7
--           (card_complete=7 of 15), E=46.7 (parcel_linked=7) [unchanged,
--           correctly -- this session did not add new parcel_id links]
--   G also incidentally improved from "density=<blank>" to "density=100.0"
--           (the new AG 7.5 district populated a previously-N/A density
--           metric) -- G remains PASS, no regression.
--   Still 6/10 overall (A,B,F,G,H,J pass; C,D,E,I fail) -- NOT certified,
--   honestly reported as forward progress, not a completion.
--
-- SELECT public.pencil_dod_evaluate_county('gilchrist');
--   BEFORE == AFTER on all 10 letters (8/10, E/I fail at 57.1%) -- zero
--   writes made for gilchrist this session, re-confirmed live.
--
-- Timestamp: 2026-08-03T08:20:00Z UTC.
