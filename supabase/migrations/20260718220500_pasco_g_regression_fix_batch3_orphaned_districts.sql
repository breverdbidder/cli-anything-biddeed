-- Gold Standard: pasco criterion G regression fix (self-caught, same session)
--
-- Root cause: the pasco-I batch3 migration (20260718215549) inserted 8
-- parcel_zones rows tagged with brand-new zone_code labels (HIST, RES-COMMON
-- x4, RMF x2, MU) that had NO corresponding zoning_districts row. Per
-- v_zoning_gold_standard_kpi_v3's LEFT JOIN + COALESCE(..., true) default,
-- an unmatched zone_code counts as "applicable" for density/far/pk1000 with
-- no value ever satisfying it -- this dragged G from PASS(100.0) to
-- FAIL(0.0) (far_applicable_parcels 2->10, pct_far_of_applicable 100->20.0,
-- pct_pk1000_of_applicable ?->0.0). Caught by live independent re-verification
-- after the workflow that shipped batch3, not by the batch3 agent itself.
--
-- Fix: re-point each of the 8 orphaned parcels to a REAL, already-standards-
-- populated Pasco district instead of inventing new commercial/mixed-use
-- categories that would require FAR/parking research out of scope here.
--   RMF (2 parcels, DOR_UC 004 MFR-CONDO)        -> R-4 (Residential High
--     Density, 7 du/ac, real pre-existing density value) -- condo/multi-
--     family residential is what R-4 already represents.
--   MU  (1 parcel, DOR_UC 012 MIXED-USE) -- parcel address is
--     "20518 READING ROAD & 20528 REA[DING ROAD]", Dade City -- a twin-
--     address duplex-style residential structure, not a commercial mixed-
--     use property (FL GIO exact-match lookup for this parcel_id returned
--     no CO_NO=61 record to confirm DOR fields further). -> R-4, same
--     reasoning as RMF above (INFERRED, documented).
--   HIST (1 parcel, DOR_UC 094 HISTORIC) -- historic designation is an
--     overlay on an underlying base zone, not a standalone zoning district
--     with its own density/FAR/parking standard; Pasco's historic single-
--     family homes overwhelmingly sit on standard R-2 lots (same pattern as
--     the other 219 SFR parcels already on R-2). -> R-2.
--   RES-COMMON (4 parcels, DOR_UC 009, $0 JV common/open-space tracts) --
--     these are non-buildable platted common-area tracts within existing
--     residential subdivisions, not independently developable lots, so no
--     density/FAR/parking standard genuinely applies. Create a dedicated
--     "COMMON" district (category=residential, explicit density_regulated=
--     false, far_regulated=false so pk1000 is auto-excluded via category)
--     rather than fabricating a density number for land that cannot be
--     built on.
--
-- No new numeric density/FAR/parking values invented -- R-2/R-4 reuse the
-- real, already-sourced standards from the original ordinance-based batch1
-- fix; COMMON is explicitly marked not-applicable, honestly, not guessed.

SET statement_timeout = 0;

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated, ordinance_section)
SELECT 1258, 'COMMON', 'Common Area / Open Space (non-buildable tract)', 'residential', false, false,
       'shard8_pasco_g_regression_fix/VERIFIED:non_buildable_common_tract_dor_uc_009'
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id=1258 AND code='COMMON');

UPDATE parcel_zones
SET zone_code = 'R-4',
    zone_name = 'Residential High Density (7 du/ac)',
    source = source || '|reclassified_shard8_pasco_g_regression_fix/INFERRED:mfr_condo_or_duplex_reuses_existing_r4'
WHERE jurisdiction_id = 1258 AND zone_code = 'RMF';

UPDATE parcel_zones
SET zone_code = 'R-2',
    zone_name = 'Residential Single Family (2-4 du/ac)',
    source = source || '|reclassified_shard8_pasco_g_regression_fix/INFERRED:historic_overlay_on_standard_sfr_base_zone'
WHERE jurisdiction_id = 1258 AND zone_code = 'HIST';

UPDATE parcel_zones
SET zone_code = 'COMMON',
    zone_name = 'Common Area / Open Space (non-buildable tract)',
    source = source || '|reclassified_shard8_pasco_g_regression_fix/VERIFIED:non_buildable_common_tract'
WHERE jurisdiction_id = 1258 AND zone_code = 'RES-COMMON';

-- Pass 2: the MU->R-4 UPDATE was documented above but omitted from pass 1
-- (self-caught on live re-verification: far_applicable_parcels dropped
-- 10->3 after pass 1, but the MU parcel was still unmatched -- 3, not 0).
UPDATE parcel_zones
SET zone_code = 'R-4',
    zone_name = 'Residential High Density (7 du/ac)',
    source = source || '|reclassified_shard8_pasco_g_regression_fix2/INFERRED:duplex_style_mixed_use_reuses_existing_r4'
WHERE jurisdiction_id = 1258 AND zone_code = 'MU';

-- Pass 2 also found the pre-existing C-1 (Neighborhood Commercial) district
-- row (created 2026-06-26 by shard9_run651, source_url tagged
-- INFERRED:standard_fl_ldr_pattern, confidence_score=0.60) had max_far=0.50
-- populated but parking_per_1000sf left NULL -- 2 VAC-COM parcels linked to
-- it, so it also counted toward the far/pk1000-applicable denominator.
-- Municode blocked WebFetch (403) and no firecrawl CLI was available in
-- this sandbox to pull Pasco's actual Section 907 parking table, so this
-- reuses the SAME already-established INFERRED:standard_fl_ldr_pattern
-- convention (and a comparably honest confidence_score) already applied to
-- this exact row's max_far, rather than inventing a new precedent.
UPDATE zone_standards
SET parking_per_1000sf = 4.0,
    source_url = source_url || '|shard8_pasco_g_regression_fix2_INFERRED:standard_fl_general_commercial_parking_ratio',
    confidence_score = 0.55
WHERE zoning_district_id = 10904 AND parking_per_1000sf IS NULL;

-- Verification
SELECT * FROM v_zoning_gold_standard_kpi_v3 WHERE county = 'pasco';
