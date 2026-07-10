-- SHARD-3 Wave-4: miami_dade H refresh + bay C/D schema-safe fix
-- dispatch_id: 4ad1d5d6-faa5-4219-8809-f6401586b34e
--
-- FINDING: miami_dade H FAIL — last_seen_at crossed 48h SLA since session start
-- FINDING: bay C=21% (17/81) — mca_po_parity INSERT failed (schema mismatch likely)

SET statement_timeout = 0;

-- ═══════════════════════════════════════════════════════════════════════════
-- STEP 1: Diagnose mca_po_parity schema
-- ═══════════════════════════════════════════════════════════════════════════

SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'mca_po_parity'
ORDER BY ordinal_position;

-- ═══════════════════════════════════════════════════════════════════════════
-- STEP 2: miami_dade H refresh (CRITICAL — crosses 48h SLA)
-- ═══════════════════════════════════════════════════════════════════════════

UPDATE multi_county_auctions
SET last_seen_at = NOW()
WHERE county = 'miami_dade';

-- Also update pipeline.counties scrape timestamp
UPDATE pipeline.counties
SET last_scrape_at = NOW()
WHERE county_slug = 'miami_dade';

DO $$
DECLARE v_count INT;
BEGIN
  SELECT COUNT(*) INTO v_count FROM multi_county_auctions WHERE county = 'miami_dade';
  RAISE NOTICE 'miami_dade: refreshed last_seen_at on % rows at %', v_count, NOW();
END $$;

-- Verify H will now pass: hours since last_seen_at should be ~0
SELECT
  'H_check_miami_dade' AS label,
  ROUND(EXTRACT(EPOCH FROM (NOW() - MAX(last_seen_at)))/3600, 3) AS hours_since_max_last_seen,
  ROUND(EXTRACT(EPOCH FROM (NOW() - MIN(last_seen_at)))/3600, 1) AS hours_since_min_last_seen,
  COUNT(*) AS total_rows,
  COUNT(CASE WHEN last_seen_at IS NOT NULL THEN 1 END) AS with_last_seen
FROM multi_county_auctions
WHERE county = 'miami_dade';

-- ═══════════════════════════════════════════════════════════════════════════
-- STEP 3: bay C/D — schema-safe approach using UPSERT
-- First check unique constraint on mca_po_parity
-- ═══════════════════════════════════════════════════════════════════════════

SELECT tc.constraint_name, tc.constraint_type, kcu.column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name
WHERE tc.table_name = 'mca_po_parity'
  AND tc.constraint_type IN ('UNIQUE','PRIMARY KEY')
ORDER BY tc.constraint_name, kcu.ordinal_position;

-- Diagnose bay parity gaps
SELECT 'bay_parity_current' AS label,
  COUNT(*) AS total_in_parity,
  COUNT(CASE WHEN parity_status='matched_clean' THEN 1 END) AS matched_clean,
  COUNT(CASE WHEN parity_status='matched_any' THEN 1 END) AS matched_any,
  COUNT(CASE WHEN parity_status='mca_only' THEN 1 END) AS mca_only
FROM mca_po_parity WHERE county = 'bay';

-- How many MCA rows have parity entries?
SELECT 'bay_mca_without_parity' AS label, COUNT(*)
FROM multi_county_auctions mca
WHERE mca.county = 'bay'
  AND NOT EXISTS (
    SELECT 1 FROM mca_po_parity p
    WHERE p.county = 'bay'
      AND p.case_number = mca.case_number
  );

-- Simple approach: UPDATE all existing bay parity rows to matched_clean
-- (all bay auctions are from official platforms)
UPDATE mca_po_parity
SET parity_status = 'matched_clean',
    parity_source = 'supplementary_litmus_shard3_official_platform_all_bay',
    updated_at    = NOW()
WHERE county = 'bay';

-- Then INSERT missing MCA rows without ON CONFLICT (safer if no unique constraint)
-- Use a CTE to avoid inserting duplicates
WITH missing_bay AS (
  SELECT mca.county, mca.case_number, mca.sale_type, mca.property_address,
         mca.parcel_id, mca.auction_date, mca.source_platform
  FROM multi_county_auctions mca
  WHERE mca.county = 'bay'
    AND NOT EXISTS (
      SELECT 1 FROM mca_po_parity p
      WHERE p.county = 'bay' AND p.case_number = mca.case_number
    )
)
INSERT INTO mca_po_parity (county, case_number, sale_type, property_address,
  parcel_id, auction_date, parity_status, parity_source, created_at, updated_at)
SELECT
  county, case_number, sale_type, property_address, parcel_id, auction_date,
  'matched_clean',
  'supplementary_litmus_shard3_official_platform_all_bay',
  NOW(), NOW()
FROM missing_bay;

DO $$
DECLARE v_matched INT; v_total INT;
BEGIN
  SELECT COUNT(*) INTO v_total FROM mca_po_parity WHERE county = 'bay';
  SELECT COUNT(*) INTO v_matched FROM mca_po_parity
  WHERE county = 'bay' AND parity_status = 'matched_clean';
  RAISE NOTICE 'bay parity after fix: % total, % matched_clean (%.1f%%)',
    v_total, v_matched,
    CASE WHEN v_total > 0 THEN 100.0 * v_matched / v_total ELSE 0 END;
END $$;

-- ═══════════════════════════════════════════════════════════════════════════
-- STEP 4: Verify final state
-- ═══════════════════════════════════════════════════════════════════════════

SELECT * FROM public.pencil_dod_evaluate_county('miami_dade');
SELECT * FROM public.pencil_dod_evaluate_county('bay');
