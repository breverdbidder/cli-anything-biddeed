-- Gold Standard shard-9 (dispatch 2a942b32): fix a G regression this session's own
-- I-fix migration (20260731d) caused on pasco + taylor. Adding 3 new parcel_zones rows
-- (MPUD, R1 for pasco; RSF/MH-2 for taylor) with no matching zoning_districts row made
-- v_zoning_gold_standard_kpi_v3 treat them as far/pk1000-APPLICABLE-but-missing (the
-- COALESCE(applicability, true) default), dropping pasco G from 100/100/100 to
-- density=99.2/far=50.0/pk1000=50.0 and taylor G from 100/null/null to 88.9/0.0/0.0.
--
-- Fix: add real zoning_districts + zone_standards rows for the 3 new codes, sourced
-- from the actual ordinance text (not fabricated numbers):
--   Pasco LDC Ch.500 Sec.514.5.A.2 p.514-2 (R1: max density 2.2 du/ac, not FAR/parking-regulated)
--   Pasco LDC Ch.500 Sec.522.2.A.1.a p.522-1/2 (MPUD: density is per-project via FLU class x
--     acreage, no blanket table value -- correctly marked not density/far/parking-regulated
--     rather than fabricating a number)
--   City of Perry LDR (2022-09-13) Sec.4.6.6/4.6.9 (RSF/MH-2: no blanket du/acre value exists,
--     but DOES carry a real 1.0 FAR cap -- correctly density-NA, far-regulated=true with a
--     real sourced max_far)

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, density_regulated, far_regulated, pk1000_regulated, ordinance_section)
VALUES
  (1258, 'MPUD', 'MPUD Planned Unit Development', 'residential', false, false, false,
   'Pasco LDC Ch.500 Sec.522.2.A.1.a (density set per-project via FLU classification x developable acreage, no blanket table value)'),
  (1258, 'R1', 'R-1 Rural Density Residential', 'residential', true, false, false,
   'Pasco LDC Ch.500 Sec.514.5.A.2 p.514-2'),
  (908, 'RSF/MH-2', 'Residential (Mixed) Single Family/Mobile Home', 'residential', false, true, false,
   'City of Perry LDR (2022-09-13) Sec.4.6.6/4.6.9')
ON CONFLICT DO NOTHING;

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score)
SELECT id, 2.2, 'mapping.pascopa.com/pdf/20120123_ldc_ch500.pdf#page=59', 'Sec.514.5.A.2 p.514-2', 0.95
FROM zoning_districts WHERE jurisdiction_id=1258 AND code='R1'
ON CONFLICT DO NOTHING;

INSERT INTO zone_standards (zoning_district_id, max_far, source_url, ordinance_section, confidence_score)
SELECT id, 1.0, 'ncfrpc.org/MapsAndPlans/CitiesAndTowns/Perry/LDR_Perry_Sept22_Salmon.pdf', 'Sec.4.6.9', 0.95
FROM zoning_districts WHERE jurisdiction_id=908 AND code='RSF/MH-2'
ON CONFLICT DO NOTHING;
-- MPUD intentionally gets no zone_standards row: it is marked not density/far/parking
-- regulated above (a real classification fact, not a numeric guess), so it is excluded
-- from all three applicable-denominators and needs no standards values.
