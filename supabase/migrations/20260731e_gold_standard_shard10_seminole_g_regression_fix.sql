-- Gold Standard shard-10 (dispatch 96a9bc5d-bc36-4e5c-904e-b80ae8b1165a): seminole.
-- P0 regression fix: this session's own I-letter fixes (2 parallel research agents
-- inserting parcel_zones rows to close the property-card completeness gap) introduced
-- a real G regression, caught live before session close-out.
--
-- Baseline BEFORE this session (VERIFIED 2026-07-31): G PASS 97.4%%
--   (density=97.4 far=100.0 pk1000=100.0).
-- MID-SESSION (after I-fix migrations 20260731c/20260731d landed): G FAIL 70.0%%
--   (density=91.5 far=80.0 pk1000=70.0) -- a real regression, not a false alarm.
--
-- Root cause (VERIFIED via v_zoning_gold_standard_kpi_v3 + parcel_zones/zoning_districts
-- join diagnostic): 2 parcel_zones rows (07-20-31-506-0000-0980, 35-19-30-523-0000-0480,
-- case numbers 2025CA000122/2025CA000244) were inserted with zone_code='SR1' and 1 row
-- (07-20-31-513-0000-0130, case 2025CA000307) with zone_code='MR3' -- both missing the
-- hyphen present in Sanford's REAL zoning_districts codes ('SR-1' id verified via join,
-- 'MR-3' id 6320, both pre-existing, sourced from Sanford LDC well before this session).
-- The LEFT JOIN to zoning_districts/v_zoning_district_applicability therefore returned
-- NULL for these 3 rows, and the KPI view's COALESCE(a.far_applicable, true) /
-- COALESCE(a.pk1000_applicable, true) / COALESCE(a.density_applicable, true) defaults
-- treat a missing join as "applicable" -- so all 3 rows counted against the density/far/
-- pk1000 denominators with zero numerator contribution, a triple-metric hit from a pure
-- string-formatting mismatch (not a real zoning gap; Sanford SR-1 already has real
-- max_far=0.25/max_density_du_acre=6.00, MR-3 already has max_far=0.83/max_density=20.00).
--
-- Fix: correct the 3 parcel_zones.zone_code values to match the existing real district
-- codes. Additive/corrective only -- no new zoning_districts/zone_standards rows created,
-- no fabricated values.
--
-- Result (VERIFIED, re-ran pencil_dod_evaluate_county('seminole') immediately after):
-- G 70.0 -> 97.9%% (density=97.9 far=100.0 pk1000=100.0) -- back to PASS, above the
-- original pre-session baseline. Audit row gold_standard_ultraloop_audit id 11635,
-- letter G, survived=true.

UPDATE parcel_zones
SET zone_code = 'SR-1'
WHERE jurisdiction_id = 904 AND zone_code = 'SR1'
  AND parcel_id IN ('07-20-31-506-0000-0980', '35-19-30-523-0000-0480');

UPDATE parcel_zones
SET zone_code = 'MR-3'
WHERE jurisdiction_id = 904 AND zone_code = 'MR3'
  AND parcel_id = '07-20-31-513-0000-0130';

SELECT public.pencil_dod_evaluate_county('seminole');
