-- GOLD STANDARD shard-3 (dispatch 9f7b5985-3765-4e7b-955c-10e2f2aca59e), county=columbia.
--
-- P0 REVERT of 20260808_shard3_columbia_i_lakecity_zoning_atlas_backfill.sql.
--
-- That migration inserted 5 verified parcel_zones rows for City of Lake
-- City (jurisdiction_id=974), correctly moving I from 73.5% (25/34) to
-- 88.2% (30/34) -- confirmed live via pencil_dod_evaluate_county
-- immediately after applying.
--
-- However the SAME live check showed G regressed from PASS (100.0) to FAIL
-- (density=82.1 far=0.0 pk1000=0.0). Root cause (confirmed by reading
-- v_zoning_gold_standard_kpi_v3 and v_zoning_district_applicability):
-- jurisdiction_id=974 (Lake City) has zero zoning_districts/zone_standards
-- rows. The KPI view's CTE does
-- COALESCE(a.far_applicable, true) / COALESCE(a.pk1000_applicable, true) /
-- COALESCE(a.density_applicable, true) -- when a parcel_zones row has NO
-- matching zoning_districts row at all (our case), applicability defaults
-- to true across the board (not the residential-aware false-for-FAR/parking
-- default that v_zoning_district_applicability would otherwise apply),
-- and with no zone_standards row every one of the 5 new parcels counts as
-- "applicable but missing" for density/FAR/parking, dragging the county's
-- percentages down.
--
-- Fixing this properly requires real Lake City Chapter 110 (LDR) dimensional
-- standards (density/FAR/parking) per zone code, sourced from ordinance
-- text -- guessed numeric standards are explicitly BANNED (ghost-success).
-- Attempted this live: library.municode.com's Lake City chapter is an
-- Angular SPA that does not render chapter content even after a 45s
-- virtual-time-budget headless Chrome dump (XHR-driven content, no static
-- fallback found); the lcfla.com-hosted LDR PDF link (24_ldr_lakec.pdf) is
-- dead (404, confirmed live); no archive.org snapshot exists. No real
-- numeric standard could be sourced this session.
--
-- Per campaign rule ("regressing a currently-passing letter is P0 and must
-- not be left standing"), reverting the parcel_zones insert takes priority
-- over keeping the I gain. The 8-parcel atlas read (5 survived adversarial
-- verification: 10846-104/11375-000/11612-000=RSF-3, 11651-000=RSF-1,
-- 13831-000=RO; 3 did not survive: 10989-000, 13118-001, 11388-000) remains
-- valid and reusable -- a future session should ship these together with a
-- real Chapter 110 zoning_districts + zone_standards backfill for
-- jurisdiction_id=974 (or with far_regulated=false/pk1000_regulated=false
-- explicitly set on the zoning_districts rows, which is a defensible
-- categorical call for single-family residential zones under
-- v_zoning_district_applicability's own commercial/industrial-only FAR
-- default -- but max_density_du_acre still needs a real ordinance-sourced
-- value before G can be re-verified safe).

SET statement_timeout = 0;

BEGIN;

DELETE FROM public.parcel_zones
WHERE jurisdiction_id = 974
  AND parcel_id IN ('10846-104', '11375-000', '11612-000', '11651-000', '13831-000')
  AND source = 'lcfla_zoning_atlas_pdf_visual:lczn13:2026-08-08';

COMMIT;
