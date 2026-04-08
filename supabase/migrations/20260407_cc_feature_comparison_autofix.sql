-- CC Feature Comparison — autofix-pr eval row
-- SUMMIT 275 / Issue #393
-- Date: 2026-04-07

-- Create table if not exists (idempotent with prior migration)
CREATE TABLE IF NOT EXISTS cc_feature_comparison (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  feature_name TEXT NOT NULL,
  cc_native_version TEXT,
  custom_equivalent TEXT,
  verdict TEXT CHECK (verdict IN ('ADOPT', 'PARK', 'RETIRE', 'REJECT')),
  time_to_green_seconds INT,
  token_cost_usd NUMERIC(8,4),
  hitl_touches INT DEFAULT 0,
  fix_correctness BOOLEAN,
  context_retention TEXT,
  notes TEXT,
  summit_issue INT,
  evaluated_at TIMESTAMPTZ DEFAULT NOW(),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert autofix-pr eval result
INSERT INTO cc_feature_comparison (
  feature_name, cc_native_version, custom_equivalent, verdict,
  time_to_green_seconds, token_cost_usd, hitl_touches, fix_correctness,
  context_retention, notes, summit_issue
) VALUES (
  'autofix-pr',
  '2.1.92',
  'AUTOLOOP V2 PR-fix layer',
  'PARK',
  NULL,
  0,
  0,
  NULL,
  NULL,
  'PARK: autofix-pr is a CCR remote agent type, unavailable in GHA dispatch. zonewise-web lacks ESLint CI gate. gh-aw agent has depleted API credits. Re-eval needed from interactive CC session.',
  393
) ON CONFLICT DO NOTHING;
