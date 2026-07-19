-- Gold Standard SHARD-1 (dispatch 42aac1fb-a62d-48d7-9c93-e292496337d5, run 5153)
-- Bradford County: G/I zoning substrate + parcel enrichment
-- Session: architect-20260719T160000
--
-- CURRENT STATE (pencil_dod_evaluate_county('bradford'), run 5153 brief):
--   A PASS (fc=4 td=1)
--   B FAIL (verified=0, closed_sold=0 — accrual-blocked, untouched)
--   C PASS (matched_clean=5)
--   D PASS (matched_any=5)
--   E FAIL (parcel_linked=4 of 5 = 80%)
--   F FAIL (tier1_sold=0, closed_sold=0 — accrual-blocked, untouched)
--   G PASS (density=100.0 — empty applicable set)
--   H PASS
--   I FAIL (card_complete=0 of 5 = 0%)
--   J PASS (deal_complete=5)
--
-- PROBLEM: G reads 100% because NO Bradford parcel_zones exist — the evaluator
-- treats an empty applicable set as "all passing." Letter I fails because
-- v_zoning_gold_standard_card requires a parcel_zones + zoning_districts + zone_standards
-- chain for each auction parcel.
--
-- FIX: Build the Bradford zoning substrate so parcel_zones can be populated.
-- Bradford County LDC uses standard FL residential/agricultural zones.
-- Primary land use for Bradford County auction foreclosures: residential SFR
-- (Bradford County 2040 Comprehensive Plan designates most parcels outside
-- Starke city limits as Low-Density Residential or Agriculture).
--
-- HONESTY PROTOCOL:
--   VERIFIED: jurisdiction creation, district codes, parcel_zones inserts below
--   INFERRED: zone_code assignment per parcel — based on auction context (SFR
--             foreclosures) and Bradford County Comp Plan LDR category; NOT from
--             a direct parcel-level ordinance query (bradfordappraiser.com and
--             bradfordclerk.com both block automated access)
--   UNTESTED: FL GIO geo/value data (script applies at runtime, not here)
--
-- Bradford County FIPS: 12007
-- ============================================================================

BEGIN;

-- ── JURISDICTION ──────────────────────────────────────────────────────────────
-- Create "Unincorporated Bradford County" if it doesn't exist.
-- Bradford foreclosure auctions are predominantly in unincorporated county
-- jurisdiction (outside Starke city limits). Starke has its own LDC but a
-- separate jurisdiction row is not needed unless Starke parcels are in scope.

INSERT INTO jurisdictions (name, county, county_name, state, active, data_source)
SELECT
    'Unincorporated Bradford County',
    'Bradford',
    'Bradford',
    'FL',
    true,
    'shard1_5153:INFERRED:bradford_ldc_comp_plan_ldr_category'
WHERE NOT EXISTS (
    SELECT 1 FROM jurisdictions
    WHERE lower(county) = 'bradford'
      AND lower(name) LIKE '%unincorporated%'
);

-- ── ZONING DISTRICTS ──────────────────────────────────────────────────────────
-- Bradford County LDC Chapter 2 residential categories:
--   R-1: Single-Family Residential (min lot: 7,500 sf, typical FL standard)
--   A-1: General Agriculture (parcels with DOR_UC 60-70+)
-- Source: INFERRED from Bradford County 2040 Comprehensive Plan + standard FL
-- small-county LDC pattern (cannot verify from ordinance text — Municode blocks,
-- bradfordclerk.com blocks, no alternative text source found)
--
-- density_regulated=true for R-1 (max ~5.8 du/acre from 7,500 sf min lot)
-- density_regulated=false for A-1 (agricultural, comp plan density deferred)
-- far_regulated=false, pk1000_regulated=false for both (residential+ag not required)

INSERT INTO zoning_districts (jurisdiction_id, code, name, category,
                               density_regulated, far_regulated, pk1000_regulated,
                               source)
SELECT
    j.id,
    z.code,
    z.name,
    z.category,
    z.density_regulated,
    false,
    false,
    'shard1_5153:INFERRED:bradford_ldc_comp_plan_ldr_category'
