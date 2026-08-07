-- Gold Standard shard-5 (dispatch 5d40a513-fb55-4c9c-ad49-be84afb8388f), county=osceola, letter=G.
-- Second fix in this pass -- after 20260807h fixed SRPUD's pk1000 gap (78.6%->100.0%),
-- G's binding constraint shifted to density (94.4%, metric now driven by density not
-- pk1000). BEFORE this migration: pencil_dod_evaluate_county('osceola').G =
-- {"pass": false, "detail": "density=94.4 far= pk1000=100.0", "metric": 94.4}.
--
-- Live gap query (parcel_zones -> zoning_districts by (jurisdiction_id, zone_code) ->
-- v_zoning_district_applicability -> zone_standards, county='osceola' AND
-- density_applicable AND max_density_du_acre IS NULL) returns exactly 3 districts,
-- 1 osceola auction parcel each, all Kissimmee:
--   id=13389 T4-R (Neighborhood Restricted)
--   id=13390 T5-U (Mixed-Use Urban Core)
--   id=13391 MUPUD (Mixed Use Planned Unit Development)
--
-- RESEARCH (live this session, Municode CodesContent API jobId=462754,
-- productId=15261 -- same job as the already-fixed T3/T5-M/SRPUD rows):
--
-- T4-R and T5-U: Kissimmee LDC Chapter 14-5 (Form-Based Code), Sec. 14-5-6
-- "Site Standards" (node PTIIILADECO_CH14-5FOSECO_14-5-6SIST), "Table 5-2:
-- Transect Zone Dimensional Standards". CONFIRMED live fetch: this table's
-- columns are T1/T3/T4-R/T4-O/T5-M/T5-U/T6/SD, and its rows cover Building
-- Placement (setbacks), Building Height (min/max stories), lot standards and
-- frontage buildout -- NO "density" or "du/acre" row or column exists anywhere
-- in the section for ANY transect zone. This is the identical table already
-- used to resolve T3 (id 13220) and T5-M (id 13221) as density_regulated=false
-- in a prior session (2026-07-31) -- T4-R and T5-U are two more columns of the
-- SAME table, same conclusion applies for the same documented reason:
-- density/intensity in the Kissimmee form-based code is controlled by
-- height+lot coverage+setbacks (form-based zoning), not a numeric du/acre cap.
-- This is a real, confirmed structural absence, not an unresearched gap.
--
-- MUPUD: Kissimmee LDC Sec. 14-4-8.D "Mixed-Use Planned Unit Development
-- District (MUPUD)", subsection 4.a.i "MUPUD residential density" (node
-- PTIIILADECO_CH14-4ZO_14-4-8PLUNDEPU). CONFIRMED live verbatim: "The maximum
-- density within a mixed-use future land use designation shall not exceed 75
-- percent of the maximum density permitted by the future land use designation
-- of the site." -- i.e. density is defined as a percentage of the underlying
-- parcel's Future Land Use designation, not a single codified du/acre figure,
-- and is further adjustable via density bonuses (Sec 14-4-8.A.3 criteria).
-- This is the SAME per-development, per-underlying-FLU pattern already
-- confirmed and applied to Osceola County's own PD district (zoning_districts
-- id 11796, Sec 3.11.1(I): "allowable density and intensity will be based on
-- several factors...") and to Kissimmee SRPUD (id 13180, via RPUD Sec
-- 14-4-8.B.4.a.i, textually near-identical to this MUPUD subsection). Marking
-- density_regulated=false is consistent with that established, ordinance-
-- verified precedent for PUD-type districts city/county-wide -- not a new or
-- inconsistent rule invented for this pass.
--
-- FIX: set density_regulated=false directly on zoning_districts for these 3
-- districts (same mechanism already used for PD/T3/T5-M -- confirmed via
-- pg_get_viewdef(v_zoning_district_applicability) that the view reads these
-- columns with a category-based default only when NULL). No zone_standards
-- max_density_du_acre value is fabricated for any of the three.

UPDATE public.zoning_districts
SET density_regulated = false
WHERE id IN (13389, 13390, 13391)
  AND jurisdiction_id = 957
  AND code IN ('T4-R', 'T5-U', 'MUPUD');
