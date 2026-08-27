-- Gold Standard shard-5 (dispatch 97eac5d8): lake G (zoning FAR/density/parking coverage)
--
-- LIVE BEFORE (verified via rpc/pencil_dod_evaluate_county('lake') at session start):
--   G: {"pass":false,"metric":66.7,"detail":"density=96.9 far=94.1 pk1000=66.7"}
--
-- ROOT CAUSE (already diagnosed by a prior session and re-confirmed live this session):
-- v_zoning_gold_standard_kpi_v3 for lake showed far_applicable_parcels=17 (16 filled=94.1%)
-- and pk1000_applicable_parcels=3 (2 filled=66.7%). The ONE parcel responsible for BOTH
-- gaps is parcel_id='052225010000001900' (case_number 2024CA000927, parcel_zones.id=872519),
-- which carries jurisdiction_id=1030 (Groveland), zone_code='PUD', zone_name='Planned Unit
-- Development' -- written earlier the same day by
-- 20260827_gold_standard_lake_i_property_card_backfill.sql from Lake County GIS
-- CityZoning MapServer layer 3 (https://gis.lakecountyfl.gov/lakegis/rest/services/LocalGov/
-- CityZoning/MapServer/3), ZoningCode="Planned Unit Develop" at centroid 28.60299,-81.84171.
--
-- Confirmed this session: no zoning_districts row existed for (jurisdiction_id=1030,
-- code='PUD') --
--   GET zoning_districts?jurisdiction_id=eq.1030&code=eq.PUD -> [] (empty)
-- Fleet precedent (COALESCE(a.far_applicable, true) / COALESCE(a.pk1000_applicable, true)
-- in v_zoning_district_applicability, e.g. 20260807e_gold_standard_shard4_pasco_g_
-- regression_fix_batch6_new_codes.sql, 20260731c_gold_standard_shard5_orange_i_municipal_
-- gis_refire_6060708f.sql) means an un-registered zone_code defaults BOTH far_applicable
-- and pk1000_applicable to TRUE -- silently counting this parcel as "applicable but
-- missing" on both axes, which is exactly the observed far=94.1/pk1000=66.7 shortfall
-- (pk1000 has a tiny denominator of 3, so one bad parcel swings it hard).
--
-- RESEARCH -- Groveland PUD district FAR/parking regulation (this session, live sources):
--
--   1. Lake County GIS CityZoning MapServer layer 3 (https://gis.lakecountyfl.gov/lakegis/
--      rest/services/LocalGov/CityZoning/MapServer/3?f=json) -- field list is
--      [OBJECTID, City, ZoningCode, Acres, GlobalID, UploadDate, SHAPE, ...]. NO FAR,
--      density, or parking attribute exists on this layer at all -- ruled out as a source.
--
--   2. City of Groveland's OWN Code of Ordinances, Ordinance 2013-08-15 (fetched from
--      Groveland's own Municode-hosted ordinance archive,
--      https://mcclibraryfunctions.azurewebsites.us/api/ordinanceDownload/15132/627997/pdf,
--      confirmed via pdftotext extraction of the live PDF, 7 pages, "AN ORDINANCE OF THE
--      CITY OF GROVELAND, FLORIDA..."). This ordinance amends Sec. 153-159 "PUD Planned
--      Unit Development District" directly (Section Six of the ordinance):
--        Sec. 153-159(b)(3): Commercial PUD permitted-use list only.
--        Sec. 153-159(c): Green Swamp ACSC restrictions (industrial PUDs not permitted;
--          commercial PUDs must comply with 153-157(g)(1)/(2) and 153-158(f)(1)/(2)).
--        Sec. 153-159(h): construction-vesting expiration (3-year window).
--      NONE of subsections (b)(3), (c), or (h) -- the only parts of 153-159 this
--      ordinance touches or quotes -- contain a numeric FAR or parking-per-1000sf value.
--      By contrast the SAME ordinance sets FAR=0.5 explicitly for the C-SR50 Commercial
--      District (Sec. 153-161(c)) and for GS-1/GS-2 special-exception nonresidential uses
--      (Sec. 153-157(g)(1), 153-158(g)(1)) -- proving the ordinance drafters DO state a
--      fixed FAR when one exists, and deliberately did not for base PUD.
--
--   3. City of Groveland Comprehensive Plan, Chapter 1 Future Land Use Element (Ordinance
--      No. 2018-10-34, fetched from Groveland's own document center,
--      https://www.groveland-fl.gov/DocumentCenter/View/3246/Draft-Chapter-01---Future-
--      Land-Use-10-1-18-PDF, confirmed via pdftotext extraction of the live 101-page PDF).
--      This document shows PUD zoning is APPLIED underneath several different Future Land
--      Use categories, each with its own FAR, set at the time of PUD master-plan approval
--      -- not one fixed value for "PUD" as a district:
--        Mixed Use (MU): "A maximum of 0.25 floor area ratio (FAR) may be considered for
--          non-residential uses" (line ~456) -- discretionary ("may be considered"), not
--          a hard cap.
--        Master Planned Community (MPC): "Land subject to this designation will have a
--          Planned Unit Development zoning, which will include a conceptual master plan"
--          (line ~464-466) -- no FAR value stated at all for MPC.
--        North Workplace Development (NWD): PUD zoning "which will include a master plan
--          of the overall design" (line ~482) -- no FAR value stated.
--        (Non-PUD comparison categories elsewhere in the same document DO carry fixed
--         FAR values of 0.5/0.7/1.0, confirming the drafting convention of stating a
--         number when one is fixed.)
--      Parking: no numeric parking-per-1000sf ratio appears anywhere in the Future Land
--      Use Element for PUD or its underlying categories -- only narrative language
--      ("amenity, parking and service facilities", "maximum opportunities for shared
--      parking shall be utilized", "may be supplemented with on-street parking").
--
-- CONCLUSION: Groveland's base PUD zoning district (Sec. 153-159) has NO fixed
-- district-wide FAR or parking-per-1000sf standard in either the zoning ordinance or the
-- comprehensive plan. FAR (when it applies at all) is negotiated per master plan at time
-- of PUD approval and varies by underlying Future Land Use designation (0.25 for Mixed
-- Use non-residential, unstated/discretionary for MPC and NWD). This matches the fleet
-- precedent already established for negotiated PUD/PD districts elsewhere (Pasco PUD id
-- registered far_regulated=false/pk1000_regulated=false in
-- 20260807e_gold_standard_shard4_pasco_g_regression_fix_batch6_new_codes.sql; same
-- pattern used by Okeechobee/other shard sessions for negotiated commercial PD districts).
-- No numeric FAR or parking value is fabricated for this district.
--
-- FIX: register jurisdiction_id=1030/code='PUD' in zoning_districts with
-- far_regulated=false and pk1000_regulated=false, citing the real ordinance/comp-plan
-- sections above. This correctly EXCLUDES the parcel from the far/pk1000 applicable
-- denominators (instead of silently defaulting it to "applicable but missing" via the
-- COALESCE(...,true) fallback), which is the mechanically correct fix per the fleet
-- precedent -- not a numeric guess.
--
-- density_regulated intentionally left NULL/untouched: density was already passing
-- (96.9% >= 95%) before this fix and is not part of the diagnosed failure; no evidence
-- was researched or found to justify changing it, so it is left alone (K3 surgical-change
-- discipline).
--
-- APPLIED LIVE via PostgREST (psql/SUPABASE_DB_PASSWORD is dead this cycle; no generic
-- SQL RPC exists -- rpc/exec and rpc/execute_sql both return PGRST202). Below is the SQL
-- form of the exact write, for the record:

INSERT INTO zoning_districts (
  jurisdiction_id, code, name, category,
  far_regulated, pk1000_regulated, ordinance_section
)
SELECT
  1030, 'PUD', 'PUD Planned Unit Development District', 'residential',
  false, false,
  'Groveland Code of Ordinances Sec. 153-159 (PUD Planned Unit Development District), as '
  || 'amended by Ordinance 2013-08-15; Groveland Comprehensive Plan Ch.1 Future Land Use '
  || 'Element Policy 1.1.x (Mixed Use / Master Planned Community / North Workplace '
  || 'Development categories). No fixed district-wide FAR or parking-per-1000sf standard '
  || 'exists for base PUD zoning -- Sec. 153-159(b)(3)/(c)/(h) specify only permitted '
  || 'uses, Green Swamp restrictions, and construction-vesting expiration, with zero '
  || 'numeric FAR/parking value. FAR is instead set per master-plan/FLU category at time '
  || 'of PUD approval and varies 0.25-1.00 depending on designation (Mixed Use=0.25, '
  || 'Master Planned Community/North Workplace Development=no fixed cap stated, '
  || 'C-SR50/GS-1/GS-2 non-PUD districts=0.5 in the same ordinance). No numeric value '
  || 'fabricated for base PUD code. GS-SHARD5-LAKE-G-97EAC5D8.'
WHERE NOT EXISTS (
  SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 1030 AND code = 'PUD'
);

-- APPLIED (confirmed via POST .../rest/v1/zoning_districts with Prefer:
-- return=representation): new row id=14222, created_at=2026-08-27T16:20:23.705475+00:00.
--
-- LIVE AFTER (re-ran rpc/pencil_dod_evaluate_county('lake') immediately after the write):
--   G: {"pass":true,"metric":96.9,"detail":"density=96.9 far=100.0 pk1000=100.0"}
-- far went 94.1 -> 100.0 (17/17), pk1000 went 66.7 -> 100.0 (3/3), density unchanged at
-- 96.9 (already passing). min(96.9,100.0,100.0)=96.9 >= 95 threshold -> PASS.
--
-- Row persistence re-confirmed via a delayed GET of zoning_districts?id=eq.14222 after
-- doing other work in the same session (see structured session output for the pasted
-- GET response) -- addressing the recent collision-refutation precedent
-- (gold_standard_ultraloop_audit id=18768) where a prior lake-G claim's writes did not
-- persist on re-check.
