-- Migration: ACTION-PLAN-V2 Tables
-- Date: 2026-03-29
-- Issue: breverdbidder/cli-anything-biddeed#21
-- Purpose: Intelligent Task Engine — artifact vault, carryforward, daily digest

-- ============================================================
-- 1. artifact_vault — track every deliverable
-- ============================================================

CREATE TABLE IF NOT EXISTS artifact_vault (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  title TEXT NOT NULL,
  description TEXT,
  artifact_type TEXT NOT NULL
    CHECK (artifact_type IN ('html','jsx','docx','spec','sql','script','report','analysis')),
  domain TEXT NOT NULL
    CHECK (domain IN ('BIDDEED','ZONEWISE','GTM','MICHAEL','PROPERTY','PERSONAL','ECOSYSTEM')),
  status TEXT DEFAULT 'created'
    CHECK (status IN ('created','deployed','buried','archived','superseded')),
  deploy_url TEXT,
  source_chat_url TEXT,
  source_repo TEXT,
  source_path TEXT,
  importance INTEGER DEFAULT 5 CHECK (importance >= 1 AND importance <= 10),
  last_referenced TIMESTAMPTZ,
  tags TEXT[],
  metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_artifact_vault_status ON artifact_vault(status);
CREATE INDEX IF NOT EXISTS idx_artifact_vault_domain ON artifact_vault(domain);
CREATE INDEX IF NOT EXISTS idx_artifact_vault_importance ON artifact_vault(importance DESC);

ALTER TABLE artifact_vault ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_full_access_artifact_vault" ON artifact_vault
  FOR ALL USING (true) WITH CHECK (true);

COMMENT ON TABLE artifact_vault IS 'Every deliverable created across Claude AI and Claude Code sessions';

-- ============================================================
-- 2. task_carryforward — daily task lifecycle with escalation
-- ============================================================

CREATE TABLE IF NOT EXISTS task_carryforward (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  task_id TEXT NOT NULL,
  date DATE NOT NULL,
  status TEXT NOT NULL
    CHECK (status IN ('new','carried','escalated','completed','dropped')),
  carry_count INTEGER DEFAULT 0,
  escalation_level INTEGER DEFAULT 0 CHECK (escalation_level >= 0 AND escalation_level <= 3),
  verified BOOLEAN DEFAULT false,
  verification_method TEXT
    CHECK (verification_method IS NULL OR verification_method IN ('curl','db_query','visual','self_report')),
  verification_proof TEXT,
  ml_priority_score FLOAT CHECK (ml_priority_score IS NULL OR (ml_priority_score >= 0 AND ml_priority_score <= 100)),
  ml_factors JSONB,
  notes TEXT,
  UNIQUE(task_id, date)
);

CREATE INDEX IF NOT EXISTS idx_carryforward_date ON task_carryforward(date DESC);
CREATE INDEX IF NOT EXISTS idx_carryforward_task ON task_carryforward(task_id);
CREATE INDEX IF NOT EXISTS idx_carryforward_status ON task_carryforward(status);

ALTER TABLE task_carryforward ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_full_access_carryforward" ON task_carryforward
  FOR ALL USING (true) WITH CHECK (true);

COMMENT ON TABLE task_carryforward IS 'Daily task lifecycle — carryforward, escalation, ML scoring, verification';

-- ============================================================
-- 3. daily_digest — searchable daily plan archive
-- ============================================================

CREATE TABLE IF NOT EXISTS daily_digest (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  date DATE NOT NULL UNIQUE,
  created_at TIMESTAMPTZ DEFAULT now(),
  digest_text TEXT NOT NULL,
  stats JSONB NOT NULL DEFAULT '{}',
  artifacts_referenced UUID[],
  domains_covered TEXT[],
  honesty_score FLOAT CHECK (honesty_score IS NULL OR (honesty_score >= 0 AND honesty_score <= 1)),
  carryforward_count INTEGER DEFAULT 0,
  streak_days INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_daily_digest_date ON daily_digest(date DESC);

ALTER TABLE daily_digest ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_full_access_daily_digest" ON daily_digest
  FOR ALL USING (true) WITH CHECK (true);

COMMENT ON TABLE daily_digest IS 'Full rendered daily digest — searchable, auditable, honesty-scored';

-- ============================================================
-- 4. Seed artifact_vault with 8 known buried artifacts
-- ============================================================

INSERT INTO artifact_vault (title, artifact_type, domain, status, importance, source_chat_url, tags) VALUES
(
  '8-Competitor Analysis (Gridics/Zoneomics/TestFit/PropertyOnion/Algoma/ArkDesign/Reventure)',
  'jsx', 'GTM', 'buried', 10,
  'https://claude.ai/chat/7fb28289-1dc6-40ad-8d96-b13b0eea22b7',
  ARRAY['competitive-intel','investor','gtm']
),
(
  'Algoma Full CI Report (PRD/PRS/SWOT/Battle Card)',
  'md', 'GTM', 'deployed', 9,
  'docs/plans/ALGOMA-CI-REPORT.md',
  ARRAY['competitive-intel','algoma']
),
(
  'TestFit CI Report',
  'docx', 'GTM', 'buried', 8,
  'https://claude.ai/chat/4144bbb3-9386-4f21-8611-45e0ecba894e',
  ARRAY['competitive-intel','testfit']
),
(
  'ZoneWise 20 Data Phases Comparison',
  'docx', 'ZONEWISE', 'buried', 9,
  'https://claude.ai/chat/b2c0ea12-84c5-4f43-b2dc-0f018f1c7421',
  ARRAY['competitive-intel','data-phases','roadmap']
),
(
  'HONESTY-PROTOCOL.md',
  'spec', 'ECOSYSTEM', 'deployed', 10,
  'https://claude.ai/chat/64e02f30-1ac3-42fe-bfe1-7b8e9139bf29',
  ARRAY['protocol','enforcement']
),
(
  'AUTOLOOP L3 Spec',
  'spec', 'ECOSYSTEM', 'deployed', 8,
  'https://claude.ai/chat/f896c220-4c63-40d7-a808-66683974e8cd',
  ARRAY['autoloop','ml']
),
(
  'DesignWise V3 Spec',
  'spec', 'ECOSYSTEM', 'created', 8,
  NULL,
  ARRAY['designwise','agents']
),
(
  'CODESEARCH Spec',
  'spec', 'ECOSYSTEM', 'created', 7,
  'https://claude.ai/chat/86396d07-a854-4579-95a0-2ed65ef3aca0',
  ARRAY['codesearch','search']
)
ON CONFLICT DO NOTHING;
