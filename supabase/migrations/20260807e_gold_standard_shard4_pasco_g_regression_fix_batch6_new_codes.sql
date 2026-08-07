-- Gold Standard shard-4 (dispatch 1338ab5d, county=pasco) — G-criterion regression
-- fix, caused by this session's own I-criterion fix (see
-- 20260807c_gold_standard_shard4_pasco_i_batch6_gis_zone_backfill.sql).
--
-- ROOT CAUSE (CONFIRMED via live query): that migration inserted 45 new
-- parcel_zones rows for 6 zone codes that have NO matching zoning_districts row
-- for jurisdiction_id=1258 (R1MH, PUD, MF2, MF1, RMH, C2). v_zoning_gold_standard_kpi_v3
-- LEFT JOINs parcel_zones -> zoning_districts -> v_zoning_district_applicability;
-- when the zoning_districts join misses entirely, v_zoning_district_applicability
-- never produces a row, so COALESCE(a.far_applicable, true) /
-- COALESCE(a.pk1000_applicable, true) default ALL of these new parcels to
-- "applicable but missing" on the far and pk1000 axes (density already defaults
-- true for residential regardless, which is correct). Live before this migration:
--   G: density=94.0 far=10.0 pk1000=10.0 -> FAIL, metric=10.0
--   (was PASS, metric=100.0, immediately prior to the I-fix migration)
--
-- FIX: register the 6 missing zoning_districts rows so the applicability CASE
-- expression's real category-based fallback logic runs instead of the
-- NULL-join COALESCE(...,true) default. NO numeric FAR/parking/density standard
-- is fabricated for any of these six:
--   - PUD: category='residential', far_regulated=false, pk1000_regulated=false,
--     density_regulated=false -- same structural-placeholder pattern as this
--     jurisdiction's own existing MPUD row (id=13217) and the Sanford/Altamonte
--     Springs PUD precedents (negotiated intensity, no fixed district scalar).
--   - R1MH, MF1, MF2, RMH: category='residential', density_regulated=true
--     (matches every other residential district in this jurisdiction -- R-1,
--     R-2, R-3, R-4, MH, R1 all set density_regulated=true). far_regulated and
--     pk1000_regulated left NULL, which the applicability view's fallback
--     resolves to false for residential-category rows (same as R-1..R-4/MH/R1
--     today) -- correctly not-applicable, not a fabricated true-but-missing gap.
--   - C2: this is a data-variant of the existing hyphenated C-2 district
--     (zoning_districts.id=10905, jurisdiction_id=1258) -- same commercial
--     category, same GIS source. Registered as its own row (code must match the
--     literal 'C2' value already written to parcel_zones.zone_code by the prior
--     migration; not renamed here to avoid altering already-applied data)
--     pointing at category='commercial', far_regulated=true (matching C-2's own
--     convention), with a zone_standards.max_far value carried over from C-2's
--     existing entry -- SAME inferred-pattern value already on file for C-2
--     (source_url tag preserved verbatim: shard9_run651_INFERRED, i.e. this is
--     NOT a new fabrication, it is reusing an already-existing INFERRED
--     convention value under its original disclosure tag, applied to a second
--     row for the same commercial designation recorded under a different code
--     spelling).
--
-- No numeric value in this migration is new/invented -- either NULL (silence,
-- not a guess) or carried over verbatim from an existing on-file INFERRED value
-- for the literal same zone (C-2/C2).
--
-- EXPECTED EFFECT: the 45 parcels from the prior migration split as: PUD-family
-- (PUD+MPUD-linked, already-not-applicable) drop out of the far/pk1000
-- denominators entirely; R1MH/MF1/MF2/RMH/AR/R-2/R-4/R1 (residential, already
-- correctly density-applicable, far/pk1000 not-applicable) also drop out of the
-- far/pk1000 denominators; only C2 (1 parcel) remains far-applicable and now has
-- a value. far_applicable_parcels and pk1000_applicable_parcels should collapse
-- back down close to their pre-I-fix size (previously-passing set), with C2
-- newly added and immediately satisfied.
--
-- cron jobs 109/111/115 and gold_standard_loop()/gold_standard_certify() NOT
-- touched or run. pencil_dod_evaluate_county() NOT modified. Verification via
-- pencil_dod_evaluate_county('pasco') only, appended below as a comment.

BEGIN;

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated, pk1000_regulated, ordinance_section)
SELECT 1258, 'PUD', 'PUD Planned Unit Development', 'residential', false, false, false,
       'Structural placeholder, matching this jurisdiction''s own existing MPUD row '
       || '(zoning_districts.id=13217) and the Sanford/Altamonte Springs PUD precedent '
       || '(negotiated per-project intensity, no fixed district-wide FAR/density/parking '
       || 'scalar exists for base-code PUD in Pasco County LDC Ch.500). No numeric value '
       || 'fabricated. GS-PASCO-4-G-BATCH6-REGRESSION-FIX-V1.'
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 1258 AND code = 'PUD');

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, density_regulated, ordinance_section)
SELECT 1258, v.code, v.name, 'residential', true,
       'Residential base-code district, density-regulated by category same as this '
       || 'jurisdiction''s existing R-1/R-2/R-3/R-4/MH/R1 rows. far_regulated/pk1000_regulated '
       || 'left NULL (resolves to not-applicable via category fallback, same as sibling '
       || 'residential codes). No numeric FAR/density/parking standard fabricated -- gap '
       || 'left open. GS-PASCO-4-G-BATCH6-REGRESSION-FIX-V1.'
FROM (VALUES
  ('R1MH', 'R-1MH Single Family/Mobile Home 1'),
  ('MF1',  'MF-1 Multiple Family Medium Density'),
  ('MF2',  'MF-2 Multiple Family High Density 2'),
  ('RMH',  'R-MH Mobile Home')
) AS v(code, name)
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 1258 AND code = v.code);

-- C2: data-variant spelling of the existing C-2 commercial district. Carries the
-- SAME already-on-file INFERRED max_far value from C-2 (zone_standards.id=3611),
-- not a new fabrication -- disclosure tag preserved.
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, far_regulated, ordinance_section)
SELECT 1258, 'C2', 'C-2 General Commercial (unhyphenated code variant of C-2, id=10905)', 'commercial', true,
       'Same commercial designation as this jurisdiction''s existing C-2 district '
       || '(id=10905); registered separately because parcel_zones.zone_code for these '
       || 'parcels was written as the GIS-literal unhyphenated ''C2'' form. '
       || 'GS-PASCO-4-G-BATCH6-REGRESSION-FIX-V1.'
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 1258 AND code = 'C2');

INSERT INTO zone_standards (zoning_district_id, max_far, source_url, confidence_score)
SELECT d.id, 0.60, 'shard9_run651_INFERRED:standard_fl_ldr_pattern_pasco_c_2 (carried over verbatim from existing C-2 district id=10905/zone_standards id=3611 -- same INFERRED value, not a new fabrication)', 0.60
FROM zoning_districts d
WHERE d.jurisdiction_id = 1258 AND d.code = 'C2'
  AND NOT EXISTS (SELECT 1 FROM zone_standards s WHERE s.zoning_district_id = d.id);

COMMIT;

-- VERIFICATION QUERY (run after apply):
-- SELECT public.pencil_dod_evaluate_county('pasco');
-- Expected: G returns to pass=true (far/pk1000 collapse back toward pre-I-fix
-- levels), I remains pass=true (unaffected -- zoning_districts changes do not
-- alter parcel_zones.zone_code, which is all the I-criterion join checks).
