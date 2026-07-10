-- RL Reward Engine V1: prediction_trajectories table
-- Issue: https://github.com/breverdbidder/cli-anything-biddeed/issues/119
-- Created: 2026-03-31

CREATE TABLE IF NOT EXISTS prediction_trajectories (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at timestamptz DEFAULT now(),

  -- Prediction inputs
  case_number text NOT NULL,
  auction_date date NOT NULL,
  auction_type text NOT NULL CHECK (auction_type IN ('foreclosure', 'tax_deed')),
  zip_code text NOT NULL,
  property_type text,
  county text DEFAULT 'Brevard',

  -- Shapira Formula inputs at prediction time
  arv_estimate numeric,
  repair_estimate numeric,
  judgment_amount numeric,
  max_bid_calculated numeric,
  bid_judgment_ratio numeric,
  recommendation text CHECK (recommendation IN ('BID', 'REVIEW', 'SKIP')),
  xgboost_probability numeric,
  xgboost_confidence numeric,

  -- Market context snapshot at prediction time
  zip_median_income numeric,
  zip_vacancy_rate numeric,
  days_on_market_avg numeric,
  similar_sales_count integer,
  market_trend text CHECK (market_trend IN ('rising', 'stable', 'declining')),

  -- Actual outcome (filled AFTER auction closes)
  actual_sold boolean,
  actual_sale_price numeric,
  actual_buyer_type text CHECK (actual_buyer_type IN ('third_party', 'plaintiff', 'no_sale')),

  -- Reward scoring
  prediction_delta numeric GENERATED ALWAYS AS (actual_sale_price - max_bid_calculated) STORED,
  reward_score numeric,
  outcome_recorded_at timestamptz,

  -- Versioning
  model_version text DEFAULT 'xgboost_v1',
  formula_version text DEFAULT 'shapira_v1',
  pipeline_version text
);

CREATE INDEX IF NOT EXISTS idx_traj_zip ON prediction_trajectories(zip_code);
CREATE INDEX IF NOT EXISTS idx_traj_date ON prediction_trajectories(auction_date);
CREATE INDEX IF NOT EXISTS idx_traj_type ON prediction_trajectories(auction_type);
CREATE INDEX IF NOT EXISTS idx_traj_outcome ON prediction_trajectories(actual_sold) WHERE actual_sold IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_traj_reward ON prediction_trajectories(reward_score) WHERE reward_score IS NOT NULL;

-- Enable RLS
ALTER TABLE prediction_trajectories ENABLE ROW LEVEL SECURITY;

-- RLS Policies
-- Service role bypasses RLS (Supabase default), so no policy needed for service role
-- Anon: no access
-- Authenticated: read-only
CREATE POLICY "Authenticated users can read trajectories"
  ON prediction_trajectories
  FOR SELECT
  TO authenticated
  USING (true);

CREATE POLICY "Service role full access"
  ON prediction_trajectories
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- Backfill from historical_auctions as seed trajectories
-- historical_auctions columns: case_number, auction_date, auction_type, zip_code,
--   final_judgment, winning_bid, status, buyer_type, county
INSERT INTO prediction_trajectories (
  case_number,
  auction_date,
  auction_type,
  zip_code,
  county,
  judgment_amount,
  actual_sold,
  actual_sale_price,
  actual_buyer_type,
  outcome_recorded_at,
  model_version,
  formula_version
)
SELECT
  case_number,
  auction_date::date,
  CASE
    WHEN auction_type ILIKE '%tax%' THEN 'tax_deed'
    ELSE 'foreclosure'
  END,
  COALESCE(NULLIF(TRIM(zip_code), ''), 'unknown'),
  COALESCE(county, 'Brevard'),
  final_judgment,
  CASE WHEN status ILIKE '%sold%' THEN true ELSE false END,
  winning_bid,
  CASE
    WHEN buyer_type ILIKE '%third%' THEN 'third_party'
    WHEN buyer_type ILIKE '%plaintiff%' THEN 'plaintiff'
    ELSE 'no_sale'
  END,
  now(),
  'backfill_v1',
  'shapira_v1'
FROM historical_auctions
WHERE auction_date IS NOT NULL
  AND case_number IS NOT NULL
ON CONFLICT DO NOTHING;
