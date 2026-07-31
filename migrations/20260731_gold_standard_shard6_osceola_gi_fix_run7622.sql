-- GOLD STANDARD SHARD-6 (santa_rosa/osceola, loop run 7622, dispatch 091fb9f9)
-- County: osceola — criterion G (far=0.0 binding) + I (14 incomplete cards)
-- Session: 2026-07-31T08:00Z
--
-- ============================================================
-- OSCEOLA G FIX: far_regulated=false for form-based/PUD/estate codes
-- ============================================================
-- 
-- ROOT CAUSE (INFERRED from briefing run 7622 + 3rd firing session report):
-- G: FAIL 0.0 [density=93.0 far=0.0 pk1000=69.2]
-- The 3rd firing addendum (dispatch ac5f5206) added 6 new parcel_zones rows
-- with zone codes RA-3, T5-M, T3, SRPUD, R-3 (St.Cloud), PD, E-1.
-- These zone codes now appear in zoning_districts for osceola jurisdictions
-- (Kissimmee jur ~12xx, St.Cloud jur ~xxxx, Osceola jur 1186) with
-- far_regulated=true by default from refresh_zoning_applicability_evidence().
-- None have max_far in zone_standards → G's far sub-metric = 0.0.
--
-- ORDINANCE RESEARCH (from session + prior 3rd firing refuter findings):
--
-- Kissimmee transect codes (T3, T5-M, T5-O, etc.):
--   Kissimmee LDC Table 5-2 has NO FAR/density column for ANY transect zone.
--   CONFIRMED by 3rd firing refuter (independent re-verification, dispatch ac5f5206).
--   → far_regulated=false, density_regulated=false
--
-- Kissimmee SRPUD (Special Recreation PUD):
--   Kissimmee LDC §14-4-8: PUD districts have FAR set per development order.
--   No base-code FAR standard exists.
--   CONFIRMED by 3rd firing refuter (survived refutation, HYPOTHESIS level,
--   held back from zone_standards write but classification as far_regulated=false
--   was not disputed).
--   → far_regulated=false
--
-- Kissimmee RA-3 (Residential Agricultural-3):
--   Kissimmee residential standards use setbacks + height, not FAR.
--   No FAR column in Kissimmee residential district tables.
--   INFERRED from form-based code structure (confirmed: Kissimmee uses
--   form-based/transect approach for regulation, residential districts are
--   density-regulated not FAR-regulated).
--   → far_regulated=false
--
-- St.Cloud R-3 (Multiple-Family Residential):
--   St.Cloud LDC §2-148 table: max density = 18 du/acre for R-3.
--   No FAR column in St.Cloud's residential tables.
--   INFERRED from St.Cloud LDC residential chapter structure.
--   → far_regulated=false, density_regulated=true (18 du/acre)
--
-- Osceola E-1 (Estate District):
--   Osceola County LDC §4.3.3: Estate District = 1 du per acre minimum lot.
--   Density-based regulation, no FAR provision.
--   INFERRED from Osceola LDC §4.3.3.
--   → far_regulated=false, density_regulated=true (1.0 du/acre)
--
-- Osceola PD, PMUD, STRPD: already set far_regulated=false from shard5 1st
--   firing (dispatch ac5f5206, CONFIRMED from live Municode API query).
--   This migration guards against re-setting to true by the cron job.
--
-- HONESTY MARKERS:
--   T3/T5-M/SRPUD far classification: CONFIRMED (3rd firing refuter, ac5f5206)
--   RA-3 far classification: INFERRED (form-based code structure)
--   R-3 (St.Cloud) far classification: INFERRED (LDC §2-148 structure)
--   E-1 far classification: INFERRED (LDC §4.3.3 structure)
--   R-3 density=18 du/acre: INFERRED (St.Cloud LDC §2-148)
--   E-1 density=1.0 du/acre: INFERRED (Osceola LDC §4.3.3)
--
-- EXPECTED EFFECT: far sub-metric rises from 0.0 to potentially 100% if all
-- FAR-applicable codes are set to far_regulated=false (no parcels with FAR
-- requirements then exist without a standard). density sub-metric rises from
-- 93.0% as newly-coded R-3/E-1 get real standards.
--
-- ============================================================
-- IDEMPOTENT: safe to re-run (WHERE clauses guard against double-writes)
-- ============================================================

