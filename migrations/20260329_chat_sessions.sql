-- Chat Sessions Intelligence Table for XGBoost Training
-- Created: 2026-03-29
-- Purpose: Store structured chat data for ML priority scoring

CREATE TABLE IF NOT EXISTS chat_sessions (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT now(),
  
  -- Identity
  chat_id TEXT UNIQUE NOT NULL,
  chat_url TEXT NOT NULL,
  
  -- Temporal (XGBoost time features)
  chat_date DATE NOT NULL,
  chat_time_start TIMESTAMPTZ,
  chat_time_end TIMESTAMPTZ,
  chat_duration_minutes INTEGER DEFAULT 0,
  chat_month INTEGER NOT NULL,
  day_of_week INTEGER DEFAULT 0,
  hour_of_day INTEGER DEFAULT 0,
  
  -- Content
  title TEXT,
  summary TEXT,
  summary_length INTEGER DEFAULT 0,
  
  -- Domain classification
  domain_primary TEXT NOT NULL DEFAULT 'ECOSYSTEM',
  domain_secondary TEXT,
  
  -- Output metrics (XGBoost productivity features)
  tools_used_count INTEGER DEFAULT 0,
  artifacts_created INTEGER DEFAULT 0,
  summits_dispatched INTEGER DEFAULT 0,
  tasks_created INTEGER DEFAULT 0,
  tasks_completed INTEGER DEFAULT 0,
  code_shipped BOOLEAN DEFAULT false,
  
  -- Quality signals (XGBoost target + features)
  frustration_level INTEGER DEFAULT 0,
  ariel_corrections INTEGER DEFAULT 0,
  strategic_decisions INTEGER DEFAULT 0,
  
  -- Extracted intelligence
  keywords TEXT[] DEFAULT '{}',
  competitors_mentioned TEXT[] DEFAULT '{}',
  repos_touched TEXT[] DEFAULT '{}',
  
  -- ML scoring (filled by Gemini nightly)
  outcome_quality INTEGER,
  gemini_analysis JSONB DEFAULT '{}',
  
  -- Backfill tracking
  backfill_month TEXT,
  processed_by_gemini BOOLEAN DEFAULT false,
  processed_by_xgboost BOOLEAN DEFAULT false
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_date ON chat_sessions(chat_date);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_month ON chat_sessions(chat_month);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_domain ON chat_sessions(domain_primary);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_quality ON chat_sessions(outcome_quality);
