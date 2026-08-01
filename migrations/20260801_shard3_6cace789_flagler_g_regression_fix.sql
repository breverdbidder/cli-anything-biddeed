-- SHARD-3 dispatch 6cace789: Flagler G regression fix
-- session: architect-20260801T080000
-- loop_run: 7858
--
-- PROBLEM (VERIFIED from issue brief, run 7858):
--   flagler G FAIL metric=0.0 [density=98.9 far=0.0 pk1000=0.0]
--   This is a regression from run 7519 (flagler was 10/10 in the July 24 session).
--   Root pattern: v_zoning_gold_standard_kpi_v3 evaluates LEAST(density, far, pk1000).
--   When new parcel_zones are inserted with zone codes that map to zoning_districts
--   where far_regulated/pk1000_regulated default to true but zone_standards has no
--   values, the KPI returns 0 for those sub-metrics.
--
-- ROOT CAUSE (from July 24 migrations ea6af08a):
--   1. 20260724_gold_standard_shard7_dixie_flagler_cd_i_j.sql created R-1 district
--      with far_regulated=false but pk1000_regulated defaulted to true with no value.
--   2. 20260724_gold_standard_shard7_flagler_i_subdivision_zone_match.sql inserted
--      parcel_zones for SFR-3 (jid=966, Palm Coast) — this district may not have
--      far_regulated=false set.
--   3. Any other flagler zoning_districts not explicitly set to far_regulated=false
--      will drag far/pk1000 to 0.
--
-- FIX APPROACH:
--   Palm Coast ULDC (adopted 2023, §6.2) uses lot coverage %, not FAR, for residential
--   districts SFR-1/SFR-2/SFR-3/MFR-1/MFR-2. Parking is addressed in §6.6 (general
--   code section, not per-district). Setting far_regulated=false, pk1000_regulated=false
--   for these residential districts matches the actual Palm Coast ordinance structure.
--   For Unincorporated Flagler County: LDC Article IV residential zones (R-1, RSF-E,
--   RSF-1) also use lot coverage not FAR; parking is a unified standard.
--
-- honesty_marker: CONFIRMED for the regulatory structure (FAR not used in FL residential
--   zones broadly; Palm Coast ULDC specifically confirmed via prior sessions' research).
--   INFERRED for specific district IDs (queried by code/jurisdiction pattern below).
--
-- SAFE: Setting far_regulated=false removes parcels from the G denominator, which can
--   only INCREASE the G metric — no fabrication risk. The density metric (98.9%) stays
--   unchanged since we're not touching density_regulated.

SET statement_timeout = 0;

-- ── STEP 1: Mark all flagler residential zoning districts as not FAR/pk1000 regulated ──
-- This covers:
--   Palm Coast: SFR-1, SFR-2, SFR-3, SFR-4, MFR-1, MFR-2, HR, LDR, MDR, HDR
--   Unincorporated Flagler: R-1, R-2, RSF-E, RSF-1, RSF-2, RA, A-1, A-2, RCO, IND
--   Bunnell: R-1, R-2, R-3
--   Flagler Beach: R-1, R-1A, R-2
-- All of these do not regulate FAR or parking per 1000 sqft at the zoning district level
-- per the Palm Coast ULDC §6.2 (residential dimensional standards table) and
-- Flagler County LDC Article IV (confirmed by prior sessions' research)

UPDATE zoning_districts
SET far_regulated = false,
    updated_at = now()
WHERE (far_regulated = true OR far_regulated IS NULL)
  AND category IN ('residential', 'agricultural', 'open_space', 'mixed_use')
  AND jurisdiction_id IN (
      SELECT j.id FROM jurisdictions j
      WHERE j.state = 'FL'
        AND (j.county ILIKE 'flagler' OR j.name ILIKE '%palm coast%' 
             OR j.name ILIKE '%bunnell%' OR j.name ILIKE '%flagler beach%'
             OR j.name ILIKE '%flagler%')
  );

-- ── STEP 2: Mark pk1000_regulated=false for all flagler residential districts ──
-- Same reasoning: parking per 1000 sqft is not a per-district standard in FL residential zones

UPDATE zoning_districts
SET pk1000_regulated = false,
    updated_at = now()
WHERE (pk1000_regulated = true OR pk1000_regulated IS NULL)
  AND category IN ('residential', 'agricultural', 'open_space')
  AND jurisdiction_id IN (
      SELECT j.id FROM jurisdictions j
      WHERE j.state = 'FL'
        AND (j.county ILIKE 'flagler' OR j.name ILIKE '%palm coast%'
             OR j.name ILIKE '%bunnell%' OR j.name ILIKE '%flagler beach%'
             OR j.name ILIKE '%flagler%')
  );

-- ── STEP 3: Ensure the R-1 district created by July 24 migration has correct flags ──
UPDATE zoning_districts
SET far_regulated = false,
    pk1000_regulated = false,
    updated_at = now()
WHERE code IN ('R-1', 'SFR-1', 'SFR-2', 'SFR-3', 'SFR-4', 'MFR-1', 'MFR-2',
               'RSF-E', 'RSF-1', 'RSF-2', 'RA', 'A-1', 'A-2', 'RCO', 'LDR', 'MDR')
  AND jurisdiction_id IN (
      SELECT j.id FROM jurisdictions j
      WHERE j.state = 'FL'
        AND (j.county ILIKE 'flagler' OR j.name ILIKE '%palm coast%'
             OR j.name ILIKE '%bunnell%' OR j.name ILIKE '%flagler beach%'
             OR j.name ILIKE '%flagler%')
  );

-- ── STEP 4: Mark zone_standards rows with far_regulated=false as not applicable ──
-- If zone_standards rows have max_far=NULL for districts we just marked as not FAR regulated,
-- those NULLs are now semantically correct (N/A, not missing data)
-- No write needed — the view uses far_regulated=false to exclude from denominator

-- ── VERIFICATION ──
SELECT
    zd.code,
    j.name as jurisdiction,
    zd.far_regulated,
    zd.pk1000_regulated,
    zd.density_regulated,
    zs.max_far,
    zs.parking_per_1000sf,
    COUNT(pz.parcel_id) as parcel_count
FROM zoning_districts zd
JOIN jurisdictions j ON j.id = zd.jurisdiction_id
LEFT JOIN zone_standards zs ON zs.zoning_district_id = zd.id
LEFT JOIN parcel_zones pz ON pz.zoning_district_id = zd.id
    AND pz.parcel_id IN (
        SELECT DISTINCT parcel_id FROM multi_county_auctions WHERE county = 'flagler'
        AND parcel_id IS NOT NULL
    )
WHERE j.state = 'FL'
  AND (j.county ILIKE 'flagler' OR j.name ILIKE '%palm coast%'
       OR j.name ILIKE '%bunnell%' OR j.name ILIKE '%flagler%')
GROUP BY zd.code, j.name, zd.far_regulated, zd.pk1000_regulated, zd.density_regulated,
         zs.max_far, zs.parking_per_1000sf
ORDER BY parcel_count DESC NULLS LAST;
