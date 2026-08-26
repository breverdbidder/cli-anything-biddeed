-- Migration: log_funnel_execution — tracks every run_daily_funnel MCP call
-- Issue: breverdbidder/cli-anything-biddeed#19480
-- Day 2 deliverable

CREATE TABLE IF NOT EXISTS log_funnel_execution (
    id              BIGSERIAL PRIMARY KEY,
    run_id          TEXT NOT NULL DEFAULT gen_random_uuid()::TEXT,
    triggered_by    TEXT NOT NULL DEFAULT 'mcp_tool',
    dry_run         BOOLEAN NOT NULL DEFAULT FALSE,
    snapshot_count  INT,
    lead_count      INT,
    sent_count      INT,
    failed_count    INT,
    status          TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','running','completed','failed')),
    error_message   TEXT,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    duration_ms     INT GENERATED ALWAYS AS (
                        CASE WHEN completed_at IS NOT NULL
                             THEN EXTRACT(EPOCH FROM (completed_at - started_at))::INT * 1000
                             ELSE NULL
                        END
                    ) STORED,
    evidence        JSONB
);

CREATE INDEX IF NOT EXISTS idx_lfe_run_id     ON log_funnel_execution(run_id);
CREATE INDEX IF NOT EXISTS idx_lfe_started_at ON log_funnel_execution(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_lfe_status     ON log_funnel_execution(status);
