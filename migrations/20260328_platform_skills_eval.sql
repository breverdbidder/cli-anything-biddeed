-- Migration: Platform Skills Eval Extension
-- Date: 2026-03-28
-- Purpose: Extend cc_feature_comparison with skills-specific scoring columns
-- Spec: PLATFORM-SKILLS-ADOPTION.md

-- ============================================================
-- 1. Extend cc_feature_comparison table
-- ============================================================

ALTER TABLE cc_feature_comparison
  ADD COLUMN IF NOT EXISTS skill_type text DEFAULT 'custom'
    CHECK (skill_type IN ('layer3_rule', 'platform_skill', 'custom')),
  ADD COLUMN IF NOT EXISTS trigger_accuracy integer DEFAULT NULL
    CHECK (trigger_accuracy IS NULL OR (trigger_accuracy >= 1 AND trigger_accuracy <= 10)),
  ADD COLUMN IF NOT EXISTS hot_reload_benefit boolean DEFAULT false,
  ADD COLUMN IF NOT EXISTS eval_native_score numeric(5,2) DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS context_isolation boolean DEFAULT false,
  ADD COLUMN IF NOT EXISTS migration_effort text DEFAULT NULL
    CHECK (migration_effort IS NULL OR migration_effort IN ('trivial', 'moderate', 'complex'));

-- Add comment for documentation
COMMENT ON COLUMN cc_feature_comparison.skill_type IS 'layer3_rule = .claude/rules/, platform_skill = .claude/skills/, custom = other';
COMMENT ON COLUMN cc_feature_comparison.trigger_accuracy IS '1-10: Did the skill activate when it should?';
COMMENT ON COLUMN cc_feature_comparison.hot_reload_benefit IS 'Did hot-reload matter for this task?';
COMMENT ON COLUMN cc_feature_comparison.eval_native_score IS 'Platform Skills native eval score (if available)';
COMMENT ON COLUMN cc_feature_comparison.context_isolation IS 'Did context forking help?';
COMMENT ON COLUMN cc_feature_comparison.migration_effort IS 'trivial/moderate/complex effort to migrate';

-- ============================================================
-- 2. Skills eval results table (detailed per-assertion tracking)
-- ============================================================

CREATE TABLE IF NOT EXISTS skills_eval_results (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  skill_id text NOT NULL,
  skill_type text NOT NULL CHECK (skill_type IN ('layer3_rule', 'platform_skill')),
  repo text NOT NULL,
  eval_run_id text NOT NULL,
  assertion_id integer NOT NULL,
  assertion_input text,
  expected text,
  actual text,
  passed boolean NOT NULL,
  wall_clock_ms integer,
  tokens_used integer,
  created_at timestamptz DEFAULT now()
);

-- Index for querying eval runs
CREATE INDEX IF NOT EXISTS idx_skills_eval_skill_id ON skills_eval_results(skill_id);
CREATE INDEX IF NOT EXISTS idx_skills_eval_run_id ON skills_eval_results(eval_run_id);
CREATE INDEX IF NOT EXISTS idx_skills_eval_created ON skills_eval_results(created_at DESC);

COMMENT ON TABLE skills_eval_results IS 'Per-assertion results from Platform Skills vs Layer 3 eval runs';

-- ============================================================
-- 3. Skills adoption decisions (audit trail)
-- ============================================================

CREATE TABLE IF NOT EXISTS skills_adoption_log (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  skill_id text NOT NULL,
  candidate_pattern text NOT NULL,
  decision text NOT NULL CHECK (decision IN ('ADOPT', 'EVAL', 'KEEP')),
  wall_clock_score numeric(5,2),
  token_cost_score numeric(5,2),
  quality_score numeric(5,2),
  trigger_accuracy_score numeric(5,2),
  compliance_rate_score numeric(5,2),
  overall_score numeric(5,2),
  layer3_pass_rate numeric(5,4),
  platform_pass_rate numeric(5,4),
  notes text,
  decided_at timestamptz DEFAULT now(),
  decided_by text DEFAULT 'claude_architect'
);

CREATE INDEX IF NOT EXISTS idx_skills_adoption_skill ON skills_adoption_log(skill_id);

COMMENT ON TABLE skills_adoption_log IS 'ADOPT/EVAL/KEEP decisions per skill candidate with scoring breakdown';

-- ============================================================
-- 4. View: Eval comparison summary
-- ============================================================

CREATE OR REPLACE VIEW skills_eval_summary AS
SELECT
  skill_id,
  skill_type,
  eval_run_id,
  COUNT(*) AS total_assertions,
  SUM(CASE WHEN passed THEN 1 ELSE 0 END) AS passed_count,
  ROUND(
    SUM(CASE WHEN passed THEN 1 ELSE 0 END)::numeric / COUNT(*)::numeric * 100, 2
  ) AS pass_rate,
  ROUND(AVG(wall_clock_ms)::numeric, 0) AS avg_wall_clock_ms,
  SUM(tokens_used) AS total_tokens,
  MIN(created_at) AS started_at,
  MAX(created_at) AS completed_at
FROM skills_eval_results
GROUP BY skill_id, skill_type, eval_run_id;

COMMENT ON VIEW skills_eval_summary IS 'Aggregated pass rates and performance per eval run';

-- ============================================================
-- 5. RLS policies
-- ============================================================

ALTER TABLE skills_eval_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE skills_adoption_log ENABLE ROW LEVEL SECURITY;

-- Service role full access (for CC/SUMMIT)
CREATE POLICY "service_full_access_eval" ON skills_eval_results
  FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "service_full_access_adoption" ON skills_adoption_log
  FOR ALL USING (true) WITH CHECK (true);
