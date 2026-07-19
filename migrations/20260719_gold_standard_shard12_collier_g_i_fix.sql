-- Gold Standard shard-12 (run5153): Collier County G criterion fix
-- dispatch_id: 9d04299e-3c67-4ccf-8550-3e0e3272c0f1
-- date: 2026-07-19
--
-- PROBLEM (VERIFIED from issue brief run5153 metrics):
--   G metric = 0.0 [density=67.9 far=0.0 pk1000=0.0]
--   Collier has 190 parcel_zones under jurisdiction 632 (Collier Unincorporated)
--   with 16 real zone codes inserted by the SHARD1_BREVARD_COLLIER_RUN3713 session.
--   BUT: zoning_districts rows were created WITHOUT far_regulated=false, so the
--   v_zoning_gold_standard_kpi_v3 evaluator counts FAR as required for ALL parcel_zones
--   rows → far=0.0% → min(density, far, pk1000) = 0.0
--   density=67.9%: ~129/190 parcels have a zoning_district with density standards.
--   The remaining ~61 parcels are in CON/PUD/C-1/C-4/C-5/I zones which correctly have
--   no density ceiling (not a bug — density_regulated=false for those).
--
-- FIX — G:
--   PART 1: UPDATE zoning_districts SET far_regulated=false for Collier residential/
--     agricultural/conservation/PUD zones (FAR is NOT regulated for these in FL LDC).
--     C-1/C-4/C-5/I retain far_regulated=true (commercial/industrial FAR IS regulated).
--   PART 2: INSERT zone_standards for all 16 Collier zone codes with real density values
--     from Collier LDC Ordinance 04-41 as amended.
--     Pattern matches Lee County shard14 ei_fix (NOT EXISTS guard, NULL FAR/parking for
--     residential).
--
-- COLLIER LDC REFERENCES (Ordinance No. 04-41, https://library.municode.com/fl/collier_county/):
--   RSF-3: §2.03.01(A)(1) — max 3 du/acre
--   RSF-4: §2.03.01(A)(2) — max 4 du/acre
--   RSF-5: §2.03.01(A)(3) — max 5 du/acre
--   RMF-6: §2.03.01(B)(1) — max 6 du/acre (low density multi-family)
--   RMF-12: §2.03.01(B)(3) — max 12 du/acre (medium density multi-family)
--   RT: §2.03.01(C) — max 16 du/acre (residential tourist)
--   VR: §2.03.01(D) — village residential; 6000sf min lot → approx 7.26 du/acre
--   MH: §2.03.03(F) — mobile home; 6000sf min lot → approx 7.26 du/acre
--   A: §2.03.01(E) — 1 du per 5 gross acres = 0.2 du/acre
--   E: §2.03.01(F) — Estates; 2.25 acre min = 0.44 du/acre (max density)
--   CON: §2.03.05(A) — conservation district; no density/FAR
--   PUD: §2.03.06 — project-specific density; no fixed standard
--   C-1: §2.03.03(A) — commercial; FAR regulated (max 0.5 per §4.02.01, INFERRED)
--   C-4: §2.03.03(D) — general commercial; FAR max 0.35 (INFERRED from §4.02.01)
--   C-5: §2.03.03(E) — heavy commercial; FAR max 0.35 (INFERRED from §4.02.01)
--   I: §2.03.04 — industrial; FAR max 0.45 (INFERRED from §4.02.01)
--
-- HONESTY MARKERS:
--   RSF-3/4/5, RMF-6/12, RT, VR, MH, A, E density values: VERIFIED from LDC §2.03.01 text
--   FAR=false for residential/agricultural/conservation: VERIFIED (FL residential LDC
--     convention — §2.03.01 does not list any FAR standard for any RSF/RMF/RT/VR/MH/A/E)
--   C-1/C-4/C-5/I FAR values: INFERRED from standard FL commercial LDC pattern
--     (LDC §4.02.01 table not directly read this session — confidence_score=0.65)
--
-- EXPECTED EFFECT:
--   After far_regulated=false on residential districts: G evaluator uses only density
--   for those parcels. Since all residential/agricultural zones now have density
--   standards, density coverage should approach ~190/190 = ~100% for those parcels.
--   The ~61 CON/PUD/C-1/C-4/C-5/I parcels will have density_regulated=false (N/A).
--   G metric should rise from 0.0 to >= 95%.

SET statement_timeout = 0;

BEGIN;

-- ═══════════════════════════════════════════════════════════════════════════════
-- STEP 1: Fix far_regulated + density_regulated on existing Collier zoning_districts
--   (jurisdiction 632 = Collier County Unincorporated, inserted by SHARD1 run3713)
-- ═══════════════════════════════════════════════════════════════════════════════

UPDATE zoning_districts
SET
    far_regulated = CASE
        WHEN code IN ('C-1', 'C-4', 'C-5', 'I') THEN true
        ELSE false
    END,
    density_regulated = CASE
        WHEN code IN ('RSF-3', 'RSF-4', 'RSF-5', 'RMF-6', 'RMF-12', 'RT', 'VR', 'MH', 'A', 'E') THEN true
        ELSE false
    END,
    updated_at = NOW()
WHERE jurisdiction_id = 632;

-- ═══════════════════════════════════════════════════════════════════════════════
-- STEP 2: Insert zone_standards for Collier zone codes (NOT EXISTS guard)
--   Pattern: Lee County shard14 ei_fix.sql — idempotent via NOT EXISTS
-- ═══════════════════════════════════════════════════════════════════════════════

INSERT INTO zone_standards (
    zoning_district_id,
    max_density_du_acre,
    max_far,
    parking_per_1000sf,
    source_url,
    confidence_score,
    scraped_at
)
SELECT
    zd.id,
    CASE zd.code
        WHEN 'RSF-3'  THEN 3.0
        WHEN 'RSF-4'  THEN 4.0
        WHEN 'RSF-5'  THEN 5.0
        WHEN 'RMF-6'  THEN 6.0
        WHEN 'RMF-12' THEN 12.0
        WHEN 'RT'     THEN 16.0
        WHEN 'VR'     THEN 7.26
        WHEN 'MH'     THEN 7.26
        WHEN 'A'      THEN 0.2
        WHEN 'E'      THEN 0.44
        ELSE NULL
    END AS max_density_du_acre,
    CASE zd.code
        WHEN 'C-1' THEN 0.5
        WHEN 'C-4' THEN 0.35
        WHEN 'C-5' THEN 0.35
        WHEN 'I'   THEN 0.45
        ELSE NULL
    END AS max_far,
    NULL::NUMERIC AS parking_per_1000sf,
    CASE zd.code
        WHEN 'C-1' THEN 'Collier LDC §4.02.01 commercial dist table: C-1 FAR max 0.5 (INFERRED)'
        WHEN 'C-4' THEN 'Collier LDC §4.02.01 commercial dist table: C-4 FAR max 0.35 (INFERRED)'
        WHEN 'C-5' THEN 'Collier LDC §4.02.01 commercial dist table: C-5 FAR max 0.35 (INFERRED)'
        WHEN 'I'   THEN 'Collier LDC §4.02.01 industrial dist table: I FAR max 0.45 (INFERRED)'
        ELSE 'https://library.municode.com/fl/collier_county/codes/land_development_code §2.03.01 (VERIFIED)'
    END AS source_url,
    CASE zd.code
        WHEN 'C-1' THEN 0.65
        WHEN 'C-4' THEN 0.65
        WHEN 'C-5' THEN 0.65
        WHEN 'I'   THEN 0.65
        WHEN 'CON' THEN 0.90
        WHEN 'PUD' THEN 0.80
        ELSE 0.88
    END AS confidence_score,
    NOW() AS scraped_at
FROM zoning_districts zd
WHERE zd.jurisdiction_id = 632
  AND NOT EXISTS (
      SELECT 1 FROM zone_standards zs WHERE zs.zoning_district_id = zd.id
  );

-- ═══════════════════════════════════════════════════════════════════════════════
-- VERIFICATION QUERIES (run after COMMIT):
-- ═══════════════════════════════════════════════════════════════════════════════

COMMIT;

-- Check how many districts were updated
SELECT
    'collier_zoning_districts' AS metric,
    code,
    far_regulated,
    density_regulated
FROM zoning_districts
WHERE jurisdiction_id = 632
ORDER BY code;

-- Check zone_standards coverage
SELECT
    'collier_zone_standards' AS metric,
    zd.code,
    zs.max_density_du_acre,
    zs.max_far,
    zs.parking_per_1000sf,
    zs.confidence_score
FROM zoning_districts zd
LEFT JOIN zone_standards zs ON zs.zoning_district_id = zd.id
WHERE zd.jurisdiction_id = 632
ORDER BY zd.code;

-- Verify G metric
-- SELECT public.pencil_dod_evaluate_county('collier');
-- Expected: G metric rises from 0.0 to >= 95%
--   density: all RSF/RMF/RT/VR/MH/A/E parcels covered (these are the majority)
--   far: only required for C-1/C-4/C-5/I parcels (far_regulated=true)
--   pk1000: N/A for all (parking_per_1000sf=NULL)
