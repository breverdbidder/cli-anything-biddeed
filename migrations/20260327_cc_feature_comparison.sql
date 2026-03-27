-- cc_feature_comparison: Eval table for Coder Workspaces vs SUMMIT dispatch
-- Spec: CODER-ADOPTION.md Section 4
-- Created: 2026-03-27

CREATE TABLE IF NOT EXISTS cc_feature_comparison (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  system text NOT NULL CHECK (system IN ('coder', 'summit')),
  task_description text NOT NULL,
  wall_clock_seconds int,
  token_cost_usd numeric(10,4),
  quality_score int CHECK (quality_score BETWEEN 1 AND 10),
  errors_count int DEFAULT 0,
  pr_merged boolean DEFAULT false,
  winner text,
  notes text,
  created_at timestamptz DEFAULT now()
);

COMMENT ON TABLE cc_feature_comparison IS 'Eval: Coder Workspaces vs SUMMIT dispatch (Mar 2026)';

-- Index for quick system comparisons
CREATE INDEX IF NOT EXISTS idx_cc_feat_system ON cc_feature_comparison(system);
CREATE INDEX IF NOT EXISTS idx_cc_feat_created ON cc_feature_comparison(created_at DESC);

-- RLS: service_role only (internal eval data)
ALTER TABLE cc_feature_comparison ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access" ON cc_feature_comparison
  FOR ALL USING (auth.role() = 'service_role');
