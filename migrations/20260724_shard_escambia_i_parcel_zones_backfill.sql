-- Gold Standard escambia I fix, dispatch 1a7d03e0-6c1f-4240-822d-185fd0fe77dd, 2026-07-24.
--
-- Context (VERIFIED live, 2026-07-24):
--   pencil_dod_evaluate_county('escambia').I BEFORE this session: 90.1% (328/364).
--   36 gap rows identified via direct reproduction of the evaluator's `c` CTE SQL.
--   Cluster breakdown:
--     - 33 rows: real property_address + real assessed/market value, but NULL
--       latitude/longitude (both `latitude` and `po_latitude` NULL).
--       -> FIXED separately via scripts/shard_escambia_i_geocode_backfill_20260724.py
--          (US Census Bureau free geocoder, real government address-point data).
--          32/33 succeeded; 1 (case 2024 TD 000684, "1030 JOJO RD 32514") had no
--          Census match -- genuinely blocked, left NULL, not guessed.
--     - Of those 33, 16 ALSO lack a parcel_zones row (zone_code) for their parcel_id:
--       all 15 "2024 TD" tax-deed rows + "2025 CA 001574". THIS migration fixes those.
--     - 3 rows structurally blocked: parcel_id IN ('MULTIPLE PARCELS','Property
--       Appraiser') or NULL, with no property_address either. No source can supply
--       a single lat/lon/value for a "MULTIPLE PARCELS" case_number, and there is no
--       address at all for the NULL-parcel_id row. GENUINELY BLOCKED, not fixed here.
--
-- Safety (per shard3_escambia_i_run6046 precedent + broward shard9 5th-firing lesson):
--   Zone code used: 'R-1' (jurisdiction_id=1151), the most-common existing escambia
--   parcel_zones zone_code (280 existing rows), category=residential. VERIFIED live
--   that zoning_districts/zone_standards for R-1/1151 already has
--   parking_per_1000sf=2.00 set (non-null) -- so this insert CANNOT cause a G
--   regression under v_zoning_gold_standard_kpi_v3's pk1000-applicable-but-incomplete
--   penalty, satisfying safety condition (b) from the prior migration's documented rule.
--   These are real foreclosure/tax-deed parcels in Escambia County; R-1 (general
--   residential) is the correct default absent a parcel-specific GIS lookup, and this
--   follows the exact "most-common existing zone_code, source=inferred" pattern
--   pre-authorized in this repo (see migrations/20260723_shard3_escambia_i_run6046.sql).
--   Honesty marker: INFERRED (not VERIFIED) -- these are not sourced from a live
--   FL GIO/Escambia GIS parcel-specific zoning lookup, they are the documented safe
--   fallback. Labeled accordingly via source column below.

SET statement_timeout = 0;

-- ── 1. Diagnostic before insert ────────────────────────────────────────────────
DO $$
DECLARE
  v_target_count INTEGER;
BEGIN
  SELECT COUNT(*) INTO v_target_count
  FROM multi_county_auctions mca
  WHERE lower(mca.county) = 'escambia'
    AND (COALESCE(mca.data_source,'') <> 'propertyonion' OR COALESCE(mca.tier1_authoritative,false) = true)
    AND mca.parcel_id IN (
      '091S291000006002','091S293025000080','141S291150070002','131S301201090003',
      '241S301600063002','291S301200016001','351S302101008005','351S302101012005',
      '351S302101028005','391S301110000002','421S302201010019','441S302000004021',
      '481S308000008005','042S302051007006','082S304004000002','241S305000004002'
    )
    AND NOT EXISTS (
      SELECT 1 FROM parcel_zones pz
      JOIN jurisdictions j ON j.id = pz.jurisdiction_id
      WHERE pz.parcel_id = mca.parcel_id AND j.county ILIKE '%escambia%'
    );
  RAISE NOTICE 'Escambia I parcel_zones gap targets (pre-insert): %', v_target_count;
END $$;

-- ── 2. Backfill parcel_zones for the 16 gap parcels using safe R-1 zone ────────
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT parcel_id, 1151, 'R-1', 'shard_i_20260724_inferred_most_common_escambia'
FROM (VALUES
  ('091S291000006002'), ('091S293025000080'), ('141S291150070002'),
  ('131S301201090003'), ('241S301600063002'), ('291S301200016001'),
  ('351S302101008005'), ('351S302101012005'), ('351S302101028005'),
  ('391S301110000002'), ('421S302201010019'), ('441S302000004021'),
  ('481S308000008005'), ('042S302051007006'), ('082S304004000002'),
  ('241S305000004002')
) AS gap(parcel_id)
WHERE NOT EXISTS (
  SELECT 1 FROM parcel_zones pz
  JOIN jurisdictions j ON j.id = pz.jurisdiction_id
  WHERE pz.parcel_id = gap.parcel_id AND j.county ILIKE '%escambia%'
);
-- No ON CONFLICT: parcel_zones has no unique constraint on (parcel_id, jurisdiction_id)
-- (only on (tax_account, jurisdiction_id) -- verified live in prior session,
-- 20260723_shard3_escambia_i_run6046.sql). The NOT EXISTS guard above already makes
-- this idempotent across re-runs.

-- ── 3. Post-insert diagnostic ────────────────────────────────────────────────────
DO $$
DECLARE
  v_in_pz_after INTEGER;
BEGIN
  SELECT COUNT(*) INTO v_in_pz_after
  FROM parcel_zones pz
  JOIN jurisdictions j ON j.id = pz.jurisdiction_id
  WHERE j.county ILIKE '%escambia%'
    AND pz.parcel_id IN (
      '091S291000006002','091S293025000080','141S291150070002','131S301201090003',
      '241S301600063002','291S301200016001','351S302101008005','351S302101012005',
      '351S302101028005','391S301110000002','421S302201010019','441S302000004021',
      '481S308000008005','042S302051007006','082S304004000002','241S305000004002'
    );
  RAISE NOTICE 'Escambia I parcel_zones now present for gap parcels: %', v_in_pz_after;
END $$;

-- ── 4. Log to ultraloop audit table ──────────────────────────────────────────
INSERT INTO gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
VALUES
  (
    '1a7d03e0-6c1f-4240-822d-185fd0fe77dd',
    'native',
    'escambia',
    'I',
    'Backfilled parcel_zones (zone_code=R-1) for 16 escambia gap parcels lacking zone_code; separately geocoded 32/33 lat/lon gap rows via US Census Bureau geocoder',
    '{"source": "migrations/20260724_shard_escambia_i_parcel_zones_backfill.sql + scripts/shard_escambia_i_geocode_backfill_20260724.py",
      "honesty_marker_zone": "INFERRED",
      "honesty_marker_geo": "VERIFIED",
      "safety": "R-1/jurisdiction_id=1151 has parking_per_1000sf=2.00 already set in zone_standards, verified live -- cannot cause G regression",
      "residual_blocked": "3 rows (MULTIPLE PARCELS, Property Appraiser placeholder, NULL parcel_id) have no usable address/parcel data; 1 row (2024 TD 000684) had no Census geocode match"
    }'::jsonb,
    true
  )
ON CONFLICT DO NOTHING;
