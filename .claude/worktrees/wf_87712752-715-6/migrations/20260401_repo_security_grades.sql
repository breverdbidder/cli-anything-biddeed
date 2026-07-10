-- AgentShield Security Grades Table
-- Created: 2026-04-01 (SUMMIT #123)
CREATE TABLE IF NOT EXISTS public.repo_security_grades (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  repo_name text NOT NULL,
  grade char(2) NOT NULL,
  score integer NOT NULL,
  critical_count integer DEFAULT 0,
  high_count integer DEFAULT 0,
  medium_count integer DEFAULT 0,
  scan_date timestamptz DEFAULT now(),
  findings_json jsonb
);

-- Index for fast lookups by repo + date
CREATE INDEX IF NOT EXISTS idx_rsg_repo_date ON public.repo_security_grades(repo_name, scan_date DESC);
