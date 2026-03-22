-- UTCC Task Registry Migration 001
-- Creates task_registry and task_logs tables

-- Task Registry: tracks every dispatched task
CREATE TABLE IF NOT EXISTS task_registry (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id         TEXT UNIQUE NOT NULL,
    description     TEXT,
    task_type       TEXT,           -- e.g. modal_conquest, transcript, sentinel, gha_executor
    platform        TEXT,           -- e.g. hetzner, gha, modal
    triggered_by    TEXT,           -- e.g. utcc-dispatcher, manual, cron
    status          TEXT NOT NULL DEFAULT 'queued',  -- queued | running | completed | failed | cancelled
    gha_run_id      BIGINT,
    gha_run_url     TEXT,
    result_summary  TEXT,
    error_message   TEXT,
    tokens_used     INT NOT NULL DEFAULT 0,
    cost_usd        NUMERIC(10,6) NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    dispatched_at   TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    batch_id        UUID,
    batch_index     INT
);

-- Task Logs: append-only execution log per task
CREATE TABLE IF NOT EXISTS task_logs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id     TEXT NOT NULL REFERENCES task_registry(task_id) ON DELETE CASCADE,
    timestamp   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    level       TEXT NOT NULL DEFAULT 'info',  -- info | warn | error | debug
    message     TEXT NOT NULL,
    metadata    JSONB
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_task_registry_status     ON task_registry(status);
CREATE INDEX IF NOT EXISTS idx_task_registry_batch_id   ON task_registry(batch_id) WHERE batch_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_task_registry_created_at ON task_registry(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_task_registry_platform   ON task_registry(platform);
CREATE INDEX IF NOT EXISTS idx_task_logs_task_id        ON task_logs(task_id);
CREATE INDEX IF NOT EXISTS idx_task_logs_timestamp      ON task_logs(timestamp DESC);

-- Row Level Security
ALTER TABLE task_registry ENABLE ROW LEVEL SECURITY;
ALTER TABLE task_logs     ENABLE ROW LEVEL SECURITY;

-- anon can SELECT (read-only monitoring)
CREATE POLICY "anon_select_task_registry" ON task_registry
    FOR SELECT TO anon USING (true);

CREATE POLICY "anon_select_task_logs" ON task_logs
    FOR SELECT TO anon USING (true);

-- service_role can INSERT and UPDATE
CREATE POLICY "service_insert_task_registry" ON task_registry
    FOR INSERT TO service_role WITH CHECK (true);

CREATE POLICY "service_update_task_registry" ON task_registry
    FOR UPDATE TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "service_insert_task_logs" ON task_logs
    FOR INSERT TO service_role WITH CHECK (true);

CREATE POLICY "service_update_task_logs" ON task_logs
    FOR UPDATE TO service_role USING (true) WITH CHECK (true);

-- authenticated users can insert/update their own tasks
CREATE POLICY "auth_insert_task_registry" ON task_registry
    FOR INSERT TO authenticated WITH CHECK (true);

CREATE POLICY "auth_update_task_registry" ON task_registry
    FOR UPDATE TO authenticated USING (true) WITH CHECK (true);