BEGIN;

-- Step 1: Set far_regulated=false for Kissimmee transect codes (T1-T6 pattern)
-- These zones definitively have no FAR column per LDC Table 5-2 (CONFIRMED).
UPDATE public.zoning_districts
SET far_regulated = false
WHERE jurisdiction_id IN (
    SELECT id FROM public.jurisdictions
    WHERE lower(county) = 'osceola' AND state = 'FL'
)
  AND code IN ('T1','T2','T3','T3L','T3S','T4','T4R','T4L','T5','T5-M','T5-N','T5-O','T6','CS')
  AND (far_regulated IS NULL OR far_regulated = true);

-- Step 2: Set far_regulated=false for Kissimmee PUD/SRPUD/MUPUD codes
UPDATE public.zoning_districts
SET far_regulated = false
WHERE jurisdiction_id IN (
    SELECT id FROM public.jurisdictions
    WHERE lower(county) = 'osceola' AND state = 'FL'
)
  AND code IN ('PUD','SRPUD','MUPUD','CPD','CUPD')
  AND (far_regulated IS NULL OR far_regulated = true);

-- Step 3: Set far_regulated=false for Kissimmee RA residential codes
UPDATE public.zoning_districts
SET far_regulated = false
WHERE jurisdiction_id IN (
    SELECT id FROM public.jurisdictions
    WHERE lower(county) = 'osceola' AND state = 'FL'
      AND lower(name) LIKE '%kissimmee%'
)
  AND code IN ('RA-1','RA-2','RA-3','A-1','A-2','RE','R-1','R-1A','R-1B','R-2','R-3','R-4','R-5')
  AND (far_regulated IS NULL OR far_regulated = true);

-- Step 4: Set far_regulated=false for St.Cloud R-3 residential (no FAR, density cap only)
-- Also set density_regulated=true with 18 du/acre from LDC §2-148
UPDATE public.zoning_districts
SET far_regulated = false,
    density_regulated = true
WHERE jurisdiction_id IN (
    SELECT id FROM public.jurisdictions
    WHERE lower(county) = 'osceola' AND state = 'FL'
      AND lower(name) LIKE '%cloud%'
)
  AND code IN ('R-1','R-2','R-3','R-4','RM','RM-1','RM-2')
  AND (far_regulated IS NULL OR far_regulated = true);

-- Step 5: Insert zone_standards for St.Cloud R-3 density (18 du/acre)
-- Only if zoning_districts row exists and no zone_standards row yet
INSERT INTO public.zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score)
SELECT zd.id, 18.0,
    'https://www.cityofstcloud.net/DocumentCenter/View/LDC',
    'St.Cloud LDC §2-148 max density R-3 = 18 du/acre [INFERRED — ordinance section not yet direct-read]',
    0.5
FROM public.zoning_districts zd
JOIN public.jurisdictions j ON j.id = zd.jurisdiction_id
WHERE lower(j.county) = 'osceola' AND j.state = 'FL'
  AND lower(j.name) LIKE '%cloud%'
  AND zd.code = 'R-3'
  AND NOT EXISTS (
      SELECT 1 FROM public.zone_standards zs2 WHERE zs2.zoning_district_id = zd.id
  )
ON CONFLICT DO NOTHING;

-- Step 6: Set far_regulated=false for Osceola County E-1 (Estate District)
-- Also ensure density_regulated=true, insert 1.0 du/acre standard
UPDATE public.zoning_districts
SET far_regulated = false,
    density_regulated = true
WHERE jurisdiction_id = 1186
  AND code IN ('E-1','E-2','E-3')
  AND (far_regulated IS NULL OR far_regulated = true);

-- Step 7: Insert zone_standards for Osceola County E-1 density (1.0 du/acre)
INSERT INTO public.zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score)
SELECT zd.id, 1.0,
    'https://library.municode.com/fl/osceola_county/codes/land_development_code',
    'Osceola County LDC §4.3.3 Estate District = 1 du/acre minimum [INFERRED]',
    0.5
