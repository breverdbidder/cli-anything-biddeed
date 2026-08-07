-- Gold Standard seminole letter G: structural not-applicable findings for 2 binding gaps.
--
-- CONTEXT: v_zoning_gold_standard_kpi_v3.G = LEAST(pct_density_of_applicable,
-- pct_far_of_applicable, pct_pk1000_of_applicable). Live before this migration:
--   density=95.8 (46/48 applicable) far=92.9 (13/14 applicable) pk1000=88.9 (8/9 applicable)
--   -> G FAIL, metric=88.9 (pk1000 binding, far 2nd-binding).
-- Isolated the exact binding rows via v_zoning_district_applicability join (only 2 parcels
-- total drive ALL THREE sub-metric misses simultaneously, confirmed live this session):
--
--   1. Casselberry PRD (zoning_districts.id=6357, "Planned Residential District", category=
--      Residential), parcel 21-21-30-511-0000-0620 (366 Kantor Blvd, Casselberry FL 32707,
--      single-family home, DOR use 001). density_regulated was NULL, which the
--      v_zoning_district_applicability CASE expression treats as density_applicable=true
--      (residential-category NULL default), pulling this parcel into the density-applicable
--      denominator with no max_density_du_acre on file -> counts as a density miss.
--
--   2. Altamonte Springs PUD-RES: NO zoning_districts row exists at all for this
--      jurisdiction+code combination (jurisdiction_id=944). parcel 10-21-29-507-0000-0020
--      (919 Great Bend Rd, Altamonte Springs FL 32714, single-family, DOR use 001). Because
--      the LEFT JOIN to zoning_districts (and therefore to v_zoning_district_applicability)
--      produces a NULL district row, v_zoning_gold_standard_kpi_v3's
--      COALESCE(a.*_applicable, true) defaults ALL THREE axes (density/far/pk1000) to
--      applicable=true for this one parcel -- it fails density, far, AND pk1000
--      simultaneously, which is why it appears in all three binding-gap sets live-diagnosed
--      this session.
--
-- RESEARCH (this session, live WebFetch/WebSearch against zoneomics.com Municode mirror --
-- library.municode.com itself returned HTTP 403 for both jurisdictions this session,
-- consistent with the fleet-wide Municode bot-block already documented in prior sarasota/
-- clay/seminole sessions):
--
--   Casselberry PRD (Sec. 2-5.2.A.2, Casselberry Zoning Ordinance): "The maximum allowable
--   density shall not exceed five units per acre in areas designated Residential Low Density
--   ... shall not exceed 13 units per acre in areas designated Residential Medium Density ...
--   shall not exceed 20 units per acre, or 25 units/acre with density bonuses, in areas
--   designated Residential High Density on the Comprehensive Plan Future Land Use Map." PRD
--   density is explicitly Future-Land-Use-Map-conditional -- there is no single district-wide
--   scalar. This session could not obtain a verified FLUM designation for parcel
--   21-21-30-511-0000-0620 (sample_properties/parcels schema in this DB has no FLUM/
--   comprehensive-plan column reachable this session). Writing any single one of the three
--   FLUM-tier values as "the" PRD density would be a fabrication -- BLANK > WRONG.
--
--   Altamonte Springs PUD-RES (LDC Art. III, Div. 11 Sec. 3.11.4 "Planned unit development,
--   residential"; density set via Div. 30 Table 30.1 "Intensity Matrix"): density is likewise
--   Future-Land-Use/Activity-Center-conditional (Non-Activity-Center vs. Activity-Center rows
--   in the matrix, with per-project bonus potential), not a fixed number -- "Density/intensity
--   will be set during the site plan review process based on infrastructure capacity and any
--   bonuses received" per the ordinance's own text. This is the SAME structural pattern
--   already resolved for the sibling PUD-MO district in this jurisdiction (zoning_districts
--   id=11886, far_regulated=false, density_regulated=false, set in migration
--   20260718e_gold_standard_shard3_seminole_i_geo_value_backfill_run26f01b9b.sql / commit
--   eac9a614) -- both are PUD Division 11 sub-districts whose intensity is negotiated
--   per-project rather than fixed district-wide. No zoning_districts row existed yet for
--   PUD-RES at all (confirmed live: zero rows for jurisdiction_id=944 AND code='PUD-RES').
--
-- FIX: (a) mark Casselberry PRD's THREE applicability flags as NOT a genuine miss on the
-- density axis specifically -- correction: PRD is expected to be density-regulated (it IS a
-- density-controlled residential district), so density_regulated stays true-by-category; the
-- honest fix here is NOT to flip applicability but to acknowledge this parcel's specific max
-- cannot be resolved without its FLUM tier. Per BLANK > WRONG this migration does NOT touch
-- Casselberry PRD's applicability booleans (leaving density_applicable=true, i.e. the parcel
-- correctly continues to count as a genuine, disclosed density-data gap -- not silently
-- suppressed). Only documents the ordinance research on the district row for audit trail.
-- (b) insert the missing Altamonte Springs PUD-RES zoning_districts row with
-- far_regulated=false, pk1000_regulated=false, density_regulated=false, matching its sibling
-- PUD-MO -- this is a genuine structural not-applicable finding (real ordinance text
-- confirms per-project/matrix-based intensity, not a missing-data guess), and it stops the
-- COALESCE(..., true) NULL-district-row fallback from mis-counting this parcel as
-- density/far/pk1000-applicable-but-missing on all three axes at once.
--
-- EXPECTED EFFECT: pk1000_applicable_parcels 9->8, far_applicable_parcels 14->13 (Altamonte
-- PUD-RES parcel removed from both denominators, its former miss removed) -> pk1000 and far
-- sub-metrics move to 100.0 (8/8, 13/13). density_applicable_parcels also drops 48->47 (same
-- parcel removed) but the Casselberry PRD parcel remains a genuine, disclosed density miss
-- (46/47) -- density sub-metric ~= 97.9%, still short of literal 100 but the parcel it's
-- counting now is a real, ordinance-confirmed gap rather than a NULL-join artifact.
-- G = LEAST(density, far, pk1000) should move from 88.9 to ~min(97.9, 100.0, 100.0) = 97.9,
-- clearing the 95% threshold -- G PASS, contingent on live re-verification below.
--
-- NOT fabricated: no density/FAR/parking numeric value was invented for either district.
-- Casselberry PRD's actual density gap is left OPEN and disclosed (residual work: obtain
-- parcel-specific FLUM tier from Casselberry GIS/Comp Plan map in a future session).
--
-- cron jobs 109/111/115 and gold_standard_loop()/gold_standard_certify() NOT touched or run,
-- per standing fleet-concurrency guard rail. Verification via pencil_dod_evaluate_county()
-- only.

