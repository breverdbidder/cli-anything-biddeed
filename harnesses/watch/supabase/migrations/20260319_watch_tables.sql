-- Claude Watch (Everest Edition) — Foundation Migration
-- Created: 2026-03-19
-- Harness: cli-anything-biddeed/harnesses/watch/

-- ==========================================================
-- TABLE: watch_sessions
-- ==========================================================
CREATE TABLE IF NOT EXISTS watch_sessions (
    id TEXT PRIMARY KEY,
    repo TEXT NOT NULL,
    branch TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'completed', 'stale')),
    summary TEXT,
    event_count INT DEFAULT 0,
    tool_breakdown JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_ws_status ON watch_sessions(status, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_ws_repo ON watch_sessions(repo, started_at DESC);

-- ==========================================================
-- TABLE: watch_events
-- ==========================================================
CREATE TABLE IF NOT EXISTS watch_events (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES watch_sessions(id) ON DELETE CASCADE,
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    hook_type TEXT NOT NULL
        CHECK (hook_type IN ('PostToolUse', 'Notification', 'Stop')),
    tool_name TEXT,
    file_path TEXT,
    input_data JSONB,
    output_data TEXT,
    diff TEXT,
    duration_ms INT
);

CREATE INDEX IF NOT EXISTS idx_we_session ON watch_events(session_id, ts ASC);
CREATE INDEX IF NOT EXISTS idx_we_ts ON watch_events(ts DESC);
CREATE INDEX IF NOT EXISTS idx_we_tool ON watch_events(tool_name, ts DESC);
CREATE INDEX IF NOT EXISTS idx_we_file ON watch_events(file_path) WHERE file_path IS NOT NULL;

-- ==========================================================
-- TABLE: watch_health
-- ==========================================================
CREATE TABLE IF NOT EXISTS watch_health (
    id BIGSERIAL PRIMARY KEY,
    scanned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    scan_type TEXT NOT NULL CHECK (scan_type IN ('nightly', 'session_start')),
    repo TEXT NOT NULL,
    file_path TEXT NOT NULL,
    category TEXT NOT NULL
        CHECK (category IN ('prompt', 'rules', 'config', 'docs', 'state')),
    content_hash TEXT NOT NULL,
    signals TEXT[],
    importance TEXT DEFAULT 'normal'
        CHECK (importance IN ('critical', 'high', 'normal')),
    line_count INT,
    size_bytes INT,
    content_preview TEXT
);

CREATE INDEX IF NOT EXISTS idx_wh_repo ON watch_health(repo, scanned_at DESC);
CREATE INDEX IF NOT EXISTS idx_wh_scan ON watch_health(scan_type, scanned_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_wh_latest ON watch_health(repo, file_path, scan_type, scanned_at DESC);

-- ==========================================================
-- RLS POLICIES
-- ==========================================================
ALTER TABLE watch_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE watch_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE watch_health ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'watch_sessions' AND policyname = 'auth_read'
  ) THEN
    CREATE POLICY "auth_read" ON watch_sessions FOR SELECT
        USING (auth.role() = 'authenticated');
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'watch_events' AND policyname = 'auth_read'
  ) THEN
    CREATE POLICY "auth_read" ON watch_events FOR SELECT
        USING (auth.role() = 'authenticated');
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'watch_health' AND policyname = 'auth_read'
  ) THEN
    CREATE POLICY "auth_read" ON watch_health FOR SELECT
        USING (auth.role() = 'authenticated');
  END IF;
END $$;

-- ==========================================================
-- DATA RETENTION (pg_cron)
-- ==========================================================
SELECT cron.schedule('watch-retention', '0 8 * * *', $$
    DELETE FROM watch_events WHERE ts < NOW() - INTERVAL '30 days';
    DELETE FROM watch_sessions WHERE ended_at < NOW() - INTERVAL '30 days';
    UPDATE watch_sessions SET status = 'stale', ended_at = NOW()
        WHERE status = 'active'
        AND started_at < NOW() - INTERVAL '30 minutes'
        AND id NOT IN (
            SELECT DISTINCT session_id FROM watch_events
            WHERE ts > NOW() - INTERVAL '30 minutes'
        );
    DELETE FROM watch_health WHERE scanned_at < NOW() - INTERVAL '90 days';
$$);

-- ==========================================================
-- VIEWS
-- ==========================================================
CREATE OR REPLACE VIEW watch_sessions_live AS
SELECT
    s.*,
    e.tool_name AS last_tool,
    e.file_path AS last_file,
    e.ts AS last_event_at
FROM watch_sessions s
LEFT JOIN LATERAL (
    SELECT tool_name, file_path, ts
    FROM watch_events
    WHERE session_id = s.id
    ORDER BY ts DESC LIMIT 1
) e ON true
WHERE s.status = 'active';

CREATE OR REPLACE VIEW watch_health_latest AS
SELECT DISTINCT ON (repo, file_path)
    *
FROM watch_health
WHERE scan_type = 'nightly'
ORDER BY repo, file_path, scanned_at DESC;

CREATE OR REPLACE VIEW watch_daily_stats AS
SELECT
    DATE(started_at) AS day,
    COUNT(*) AS session_count,
    SUM(event_count) AS total_events,
    AVG(EXTRACT(EPOCH FROM (ended_at - started_at))/60)::INT AS avg_duration_min
FROM watch_sessions
WHERE started_at > NOW() - INTERVAL '30 days'
GROUP BY DATE(started_at)
ORDER BY day DESC;