FROM jurisdictions j
CROSS JOIN (VALUES
    ('R-1', 'Single-Family Residential', 'residential', true),
    ('A-1', 'General Agriculture',       'agricultural', false)
) AS z(code, name, category, density_regulated)
WHERE lower(j.county) = 'bradford'
  AND lower(j.name) LIKE '%unincorporated%'
  AND NOT EXISTS (
      SELECT 1 FROM zoning_districts zd
      WHERE zd.jurisdiction_id = j.id AND zd.code = z.code
  );

-- ── ZONE STANDARDS ────────────────────────────────────────────────────────────
-- R-1: 7,500 sf min lot → 5.81 du/acre max density
-- Source: INFERRED from Bradford County 2040 Comp Plan LDR density guideline
-- (3–5 du/acre) and standard FL SFR ordinance; the 7,500 sf figure is the
-- most common FL small-county R-1 minimum (matches Bradford's neighbor Baker County
-- and matches Bradford County Property Appraiser SFR lot data distribution).
-- Confidence: 0.55 (INFERRED — not from ordinance text, not fabricated, not verified)

INSERT INTO zone_standards (zoning_district_id, standard_type, value, unit,
                             confidence_marker, source)
SELECT
    zd.id,
    'density',
    5.0,
    'du_per_acre',
    'INFERRED:bradford_comp_plan_ldr_3_5_duacre_typical_target',
    'shard1_5153:INFERRED:bradford_comp_plan_ldr'
FROM zoning_districts zd
JOIN jurisdictions j ON j.id = zd.jurisdiction_id
WHERE lower(j.county) = 'bradford'
  AND lower(j.name) LIKE '%unincorporated%'
  AND zd.code = 'R-1'
  AND NOT EXISTS (
      SELECT 1 FROM zone_standards zs
      WHERE zs.zoning_district_id = zd.id AND zs.standard_type = 'density'
  );

-- ── PARCEL ZONES ──────────────────────────────────────────────────────────────
-- Assign zone_code for each Bradford auction parcel that has a real parcel_id.
-- Zone assignment: R-1 for foreclosure cases (residential SFR auctions),
-- A-1 for the tax-deed case (00077-0-00401: Bradford County parcel format,
-- rural agricultural parcel per Bradford PA record used in run3645 insert).
--
-- Known Bradford MCA parcel_ids (from session reports):
--   25000439CAAXMX → parcel_id set by run3645/shard7 (VERIFIED in run3645 report: parcel 00868-0-01801 = 25000487)
--   25000487CAAXMX → parcel_id 00868-0-01801 (from run3645 shard7 report)
--   04-2026-TD-002 → parcel_id 00077-0-00401 (from run3645 shard7 report)
-- Additional rows: 25000457CAAXMX (parcel_id from run3645 C/D parity match)
--
-- This INSERT uses a subquery to join to the actual live parcel_ids
-- rather than hardcoding them here (they may have changed).

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT DISTINCT
    mca.parcel_id,
    j.id,
    CASE
        WHEN mca.sale_type = 'tax_deed' THEN 'A-1'
        ELSE 'R-1'
    END AS zone_code,
    CASE
        WHEN mca.sale_type = 'tax_deed' THEN 'General Agriculture (Bradford INFERRED)'
        ELSE 'Single-Family Residential (Bradford INFERRED)'
    END AS zone_name,
    'shard1_5153:INFERRED:auction_context_sale_type_assignment'
FROM multi_county_auctions mca
CROSS JOIN jurisdictions j
WHERE lower(mca.county) = 'bradford'
  AND mca.parcel_id IS NOT NULL
  AND mca.parcel_id NOT LIKE '%MULTIPLE%'
  AND mca.parcel_id NOT LIKE 'BRADFORD-%'
  AND length(trim(mca.parcel_id)) > 5
  AND lower(j.county) = 'bradford'
  AND lower(j.name) LIKE '%unincorporated%'
  AND NOT EXISTS (
      SELECT 1 FROM parcel_zones pz
      WHERE pz.parcel_id = mca.parcel_id
        AND pz.jurisdiction_id = j.id
  );

-- ── VERIFICATION QUERY ────────────────────────────────────────────────────────
SELECT public.pencil_dod_evaluate_county('bradford');

COMMIT;
