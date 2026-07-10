-- Migration: AUTOLOOP L3 — Self-Evolving Skills
-- Date: 2026-03-29
-- Spec: specs/AUTOLOOP-L3-SPEC.md
-- Source: Patterns extracted from HKUDS/OpenSpace (REPOEVAL 58/100 EVAL)
-- Issue: breverdbidder/cli-anything-biddeed#16

-- ============================================================
-- 1. Post-Execution Analyzer results
-- ============================================================

CREATE TABLE IF NOT EXISTS skill_analyses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  skill_name TEXT NOT NULL,
  task_id TEXT NOT NULL,
  run_id TEXT NOT NULL,
  task_completed BOOLEAN NOT NULL,
  execution_note TEXT,
  skill_applied BOOLEAN DEFAULT true,
  evolution_type TEXT CHECK (evolution_type IN ('fix', 'derived', 'captured', NULL)),
  evolution_direction TEXT,
  target_skill TEXT,
  analyzed_by TEXT DEFAULT 'gemini-flash',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_skill_analyses_skill ON skill_analyses(skill_name);
CREATE INDEX IF NOT EXISTS idx_skill_analyses_run ON skill_analyses(run_id);
CREATE INDEX IF NOT EXISTS idx_skill_analyses_created ON skill_analyses(created_at DESC);

COMMENT ON TABLE skill_analyses IS 'L3 post-execution analyzer results: task completion, skill application, evolution suggestions';
COMMENT ON COLUMN skill_analyses.evolution_type IS 'fix=repair in-place, derived=enhanced variant, captured=brand new pattern';
COMMENT ON COLUMN skill_analyses.evolution_direction IS 'What specifically to change in the skill';

-- ============================================================
-- 2. Skill Lineage DAG
-- ============================================================

CREATE TABLE IF NOT EXISTS skill_lineage (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  skill_id TEXT NOT NULL,
  skill_name TEXT NOT NULL,
  origin TEXT NOT NULL CHECK (origin IN ('imported', 'captured', 'derived', 'fixed')),
  generation INT DEFAULT 0,
  parent_skill_ids TEXT[] DEFAULT '{}',
  source_task_id TEXT,
  change_summary TEXT,
  content_hash TEXT,
  is_active BOOLEAN DEFAULT true,
  total_runs INT DEFAULT 0,
  total_pass INT DEFAULT 0,
  total_fail INT DEFAULT 0,
  pass_rate NUMERIC GENERATED ALWAYS AS (
    CASE WHEN total_runs > 0 THEN total_pass::numeric / total_runs ELSE 0 END
  ) STORED,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lineage_skill ON skill_lineage(skill_name);
CREATE INDEX IF NOT EXISTS idx_lineage_active ON skill_lineage(is_active);
CREATE INDEX IF NOT EXISTS idx_lineage_skill_id ON skill_lineage(skill_id);

COMMENT ON TABLE skill_lineage IS 'Skill version DAG: tracks evolution history, quality counters, content hashes';
COMMENT ON COLUMN skill_lineage.content_hash IS 'SHA256 of SKILL.md at this version — links to git commit';
COMMENT ON COLUMN skill_lineage.generation IS '0 = root/imported, N = generations of FIX/DERIVED evolution';
COMMENT ON COLUMN skill_lineage.pass_rate IS 'Computed: total_pass / total_runs';

-- ============================================================
-- 3. Seed lineage with current 5 Platform Skills as generation 0
-- ============================================================

INSERT INTO skill_lineage (skill_id, skill_name, origin, generation, change_summary)
VALUES
  ('zonewise-scraper__v1', 'zonewise-scraper', 'imported', 0, 'Initial import from .claude/rules/zonewise-scraper.md'),
  ('cost-discipline__v1',  'cost-discipline',  'imported', 0, 'Initial import from .claude/rules/cost-discipline.md'),
  ('honesty-protocol__v1', 'honesty-protocol', 'imported', 0, 'Initial import from .claude/rules/honesty-protocol.md'),
  ('brand-colors__v1',     'brand-colors',     'imported', 0, 'Initial import from .claude/rules/brand-colors.md'),
  ('ship-gate__v1',        'ship-gate',        'imported', 0, 'Initial import from .claude/rules/ship-gate.md')
ON CONFLICT DO NOTHING;

-- ============================================================
-- 4. View: Active skill lineage with pass rates
-- ============================================================

CREATE OR REPLACE VIEW active_skill_lineage AS
SELECT
  skill_name,
  skill_id,
  origin,
  generation,
  parent_skill_ids,
  content_hash,
  total_runs,
  total_pass,
  total_fail,
  ROUND(pass_rate * 100, 1) AS pass_rate_pct,
  created_at
FROM skill_lineage
WHERE is_active = true
ORDER BY skill_name, generation DESC;

COMMENT ON VIEW active_skill_lineage IS 'Latest active version per skill with pass rate %';

-- ============================================================
-- 5. RLS policies
-- ============================================================

ALTER TABLE skill_analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE skill_lineage ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_full_access_analyses" ON skill_analyses
  FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "service_full_access_lineage" ON skill_lineage
  FOR ALL USING (true) WITH CHECK (true);
