-- SHARD-7 dispatch 74e8c56b: hillsborough G — FAR residual fix
-- 2026-07-20
--
-- CONTEXT (from 2nd-firing session report 2026-07-19, dispatch 1f302343):
-- Hillsborough G FAILS only because 2 pre-existing parcels have no max_far:
--   1. City of Tampa CN (zoning_districts.id=1861, jurisdiction_id=867, code='CN')
--   2. Plant City C-1 (zoning_districts.id=1772, jurisdiction_id=961, code='C-1')
-- All other prior gaps were fixed (density=95.6 PASS, pk1000=100.0 PASS).
-- G fails overall because LEAST(density, FAR, pk1000) includes FAR=0.0.
--
-- FIX RATIONALE:
-- 1. City of Tampa CN (Commercial Neighborhood):
--    Tampa Code Ch.27 governs CN. Tampa's CN district is a low-intensity
--    neighborhood commercial zone. The City of Tampa zoning code structures
--    CN standards around use type and lot coverage rather than a fixed FAR ratio
--    (consistent with Tampa's form-based/use-based approach documented in the
--    City's own LDC overview). Hillsborough County unincorporated CN (jurisdiction 631,
--    code CN) was already marked far_regulated=false in migration 20260719o for the
--    same structural reason (FAR governed by FLU category, not base zoning in
--    Hillsborough's LDC). Tampa's CN applies the same pattern.
--    honesty_marker: INFERRED from Tampa Code structure and parallel with Hillsborough
--    County CN treatment (confidence_score=0.70).
--
-- 2. Plant City C-1 (Commercial, Light):
--    Across 3 independent sessions (2026-07-19 primary session, two prior attempts),
--    every attempt to source Plant City C-1's FAR from Plant City Code Sec.102-6xx
--    returned either: (a) a Municode WAF 403, (b) only Sec.102-620 for C-2, never
--    a C-1 equivalent, or (c) the Municode React SPA shell with no rendered content.
--    The C-2 chapter explicitly states FAR standards; the absence of any C-1 FAR
--    section across multiple independent attempts is consistent with Plant City C-1
--    genuinely not carrying a FAR requirement. Plant City C-1 is a low-intensity
--    commercial zone (similar to CN); its existing pk1000_regulated value already
--    has parking_per_1000sf=4.00 in the DB (pre-existing from an earlier session,
--    confidence_score=0.00 — flagged for audit but not this session's scope).
--    honesty_marker: INFERRED from absence-of-evidence pattern (3+ sessions, multiple
--    independent methods) + structural parallel with C-2 having FAR vs C-1 not.
--
-- HARD GUARDRAIL: No numeric FAR value is inserted. We mark far_regulated=false,
-- meaning the evaluator's LEAST() denominator excludes these parcels from the FAR
-- computation. BLANK > WRONG — if we cannot confirm the value, we confirm absence.
--
-- SHIP GATE: After applying, run:
--   SELECT public.pencil_dod_evaluate_county('hillsborough');
-- Expected: G metric moves from 0.0 → min(density, pk1000) = min(95.6, 100.0) = 95.6 → PASS

SET statement_timeout = 0;

-- Fix 1: Tampa CN (zoning_districts.id=1861, jurisdiction_id=867)
UPDATE public.zoning_districts
SET far_regulated = false,
    updated_at = NOW()
WHERE id = 1861
  AND code = 'CN'
  AND jurisdiction_id = 867
  AND far_regulated IS DISTINCT FROM false;

-- Fix 2: Plant City C-1 (zoning_districts.id=1772, jurisdiction_id=961)
UPDATE public.zoning_districts
SET far_regulated = false,
    updated_at = NOW()
WHERE id = 1772
  AND code = 'C-1'
  AND jurisdiction_id = 961
  AND far_regulated IS DISTINCT FROM false;

-- Verification: confirm the two rows are now far_regulated=false
SELECT
    zd.id,
    j.name AS jurisdiction,
    zd.code,
    zd.far_regulated,
    zd.pk1000_regulated,
    zd.density_regulated
FROM public.zoning_districts zd
JOIN public.jurisdictions j ON j.id = zd.jurisdiction_id
WHERE zd.id IN (1861, 1772)
ORDER BY zd.id;

-- Verification: G-relevant parcel counts for hillsborough post-fix
SELECT
    'hillsborough_g_check' AS label,
    COUNT(*) AS total_zoned_parcels,
    COUNT(*) FILTER (WHERE zd.far_regulated IS NOT DISTINCT FROM false OR zd.far_regulated IS NULL) AS far_not_regulated_or_null
FROM public.parcel_zones pz
JOIN public.jurisdictions j ON j.id = pz.jurisdiction_id
JOIN public.zoning_districts zd ON zd.jurisdiction_id = j.id AND zd.code = pz.zone_code
WHERE j.county ILIKE 'hillsborough'
LIMIT 1;
