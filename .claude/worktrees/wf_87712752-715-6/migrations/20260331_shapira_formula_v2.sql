-- Migration: Shapira Formula V2 — Adaptive Parameter Learning
-- Date: 2026-03-31
-- Issue: breverdbidder/cli-anything-biddeed#120
-- Purpose: prediction_trajectories (RL ground truth) + learned_parameters + retrain_events

-- ============================================================
-- 1. prediction_trajectories — RL reward loop ground truth
--    Records formula predictions vs actual auction outcomes
-- ============================================================

CREATE TABLE IF NOT EXISTS prediction_trajectories (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT now(),
  -- Property context
  case_number TEXT,
  parcel_id TEXT,
  zip_code TEXT NOT NULL,
  auction_type TEXT NOT NULL DEFAULT 'foreclosure'
    CHECK (auction_type IN ('foreclosure', 'tax_deed')),
  property_type TEXT,
  -- Formula inputs
  arv_used NUMERIC,
  repairs_estimate NUMERIC DEFAULT 0,
  judgment_amount NUMERIC,
  -- Formula V1 output
  predicted_max_bid NUMERIC,
  predicted_action TEXT CHECK (predicted_action IN ('BID', 'REVIEW', 'SKIP')),
  bid_ratio NUMERIC,
  parameters_version TEXT DEFAULT 'v1_default',
  -- Actual outcome (populated after auction)
  actual_sold NUMERIC,
  winning_bidder_type TEXT,
  -- Reward signal
  reward_score NUMERIC,
  outcome_notes TEXT,
  -- Source
  source_auction_id UUID
);

CREATE INDEX IF NOT EXISTS pt_zip_type_idx ON prediction_trajectories (zip_code, auction_type);
CREATE INDEX IF NOT EXISTS pt_created_idx ON prediction_trajectories (created_at DESC);
CREATE INDEX IF NOT EXISTS pt_outcome_idx ON prediction_trajectories (actual_sold) WHERE actual_sold IS NOT NULL;
CREATE INDEX IF NOT EXISTS pt_reward_idx ON prediction_trajectories (reward_score) WHERE reward_score IS NOT NULL;

-- ============================================================
-- 2. learned_parameters — adaptive Shapira Formula params per zip + auction_type
-- ============================================================

CREATE TABLE IF NOT EXISTS learned_parameters (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT now(),
  zip_code TEXT NOT NULL,
  auction_type TEXT NOT NULL CHECK (auction_type IN ('foreclosure', 'tax_deed')),
  parameters JSONB NOT NULL,
  sample_size INTEGER NOT NULL,
  avg_reward NUMERIC,
  retrained_at TIMESTAMPTZ DEFAULT now(),
  model_version TEXT DEFAULT 'shapira_v2',
  UNIQUE(zip_code, auction_type)
);

CREATE INDEX IF NOT EXISTS lp_zip_type_idx ON learned_parameters (zip_code, auction_type);
CREATE INDEX IF NOT EXISTS lp_retrained_idx ON learned_parameters (retrained_at DESC);

-- ============================================================
-- 3. retrain_events — audit log for every monthly retrain run
-- ============================================================

CREATE TABLE IF NOT EXISTS retrain_events (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT now(),
  total_trajectories INTEGER,
  groups_retrained INTEGER,
  groups_skipped INTEGER,
  model_version TEXT DEFAULT 'shapira_v2',
  accuracy_before NUMERIC,
  accuracy_after NUMERIC,
  duration_seconds NUMERIC(8, 2),
  notes TEXT
);

CREATE INDEX IF NOT EXISTS re_created_idx ON retrain_events (created_at DESC);

-- ============================================================
-- 4. Row Level Security
-- ============================================================

ALTER TABLE prediction_trajectories ENABLE ROW LEVEL SECURITY;
ALTER TABLE learned_parameters ENABLE ROW LEVEL SECURITY;
ALTER TABLE retrain_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY IF NOT EXISTS "service_role_all_prediction_trajectories"
  ON prediction_trajectories FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

CREATE POLICY IF NOT EXISTS "service_role_all_learned_parameters"
  ON learned_parameters FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

CREATE POLICY IF NOT EXISTS "service_role_all_retrain_events"
  ON retrain_events FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

-- Anon can read learned_parameters (formula lookups from app)
CREATE POLICY IF NOT EXISTS "anon_read_learned_parameters"
  ON learned_parameters FOR SELECT
  USING (true);
