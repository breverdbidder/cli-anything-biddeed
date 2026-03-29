-- chat_sessions ALTER TABLE — add columns missing from initial 26-feature schema
-- Safe to run multiple times (uses ADD COLUMN IF NOT EXISTS)
-- Created: 2026-03-29 (Issue #30)

-- Temporal features
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS chat_date DATE;
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS chat_time_start TIMESTAMPTZ;
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS chat_time_end TIMESTAMPTZ;
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS chat_duration_minutes INTEGER DEFAULT 0;
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS chat_month INTEGER;
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS day_of_week INTEGER DEFAULT 0;
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS hour_of_day INTEGER DEFAULT 0;

-- Content
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS title TEXT;
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS summary TEXT;
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS summary_length INTEGER DEFAULT 0;

-- Domain
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS domain_primary TEXT NOT NULL DEFAULT 'ECOSYSTEM';
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS domain_secondary TEXT;

-- Output metrics
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS tools_used_count INTEGER DEFAULT 0;
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS artifacts_created INTEGER DEFAULT 0;
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS summits_dispatched INTEGER DEFAULT 0;
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS tasks_created INTEGER DEFAULT 0;
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS tasks_completed INTEGER DEFAULT 0;
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS code_shipped BOOLEAN DEFAULT false;

-- Quality signals
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS frustration_level INTEGER DEFAULT 0;
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS ariel_corrections INTEGER DEFAULT 0;
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS strategic_decisions INTEGER DEFAULT 0;

-- Arrays
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS keywords TEXT[] DEFAULT '{}';
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS competitors_mentioned TEXT[] DEFAULT '{}';
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS repos_touched TEXT[] DEFAULT '{}';

-- ML
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS outcome_quality INTEGER;
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS gemini_analysis JSONB DEFAULT '{}';

-- Backfill
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS backfill_month TEXT;
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS processed_by_gemini BOOLEAN DEFAULT false;
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS processed_by_xgboost BOOLEAN DEFAULT false;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_chat_sessions_date ON chat_sessions(chat_date);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_month ON chat_sessions(chat_month);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_domain ON chat_sessions(domain_primary);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_quality ON chat_sessions(outcome_quality);