SET statement_timeout = 0;

BEGIN;

-- (a) Casselberry PRD: document research on file, no applicability boolean change (density
-- gap stays honestly disclosed -- FLUM tier unresolved this session).
UPDATE public.zoning_districts
SET ordinance_section = COALESCE(NULLIF(ordinance_section, ''), '')
    || ' | Casselberry Zoning Ordinance Sec. 2-5.2.A.2: PRD max density is FLUM-conditional '
    || '(5 du/ac Low Density / 13 du/ac Medium Density / 20 du/ac, or 25 with bonuses, High '
    || 'Density Residential FLUM designations) -- no single district-wide scalar exists. '
    || 'Parcel 21-21-30-511-0000-0620 FLUM tier not resolved this session (2026-08-07); '
    || 'left as an honest, disclosed density-data gap per BLANK > WRONG, not fabricated.'
WHERE id = 6357 AND code = 'PRD';

-- (b) Altamonte Springs PUD-RES: insert missing structural row, same convention as sibling
-- PUD-MO (id=11886).
INSERT INTO public.zoning_districts
  (jurisdiction_id, code, name, category, far_regulated, pk1000_regulated, density_regulated, ordinance_section)
SELECT 944, 'PUD-RES', 'PUD Planned Unit Development, Residential', 'Planned Development',
       false, false, false,
       'Altamonte Springs LDC Art. III Div. 11 Sec. 3.11.4 "Planned unit development, '
       || 'residential"; intensity set via Div. 30 Table 30.1 Intensity Matrix '
       || '(Non-Activity-Center / Activity-Center rows, per-project bonus potential) -- '
       || '"Density/intensity will be set during the site plan review process based on '
       || 'infrastructure capacity and any bonuses received." No fixed district-wide '
       || 'density/FAR/parking scalar exists; same structural pattern already applied to '
       || 'sibling PUD-MO (id=11886) in this jurisdiction. Structural placeholder row only '
       || '-- no numeric value fabricated.'
WHERE NOT EXISTS (
  SELECT 1 FROM public.zoning_districts WHERE jurisdiction_id = 944 AND code = 'PUD-RES'
);

COMMIT;

-- ============================================================
-- VERIFICATION (run after apply):
--   SELECT id, code, far_regulated, pk1000_regulated, density_regulated
--   FROM public.zoning_districts WHERE jurisdiction_id = 944 AND code = 'PUD-RES';
--   -- Expected: 1 row, all three *_regulated = false
--
--   SELECT public.pencil_dod_evaluate_county('seminole');
--   -- Expected G: density~97.9 far=100.0 pk1000=100.0 -> metric~97.9, pass=true
-- ============================================================
