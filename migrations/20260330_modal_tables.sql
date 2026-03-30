-- Migration: Modal Infrastructure Tables
-- Date: 2026-03-30
-- Issue: breverdbidder/cli-anything-biddeed#66
-- Purpose: modal_runs (execution audit log) + vault_sync_log (Google Drive sync history)

-- ============================================================
-- 1. modal_runs — log every Modal function execution
-- ============================================================

CREATE TABLE IF NOT EXISTS modal_runs (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT now(),
  ran_at TIMESTAMPTZ DEFAULT now(),
  run_type TEXT NOT NULL
    CHECK (run_type IN ('nightly_scorer', 'vault_sync', 'county_scraper', 'xgboost_retrain', 'executor')),
  status TEXT DEFAULT 'completed'
    CHECK (status IN ('started', 'completed', 'failed', 'partial')),
  -- scoring runs
  tasks_scored INTEGER,
  tasks_updated INTEGER,
  top_task_id TEXT,
  top_score NUMERIC(5, 1),
  -- scraper runs
  county TEXT,
  parcels_fetched INTEGER,
  parcels_upserted INTEGER,
  -- generic
  duration_seconds NUMERIC(8, 2),
  error_message TEXT,
  metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS modal_runs_run_type_idx ON modal_runs (run_type);
CREATE INDEX IF NOT EXISTS modal_runs_ran_at_idx ON modal_runs (ran_at DESC);
CREATE INDEX IF NOT EXISTS modal_runs_status_idx ON modal_runs (status);

-- ============================================================
-- 2. vault_sync_log — track every Google Drive sync cycle
-- ============================================================

CREATE TABLE IF NOT EXISTS vault_sync_log (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT now(),
  synced_at TIMESTAMPTZ DEFAULT now(),
  status TEXT DEFAULT 'completed'
    CHECK (status IN ('started', 'completed', 'failed', 'skipped')),
  files_synced INTEGER DEFAULT 0,
  files_skipped INTEGER DEFAULT 0,
  files_failed INTEGER DEFAULT 0,
  bytes_transferred BIGINT DEFAULT 0,
  drive_folder_id TEXT,
  sync_duration_seconds NUMERIC(8, 2),
  error_message TEXT,
  metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS vault_sync_log_synced_at_idx ON vault_sync_log (synced_at DESC);
CREATE INDEX IF NOT EXISTS vault_sync_log_status_idx ON vault_sync_log (status);

-- Row-level security (match existing table conventions)
ALTER TABLE modal_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE vault_sync_log ENABLE ROW LEVEL SECURITY;

-- Service role has full access (GHA workflows use service role key)
CREATE POLICY IF NOT EXISTS "service_role_all_modal_runs"
  ON modal_runs FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

CREATE POLICY IF NOT EXISTS "service_role_all_vault_sync_log"
  ON vault_sync_log FOR ALL
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');
