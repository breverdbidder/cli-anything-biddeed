-- Migration: deployment_checks + deployment_incidents tables
-- Issue: breverdbidder/cli-anything-biddeed#101
-- Created: 2026-03-30

-- deployment_checks: raw verification results from verify_deployment.py
CREATE TABLE IF NOT EXISTS deployment_checks (
    id              BIGSERIAL PRIMARY KEY,
    url             TEXT NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('pass', 'fail', 'error')),
    http_code       INT,
    load_ms         FLOAT,
    checks_json     JSONB,          -- array of {name, passed, detail}
    errors_json     JSONB,          -- array of error strings
    has_screenshot  BOOLEAN DEFAULT FALSE,
    verified_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dc_url        ON deployment_checks(url);
CREATE INDEX IF NOT EXISTS idx_dc_status     ON deployment_checks(status);
CREATE INDEX IF NOT EXISTS idx_dc_verified   ON deployment_checks(verified_at DESC);

-- deployment_incidents: critical signals + repair actions from auto_repair.py
CREATE TABLE IF NOT EXISTS deployment_incidents (
    id              BIGSERIAL PRIMARY KEY,
    url             TEXT NOT NULL,
    signal_type     TEXT NOT NULL,
    severity        TEXT NOT NULL CHECK (severity IN ('critical', 'warning', 'info')),
    message         TEXT,
    evidence        TEXT,
    suggestion      TEXT,
    issue_url       TEXT,           -- GitHub issue URL if auto-created
    resolved        BOOLEAN DEFAULT FALSE,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_di_url        ON deployment_incidents(url);
CREATE INDEX IF NOT EXISTS idx_di_signal     ON deployment_incidents(signal_type);
CREATE INDEX IF NOT EXISTS idx_di_severity   ON deployment_incidents(severity);
CREATE INDEX IF NOT EXISTS idx_di_resolved   ON deployment_incidents(resolved);
CREATE INDEX IF NOT EXISTS idx_di_occurred   ON deployment_incidents(occurred_at DESC);

-- View: latest check per URL
CREATE OR REPLACE VIEW latest_deployment_checks AS
SELECT DISTINCT ON (url)
    id, url, status, http_code, load_ms, verified_at
FROM deployment_checks
ORDER BY url, verified_at DESC;
