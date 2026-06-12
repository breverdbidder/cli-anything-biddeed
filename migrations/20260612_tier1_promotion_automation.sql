-- TIER1 PROMOTION AUTOMATION
-- Migration: 20260612_tier1_promotion_automation.sql
-- Implements automatic tier1_sold_amount promotion from verified outcomes
-- Required for Gold Standard Letter F compliance

-- Function to promote tier1_sold_amount from verified outcomes
CREATE OR REPLACE FUNCTION public.promote_tier1_from_outcomes()
RETURNS TABLE(
  county_slug TEXT,
  promoted_count INTEGER,
  total_available INTEGER
)
LANGUAGE plpgsql
AS $$
DECLARE
  promotion_rec RECORD;
  total_promoted INTEGER := 0;
  current_county TEXT;
  current_count INTEGER;
BEGIN
  -- Clear any existing results
  DELETE FROM pg_temp.promotion_results WHERE TRUE;
  CREATE TEMP TABLE IF NOT EXISTS promotion_results (
    county_slug TEXT,
    promoted_count INTEGER,
    total_available INTEGER
  );

  -- Promote from foreclosure_outcomes
  FOR promotion_rec IN
    SELECT 
      fo.county_slug,
      fo.case_number,
      COALESCE(fo.sale_amount, fo.high_bid) as amount,
      fo.auction_date,
      fo.data_source
    FROM foreclosure_outcomes fo
    JOIN multi_county_auctions mca ON mca.case_number = fo.case_number 
      AND mca.county = fo.county_slug
    WHERE 
      mca.tier1_sold_amount IS NULL
      AND COALESCE(fo.sale_amount, fo.high_bid) IS NOT NULL
      AND COALESCE(fo.sale_amount, fo.high_bid) > 0
      AND fo.data_source NOT ILIKE '%propertyonion%'  -- Only independent sources
  LOOP
    -- Update multi_county_auctions with tier1 amount
    UPDATE multi_county_auctions 
    SET 
      tier1_sold_amount = promotion_rec.amount,
      tier1_verified_at = now(),
      tier1_source = 'foreclosure_outcomes:' || promotion_rec.data_source,
      updated_at = now()
    WHERE 
      case_number = promotion_rec.case_number 
      AND county = promotion_rec.county_slug
      AND tier1_sold_amount IS NULL;

    IF FOUND THEN
      total_promoted := total_promoted + 1;
    END IF;
  END LOOP;

  -- Promote from tax_deed_outcomes
  FOR promotion_rec IN
    SELECT 
      tdo.county_slug,
      tdo.case_number,
      tdo.sale_amount as amount,
      tdo.auction_date,
      tdo.data_source
    FROM tax_deed_outcomes tdo
    JOIN multi_county_auctions mca ON mca.case_number = tdo.case_number 
      AND mca.county = tdo.county_slug
    WHERE 
      mca.tier1_sold_amount IS NULL
      AND tdo.sale_amount IS NOT NULL
      AND tdo.sale_amount > 0
      AND tdo.data_source NOT ILIKE '%propertyonion%'  -- Only independent sources
  LOOP
    -- Update multi_county_auctions with tier1 amount
    UPDATE multi_county_auctions 
    SET 
      tier1_sold_amount = promotion_rec.amount,
      tier1_verified_at = now(),
      tier1_source = 'tax_deed_outcomes:' || promotion_rec.data_source,
      updated_at = now()
    WHERE 
      case_number = promotion_rec.case_number 
      AND county = promotion_rec.county_slug
      AND tier1_sold_amount IS NULL;

    IF FOUND THEN
      total_promoted := total_promoted + 1;
    END IF;
  END LOOP;

  -- Generate per-county summary
  FOR current_county IN 
    SELECT DISTINCT mca.county 
    FROM multi_county_auctions mca
    WHERE mca.county IN (
      SELECT DISTINCT county_slug FROM foreclosure_outcomes
      UNION
      SELECT DISTINCT county_slug FROM tax_deed_outcomes
    )
  LOOP
    -- Count promoted for this county
    SELECT COUNT(*) INTO current_count
    FROM multi_county_auctions mca
    WHERE mca.county = current_county
      AND mca.tier1_sold_amount IS NOT NULL
      AND mca.tier1_verified_at >= now() - INTERVAL '5 minutes';

    -- Count total available outcomes for this county
    WITH available_outcomes AS (
      SELECT case_number FROM foreclosure_outcomes 
      WHERE county_slug = current_county 
        AND COALESCE(sale_amount, high_bid) IS NOT NULL
        AND data_source NOT ILIKE '%propertyonion%'
      UNION
      SELECT case_number FROM tax_deed_outcomes
      WHERE county_slug = current_county 
        AND sale_amount IS NOT NULL
        AND data_source NOT ILIKE '%propertyonion%'
    )
    INSERT INTO pg_temp.promotion_results (county_slug, promoted_count, total_available)
    SELECT 
      current_county,
      current_count,
      (SELECT COUNT(*) FROM available_outcomes);
  END LOOP;

  -- Return results
  RETURN QUERY SELECT pr.county_slug, pr.promoted_count, pr.total_available 
  FROM pg_temp.promotion_results pr
  ORDER BY pr.county_slug;
