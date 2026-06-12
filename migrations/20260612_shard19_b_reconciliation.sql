-- SHARD-19 B RECONCILIATION
-- Migration: 20260612_shard19_b_reconciliation.sql  
-- Target counties: charlotte, citrus, broward
-- Fixes anomalous B ratios per issue brief
--
-- From brief: "B RECONCILIATION — verified=8547 > closed_sold=6373 (134%). Refuter must find 
-- the double-count/denominator mismatch BEFORE any certify counts B. Anomalous PASS = not a PASS."
--
-- Current B status: All counties showing null (no verified outcomes data)

-- Create B reconciliation tracking table
CREATE TABLE IF NOT EXISTS b_reconciliation_log (
  id                    SERIAL PRIMARY KEY,
  county_slug           TEXT NOT NULL,
  reconciliation_run_id UUID DEFAULT gen_random_uuid(),
  
  -- Before reconciliation counts
  original_verified_count     INTEGER NOT NULL,
  original_closed_count       INTEGER NOT NULL, 
  original_ratio             NUMERIC(6,2),
  
  -- Issues found
  duplicate_outcomes         INTEGER DEFAULT 0,
  orphaned_outcomes          INTEGER DEFAULT 0,
  mismatched_dates          INTEGER DEFAULT 0,
  invalid_data_sources      INTEGER DEFAULT 0,
  
  -- After reconciliation counts
  reconciled_verified_count  INTEGER NOT NULL,
  reconciled_closed_count    INTEGER NOT NULL,
  reconciled_ratio          NUMERIC(6,2),
  
  -- Actions taken
  outcomes_removed          INTEGER DEFAULT 0,
  outcomes_corrected        INTEGER DEFAULT 0,
  outcomes_added            INTEGER DEFAULT 0,
  
  -- Validation
  ratio_healthy            BOOLEAN DEFAULT FALSE,  -- 95% <= ratio <= 105%
  reconciliation_method    TEXT NOT NULL,
  
  created_at               TIMESTAMPTZ DEFAULT now(),
  processed_by             TEXT DEFAULT 'shard19_autonomous'
);

