-- Production Studio: ScriptwriterAgent table
CREATE TABLE IF NOT EXISTS production_scripts (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  project_id TEXT NOT NULL,
  brief_id UUID,
  script_version INT DEFAULT 1,
  voiceover_text TEXT NOT NULL,
  scenes JSONB NOT NULL,
  total_words INT,
  estimated_duration_seconds NUMERIC,
  words_per_second NUMERIC DEFAULT 2.5,
  status TEXT DEFAULT 'draft' CHECK (status IN ('draft','approved','revised')),
  created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE production_scripts ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role full access" ON production_scripts FOR ALL USING (auth.role() = 'service_role');
CREATE INDEX IF NOT EXISTS idx_production_scripts_project ON production_scripts(project_id);
