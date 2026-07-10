-- Production Studio: BriefAgent table
-- Run via Supabase SQL Editor or CC on Hetzner

CREATE TABLE IF NOT EXISTS production_briefs (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  project_id TEXT UNIQUE NOT NULL,
  raw_input TEXT NOT NULL,
  structured_brief JSONB NOT NULL,
  status TEXT DEFAULT 'pending_approval' 
    CHECK (status IN ('pending_approval','approved','revised','rejected')),
  ariel_notes TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE production_briefs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access" ON production_briefs
  FOR ALL USING (auth.role() = 'service_role');

-- Index for quick lookups
CREATE INDEX IF NOT EXISTS idx_production_briefs_status ON production_briefs(status);
CREATE INDEX IF NOT EXISTS idx_production_briefs_project_id ON production_briefs(project_id);