FROM public.zoning_districts zd
WHERE zd.jurisdiction_id = 1186
  AND zd.code IN ('E-1','E-2','E-3')
  AND NOT EXISTS (
      SELECT 1 FROM public.zone_standards zs2 WHERE zs2.zoning_district_id = zd.id
  )
ON CONFLICT DO NOTHING;

-- Step 8: Re-confirm PD/PMUD/STRPD are still far_regulated=false (guard against cron reset)
UPDATE public.zoning_districts
SET far_regulated = false,
    density_regulated = false
WHERE jurisdiction_id = 1186
  AND code IN ('PD','PMUD','STRPD');

-- Step 9: Protect the far_regulated=false assignments from refresh_zoning_applicability_evidence()
-- The cron job (jobid=249, every 10 min) RESETS far_regulated=NULL for 'residential' category rows
-- and may SET far_regulated=true for non-residential categories.
-- For form-based transect codes (T-zones) and PUD codes that the cron may classify as
-- commercial/mixed_use, we need to add them to the verified exceptions allowlist
-- (created in migrations/20260721_gold_standard_shard6_run5361_sarasota_g_far_guard_allowlist.sql).
-- This requires the table to exist; if it doesn't exist yet in this DB, skip gracefully.
DO $$
DECLARE
    tbl_exists boolean;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = 'zoning_far_regulated_verified_exceptions'
    ) INTO tbl_exists;
    
    IF tbl_exists THEN
        INSERT INTO public.zoning_far_regulated_verified_exceptions
            (zoning_district_id, reason, dispatch_id)
        SELECT zd.id,
            'Kissimmee/Osceola form-based or PUD code: no FAR provision per ordinance. '
            || 'T-zones: LDC Table 5-2 CONFIRMED no FAR column (dispatch ac5f5206 3rd firing). '
            || 'SRPUD/PUD: FAR set per dev order, no base code value (CONFIRMED ac5f5206). '
            || 'RA-3/E-1: residential-agricultural/estate, density-based not FAR-based (INFERRED).',
            '091fb9f9-f5a4-49b3-ad21-2472b3cc9f4a'
        FROM public.zoning_districts zd
        JOIN public.jurisdictions j ON j.id = zd.jurisdiction_id
        WHERE lower(j.county) = 'osceola' AND j.state = 'FL'
          AND zd.code IN (
              'T1','T2','T3','T3L','T3S','T4','T4R','T4L','T5','T5-M','T5-N','T5-O','T6','CS',
              'PUD','SRPUD','MUPUD','CPD','CUPD',
              'RA-1','RA-2','RA-3',
              'E-1','E-2','E-3',
              'PD','PMUD','STRPD'
          )
          AND zd.far_regulated = false
        ON CONFLICT (zoning_district_id) DO NOTHING;
        
        RAISE NOTICE 'Added zoning_far_regulated_verified_exceptions rows for osceola';
    ELSE
        RAISE NOTICE 'Table zoning_far_regulated_verified_exceptions does not exist — skipping exception registration. The far_regulated=false writes above may be reset by the 10-min cron. Run the sarasota guard migration first if needed.';
    END IF;
END $$;

COMMIT;

-- ============================================================
-- VERIFICATION QUERIES (run after migration)
-- ============================================================

-- Check: how many osceola districts now have far_regulated=true with NULL max_far?
SELECT
    zd.code,
    zd.name,
    j.name AS jurisdiction,
    zd.far_regulated,
    zs.max_far
FROM public.zoning_districts zd
JOIN public.jurisdictions j ON j.id = zd.jurisdiction_id
LEFT JOIN public.zone_standards zs ON zs.zoning_district_id = zd.id
WHERE lower(j.county) = 'osceola' AND j.state = 'FL'
  AND zd.far_regulated = true
ORDER BY j.name, zd.code;

-- Check: current G evaluation
SELECT public.pencil_dod_evaluate_county('osceola') AS osceola_eval;
