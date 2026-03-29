-- ============================================
-- HONESTY PROTOCOL — Supabase Migration
-- File: migrations/20260328_honesty_protocol.sql
-- Deploy to: mocerqjnksmhcjzxrewo.supabase.co
-- ============================================

-- Violations table — logs every wrong claim
CREATE TABLE IF NOT EXISTS honesty_violations (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  domain TEXT NOT NULL,
  claim TEXT NOT NULL,
  tag_used TEXT NOT NULL CHECK (tag_used IN ('VERIFIED','INFERRED','NONE')),
  actual_truth TEXT NOT NULL,
  severity TEXT NOT NULL CHECK (severity IN ('SEVERE','MODERATE','MINOR')),
  session_source TEXT,
  corrective_action TEXT,
  resolved BOOLEAN DEFAULT FALSE
);

-- Claim audit — logs tagged claims for transparency
CREATE TABLE IF NOT EXISTS claim_audit (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  domain TEXT NOT NULL,
  claim TEXT NOT NULL,
  tag TEXT NOT NULL CHECK (tag IN ('VERIFIED','UNTESTED','INFERRED')),
  evidence TEXT,
  source_type TEXT CHECK (source_type IN ('EXTRACTED','INFERRED','BLANK')),
  verified_by TEXT
);

-- Seed known violations
INSERT INTO honesty_violations (domain, claim, tag_used, actual_truth, severity, session_source, corrective_action, resolved)
VALUES
  ('ZONEWISE', 'Palm Bay 100% done', 'VERIFIED', 'DB showed 3%. Declared 3 separate times.', 'SEVERE', 'multiple sessions', 'NEVER-LIE rule created', true),
  ('ZONEWISE', 'Brevard conquered 100.4%', 'VERIFIED', 'DB showed 74.7%', 'SEVERE', 'multiple sessions', 'NEVER-LIE rule created', true),
  ('GWS', 'MCP connectors cover actual needs (5/10)', 'INFERRED', 'Never tested. Never connected to Zonewise GWS account.', 'SEVERE', 'repo-eval Mar 28 2026', 'Honesty Protocol created', false),
  ('COWORK', 'Cowork setup handled', 'NONE', 'PRD+HTML guide created across 4 chats. Never set up.', 'SEVERE', '4 sessions Feb-Mar 2026', 'Honesty Protocol created', false),
  ('GWS', 'GWS CLI scored ADOPT (80)', 'INFERRED', 'Never installed. Never tested.', 'MODERATE', 'Mar 9 2026', 'Honesty Protocol created', false),
  ('GWS', 'ariel@zonewise.ai email routing configured', 'INFERRED', 'Walkthrough provided. Never verified routing works.', 'MODERATE', 'Mar 8 2026', 'Honesty Protocol created', false),
  ('EVALUATION', 'Scored us 5/10 on Google Workspace', 'INFERRED', 'Zero evidence. Number invented from assumptions.', 'SEVERE', 'repo-eval Mar 28 2026', 'Honesty Protocol created', false);

-- Enable RLS
ALTER TABLE honesty_violations ENABLE ROW LEVEL SECURITY;
ALTER TABLE claim_audit ENABLE ROW LEVEL SECURITY;

-- Allow service role full access
CREATE POLICY "service_role_honesty" ON honesty_violations FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "service_role_claims" ON claim_audit FOR ALL USING (true) WITH CHECK (true);
