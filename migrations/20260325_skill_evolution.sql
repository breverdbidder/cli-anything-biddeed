-- Skill Evolution Table — tracks evolutionary tournament results across generations
-- Used by eval_runner.py evolve command + AUTOLOOP GHA

CREATE TABLE IF NOT EXISTS skill_evolution (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  skill_name TEXT NOT NULL,
  generation INTEGER NOT NULL,
  variant TEXT,
  pass_rate NUMERIC(5,4) NOT NULL,
  baseline_rate NUMERIC(5,4),
  failures JSONB DEFAULT '[]',
  failure_analysis JSONB DEFAULT '{}',
  bred_from TEXT[],
  is_production BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_skill_evolution_lookup
  ON skill_evolution(skill_name, generation DESC);