END;
$$;

-- Helper function to check tier1 promotion status
CREATE OR REPLACE FUNCTION public.check_tier1_coverage(county_slug_arg TEXT DEFAULT NULL)
RETURNS TABLE(
  county_slug TEXT,
  total_closed INTEGER,
  with_tier1 INTEGER,
  coverage_pct NUMERIC,
  last_promotion TIMESTAMPTZ
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT 
    mca.county as county_slug,
    COUNT(*)::INTEGER as total_closed,
    COUNT(mca.tier1_sold_amount)::INTEGER as with_tier1,
    CASE 
      WHEN COUNT(*) > 0 THEN (COUNT(mca.tier1_sold_amount) * 100.0 / COUNT(*))
      ELSE 0
    END as coverage_pct,
    MAX(mca.tier1_verified_at) as last_promotion
  FROM multi_county_auctions mca
  WHERE 
    mca.auction_status IN ('sold', 'no_sale', 'canceled')
    AND (county_slug_arg IS NULL OR mca.county = county_slug_arg)
  GROUP BY mca.county
  ORDER BY coverage_pct DESC, mca.county;
END;
$$;

-- Function to queue acclaim harvest jobs for missing case numbers
CREATE OR REPLACE FUNCTION public.feed_acclaim_queue_brevard()
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
  queued_count INTEGER := 0;
BEGIN
  -- Queue Brevard foreclosure cases that are closed but not in acclaim outcomes
  INSERT INTO acclaim_harvest_queue (
    county_slug,
    case_number,
    sale_type,
    auction_date,
    status,
    created_at
  )
  SELECT DISTINCT
    'brevard',
    mca.case_number,
    'foreclosure',
    mca.auction_date,
    'pending',
    now()
  FROM multi_county_auctions mca
  WHERE 
    mca.county = 'brevard'
    AND mca.sale_type = 'foreclosure'
    AND mca.auction_status IN ('sold', 'no_sale', 'canceled')
    AND mca.case_number IS NOT NULL
    AND NOT EXISTS (
      SELECT 1 FROM foreclosure_outcomes fo 
      WHERE fo.case_number = mca.case_number 
        AND fo.county_slug = 'brevard'
    )
    AND NOT EXISTS (
      SELECT 1 FROM acclaim_harvest_queue ahq
      WHERE ahq.case_number = mca.case_number 
        AND ahq.county_slug = 'brevard'
    );

  GET DIAGNOSTICS queued_count = ROW_COUNT;
  
  RETURN queued_count;
END;
$$;

-- Create acclaim_harvest_queue table if it doesn't exist (based on Duval pattern)
CREATE TABLE IF NOT EXISTS acclaim_harvest_queue (
  id                SERIAL PRIMARY KEY,
  county_slug       TEXT NOT NULL,
  case_number       TEXT NOT NULL,
  sale_type         TEXT NOT NULL, -- 'foreclosure', 'tax_deed'  
  auction_date      DATE,
  status            TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
  attempts          INTEGER DEFAULT 0,
  last_attempt_at   TIMESTAMPTZ,
  error_message     TEXT,
  created_at        TIMESTAMPTZ DEFAULT now(),
  completed_at      TIMESTAMPTZ,
  
  UNIQUE(county_slug, case_number, sale_type)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_ahq_county_status ON acclaim_harvest_queue(county_slug, status);
CREATE INDEX IF NOT EXISTS idx_ahq_case_number ON acclaim_harvest_queue(case_number);
CREATE INDEX IF NOT EXISTS idx_ahq_created_at ON acclaim_harvest_queue(created_at);

-- Grant permissions
GRANT EXECUTE ON FUNCTION public.promote_tier1_from_outcomes() TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.check_tier1_coverage(TEXT) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.feed_acclaim_queue_brevard() TO anon, authenticated;

GRANT SELECT, INSERT, UPDATE ON acclaim_harvest_queue TO anon, authenticated;

-- Add comments
COMMENT ON FUNCTION public.promote_tier1_from_outcomes() IS 'Promotes tier1_sold_amount from verified outcomes tables - runs hourly via cron';
COMMENT ON FUNCTION public.check_tier1_coverage(TEXT) IS 'Reports tier1_sold_amount coverage by county for Letter F assessment';
COMMENT ON FUNCTION public.feed_acclaim_queue_brevard() IS 'Queues missing Brevard foreclosure cases for AcclaimWeb harvest';
COMMENT ON TABLE acclaim_harvest_queue IS 'Queue for AcclaimWeb document harvest jobs';