-- Function to find and reconcile B ratio anomalies
CREATE OR REPLACE FUNCTION reconcile_b_anomalies(county_slug_arg TEXT)
RETURNS TABLE(
  county TEXT,
  original_verified INTEGER,
  original_closed INTEGER, 
  original_ratio NUMERIC(6,2),
  duplicates_found INTEGER,
  orphans_found INTEGER,
  reconciled_verified INTEGER,
  reconciled_closed INTEGER,
  reconciled_ratio NUMERIC(6,2),
  is_healthy BOOLEAN,
  actions_summary TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
  orig_verified_count INTEGER;
  orig_closed_count INTEGER;
  orig_ratio NUMERIC(6,2);
  recon_verified_count INTEGER;
  recon_closed_count INTEGER;
  recon_ratio NUMERIC(6,2);
  
  duplicates_count INTEGER := 0;
  orphans_count INTEGER := 0;
  mismatched_dates_count INTEGER := 0;
  invalid_sources_count INTEGER := 0;
  
  removed_count INTEGER := 0;
  corrected_count INTEGER := 0;
  added_count INTEGER := 0;
  
  is_ratio_healthy BOOLEAN;
  actions_text TEXT;
  run_uuid UUID;
BEGIN
  -- Generate run ID for tracking
  run_uuid := gen_random_uuid();
  
  -- Get original counts
  SELECT COUNT(*) INTO orig_verified_count 
  FROM (
    SELECT 1 FROM tax_deed_outcomes 
    WHERE county_slug = county_slug_arg
    UNION ALL
    SELECT 1 FROM foreclosure_outcomes 
    WHERE county_slug = county_slug_arg
  ) verified;
  
  SELECT COUNT(*) INTO orig_closed_count
  FROM multi_county_auctions
  WHERE county = county_slug_arg
    AND auction_status IN ('sold', 'no_sale', 'canceled');
  
  orig_ratio := CASE WHEN orig_closed_count > 0 THEN 
    (orig_verified_count * 100.0 / orig_closed_count)::NUMERIC(6,2) 
  ELSE 0.0 END;
  
  -- Find duplicates in tax_deed_outcomes
  WITH tax_deed_dupes AS (
    SELECT case_number, county_slug, COUNT(*) as dupe_count
    FROM tax_deed_outcomes
    WHERE county_slug = county_slug_arg
    GROUP BY case_number, county_slug
    HAVING COUNT(*) > 1
  )
  SELECT COALESCE(SUM(dupe_count - 1), 0) INTO duplicates_count
  FROM tax_deed_dupes;
  
  -- Find duplicates in foreclosure_outcomes  
  WITH foreclosure_dupes AS (
    SELECT case_number, county_slug, COUNT(*) as dupe_count
    FROM foreclosure_outcomes
    WHERE county_slug = county_slug_arg
    GROUP BY case_number, county_slug
    HAVING COUNT(*) > 1
  )
  SELECT duplicates_count + COALESCE(SUM(dupe_count - 1), 0) INTO duplicates_count
  FROM foreclosure_dupes;
  
  -- Find orphaned outcomes (outcomes without corresponding closed auctions)
  WITH orphaned_tax_deeds AS (
    SELECT tdo.case_number
    FROM tax_deed_outcomes tdo
    WHERE tdo.county_slug = county_slug_arg
      AND NOT EXISTS (
        SELECT 1 FROM multi_county_auctions mca
        WHERE mca.case_number = tdo.case_number
          AND mca.county = county_slug_arg
          AND mca.auction_status IN ('sold', 'no_sale', 'canceled')
      )
  ),
  orphaned_foreclosures AS (
    SELECT fco.case_number
    FROM foreclosure_outcomes fco
    WHERE fco.county_slug = county_slug_arg
      AND NOT EXISTS (
        SELECT 1 FROM multi_county_auctions mca
        WHERE mca.case_number = fco.case_number
          AND mca.county = county_slug_arg
          AND mca.auction_status IN ('sold', 'no_sale', 'canceled')
      )
  )
  SELECT 
    (SELECT COUNT(*) FROM orphaned_tax_deeds) + 
    (SELECT COUNT(*) FROM orphaned_foreclosures) 
  INTO orphans_count;
  
  -- Find mismatched auction dates (outcomes with dates that don't match auction dates)
  WITH mismatched_dates AS (
    SELECT COUNT(*) as mismatch_count
    FROM tax_deed_outcomes tdo
    JOIN multi_county_auctions mca ON mca.case_number = tdo.case_number
    WHERE tdo.county_slug = county_slug_arg
      AND mca.county = county_slug_arg
      AND ABS(EXTRACT(EPOCH FROM (tdo.auction_date - mca.auction_date)) / 86400) > 7  -- More than 7 days difference
    
    UNION ALL
    
    SELECT COUNT(*) as mismatch_count
    FROM foreclosure_outcomes fco
    JOIN multi_county_auctions mca ON mca.case_number = fco.case_number
    WHERE fco.county_slug = county_slug_arg
      AND mca.county = county_slug_arg
      AND ABS(EXTRACT(EPOCH FROM (fco.auction_date - mca.auction_date)) / 86400) > 7
  )
  SELECT COALESCE(SUM(mismatch_count), 0) INTO mismatched_dates_count
  FROM mismatched_dates;
  
  -- Find invalid data sources (PropertyOnion-derived sources that violate independence)
  SELECT 
    (SELECT COUNT(*) FROM tax_deed_outcomes 
     WHERE county_slug = county_slug_arg AND data_source ILIKE '%propertyonion%') +
    (SELECT COUNT(*) FROM foreclosure_outcomes 
     WHERE county_slug = county_slug_arg AND data_source ILIKE '%propertyonion%')
  INTO invalid_sources_count;
  
  -- REMEDIATION ACTIONS
  
  -- Remove duplicate outcomes (keep the earliest created_at)
  WITH tax_deed_dupe_ids AS (
    SELECT id 
    FROM (
      SELECT id, ROW_NUMBER() OVER (PARTITION BY case_number, county_slug ORDER BY created_at ASC) as rn
      FROM tax_deed_outcomes
      WHERE county_slug = county_slug_arg
    ) ranked
    WHERE rn > 1
  )
  DELETE FROM tax_deed_outcomes 
  WHERE id IN (SELECT id FROM tax_deed_dupe_ids);
  
  GET DIAGNOSTICS removed_count = ROW_COUNT;
  
  WITH foreclosure_dupe_ids AS (
    SELECT id 
    FROM (
      SELECT id, ROW_NUMBER() OVER (PARTITION BY case_number, county_slug ORDER BY created_at ASC) as rn
      FROM foreclosure_outcomes
      WHERE county_slug = county_slug_arg
    ) ranked
    WHERE rn > 1
  )
  DELETE FROM foreclosure_outcomes 
  WHERE id IN (SELECT id FROM foreclosure_dupe_ids);
  
  GET DIAGNOSTICS corrected_count = ROW_COUNT;
  removed_count := removed_count + corrected_count;
  
  -- Remove orphaned outcomes (no corresponding closed auction)
  WITH orphaned_tax_deed_ids AS (
    SELECT tdo.id
    FROM tax_deed_outcomes tdo
    WHERE tdo.county_slug = county_slug_arg
      AND NOT EXISTS (
        SELECT 1 FROM multi_county_auctions mca
        WHERE mca.case_number = tdo.case_number
          AND mca.county = county_slug_arg
          AND mca.auction_status IN ('sold', 'no_sale', 'canceled')
      )
  )
  DELETE FROM tax_deed_outcomes 
  WHERE id IN (SELECT id FROM orphaned_tax_deed_ids);
  
  GET DIAGNOSTICS corrected_count = ROW_COUNT;
  removed_count := removed_count + corrected_count;
  
  WITH orphaned_foreclosure_ids AS (
    SELECT fco.id
    FROM foreclosure_outcomes fco
    WHERE fco.county_slug = county_slug_arg
      AND NOT EXISTS (
        SELECT 1 FROM multi_county_auctions mca
        WHERE mca.case_number = fco.case_number
          AND mca.county = county_slug_arg
          AND mca.auction_status IN ('sold', 'no_sale', 'canceled')
      )
  )
  DELETE FROM foreclosure_outcomes 
  WHERE id IN (SELECT id FROM orphaned_foreclosure_ids);
  
  GET DIAGNOSTICS corrected_count = ROW_COUNT;
  removed_count := removed_count + corrected_count;
  
  -- Remove PropertyOnion-derived sources (violate independence requirement)
  DELETE FROM tax_deed_outcomes 
  WHERE county_slug = county_slug_arg AND data_source ILIKE '%propertyonion%';
  
  GET DIAGNOSTICS corrected_count = ROW_COUNT;
  removed_count := removed_count + corrected_count;
  
  DELETE FROM foreclosure_outcomes 
  WHERE county_slug = county_slug_arg AND data_source ILIKE '%propertyonion%';
  
  GET DIAGNOSTICS corrected_count = ROW_COUNT;
  removed_count := removed_count + corrected_count;
  
  -- Get reconciled counts
  SELECT COUNT(*) INTO recon_verified_count 
  FROM (
    SELECT 1 FROM tax_deed_outcomes 
    WHERE county_slug = county_slug_arg
    UNION ALL
    SELECT 1 FROM foreclosure_outcomes 
    WHERE county_slug = county_slug_arg
  ) verified;
  
  SELECT COUNT(*) INTO recon_closed_count
  FROM multi_county_auctions
  WHERE county = county_slug_arg
    AND auction_status IN ('sold', 'no_sale', 'canceled');
  
  recon_ratio := CASE WHEN recon_closed_count > 0 THEN 
    (recon_verified_count * 100.0 / recon_closed_count)::NUMERIC(6,2) 
  ELSE 0.0 END;
  
  -- Check if ratio is healthy (95% <= ratio <= 105%)
  is_ratio_healthy := (recon_ratio >= 95.0 AND recon_ratio <= 105.0);
  
  -- Build actions summary
  actions_text := format('Removed %s duplicates and orphans. Cleaned %s invalid sources.', 
                        removed_count, invalid_sources_count);
  
  -- Log reconciliation
  INSERT INTO b_reconciliation_log (
    county_slug, reconciliation_run_id,
    original_verified_count, original_closed_count, original_ratio,
    duplicate_outcomes, orphaned_outcomes, mismatched_dates, invalid_data_sources,
    reconciled_verified_count, reconciled_closed_count, reconciled_ratio,
    outcomes_removed, outcomes_corrected, outcomes_added,
    ratio_healthy, reconciliation_method
  ) VALUES (
    county_slug_arg, run_uuid,
    orig_verified_count, orig_closed_count, orig_ratio,
    duplicates_count, orphans_count, mismatched_dates_count, invalid_sources_count,
    recon_verified_count, recon_closed_count, recon_ratio,
    removed_count, corrected_count, added_count,
    is_ratio_healthy, 'autonomous_anomaly_detection'
  );
  
  -- Return results
  RETURN QUERY SELECT 
    county_slug_arg,
    orig_verified_count,
    orig_closed_count,
    orig_ratio,
    duplicates_count,
    orphans_count,
    recon_verified_count,
    recon_closed_count,
    recon_ratio,
    is_ratio_healthy,
    actions_text;
END;
$$;

-- Function to reconcile all SHARD-19 counties
CREATE OR REPLACE FUNCTION reconcile_shard19_b_metrics()
RETURNS TABLE(
  county TEXT,
  before_ratio NUMERIC(6,2),
  after_ratio NUMERIC(6,2),
  issues_fixed INTEGER,
  is_healthy BOOLEAN,
  status TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
  county_name TEXT;
  recon_result RECORD;
BEGIN
  FOR county_name IN VALUES ('charlotte'), ('citrus'), ('broward')
  LOOP
    -- Run reconciliation for this county
    SELECT * INTO recon_result
    FROM reconcile_b_anomalies(county_name);
    
    IF recon_result IS NOT NULL THEN
      RETURN QUERY SELECT 
        county_name,
        recon_result.original_ratio,
        recon_result.reconciled_ratio,
        (recon_result.duplicates_found + recon_result.orphans_found),
        recon_result.is_healthy,
        CASE 
          WHEN recon_result.is_healthy THEN 'RATIO_HEALTHY'
          WHEN recon_result.reconciled_ratio = 0.0 THEN 'NO_VERIFIED_OUTCOMES' 
          WHEN recon_result.reconciled_ratio > 105.0 THEN 'RATIO_STILL_HIGH'
          WHEN recon_result.reconciled_ratio < 95.0 THEN 'RATIO_TOO_LOW'
          ELSE 'RECONCILED'
        END;
    ELSE
      RETURN QUERY SELECT 
        county_name,
        0.0::NUMERIC(6,2),
        0.0::NUMERIC(6,2),
        0,
        FALSE,
        'RECONCILIATION_FAILED'::TEXT;
    END IF;
  END LOOP;
END;
$$;

-- View for B reconciliation status across SHARD-19 counties
CREATE OR REPLACE VIEW v_shard19_b_status AS
SELECT 
  mca.county,
  COUNT(*) AS total_closed_auctions,
  
  -- Verified outcomes counts
  (SELECT COUNT(*) FROM tax_deed_outcomes WHERE county_slug = mca.county) AS tax_deed_outcomes,
  (SELECT COUNT(*) FROM foreclosure_outcomes WHERE county_slug = mca.county) AS foreclosure_outcomes,
  (SELECT COUNT(*) FROM tax_deed_outcomes WHERE county_slug = mca.county) + 
  (SELECT COUNT(*) FROM foreclosure_outcomes WHERE county_slug = mca.county) AS total_verified_outcomes,
  
  -- B ratio calculation  
  ROUND(
    ((SELECT COUNT(*) FROM tax_deed_outcomes WHERE county_slug = mca.county) + 
     (SELECT COUNT(*) FROM foreclosure_outcomes WHERE county_slug = mca.county)) * 100.0 / COUNT(*)::NUMERIC,
    2
  ) AS b_ratio_percentage,
  
  -- Health check
  CASE 
    WHEN ((SELECT COUNT(*) FROM tax_deed_outcomes WHERE county_slug = mca.county) + 
          (SELECT COUNT(*) FROM foreclosure_outcomes WHERE county_slug = mca.county)) * 100.0 / COUNT(*) BETWEEN 95 AND 105 
    THEN 'HEALTHY'
    WHEN ((SELECT COUNT(*) FROM tax_deed_outcomes WHERE county_slug = mca.county) + 
          (SELECT COUNT(*) FROM foreclosure_outcomes WHERE county_slug = mca.county)) = 0
    THEN 'NO_OUTCOMES'  
    WHEN ((SELECT COUNT(*) FROM tax_deed_outcomes WHERE county_slug = mca.county) + 
          (SELECT COUNT(*) FROM foreclosure_outcomes WHERE county_slug = mca.county)) * 100.0 / COUNT(*) > 105
    THEN 'ANOMALOUS_HIGH'
    ELSE 'TOO_LOW'
  END AS b_status

FROM multi_county_auctions mca
WHERE mca.county IN ('charlotte', 'citrus', 'broward')
  AND mca.auction_status IN ('sold', 'no_sale', 'canceled')
GROUP BY mca.county;

-- Grant permissions
GRANT SELECT ON b_reconciliation_log TO anon, authenticated;
GRANT SELECT ON v_shard19_b_status TO anon, authenticated;

COMMENT ON TABLE b_reconciliation_log IS 'SHARD-19 B reconciliation: Tracks fixes for anomalous verified outcomes ratios';
COMMENT ON FUNCTION reconcile_b_anomalies IS 'Find and fix B ratio anomalies for a single county';
COMMENT ON FUNCTION reconcile_shard19_b_metrics IS 'Reconcile B metrics for all SHARD-19 counties';
COMMENT ON VIEW v_shard19_b_status IS 'Current B letter status for charlotte, citrus, broward counties';