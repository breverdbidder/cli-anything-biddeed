-- Migration: Stripe paywall — lookup counter + pro session tracking
-- Issue: breverdbidder/cli-anything-biddeed#93
-- Created: 2026-03-30

CREATE TABLE IF NOT EXISTS paywall_sessions (
    id                  BIGSERIAL PRIMARY KEY,
    session_id          TEXT NOT NULL UNIQUE,
    lookup_count        INT NOT NULL DEFAULT 0,
    is_pro              BOOLEAN NOT NULL DEFAULT FALSE,
    stripe_customer_id  TEXT,
    stripe_sub_id       TEXT,
    last_lookup_at      TIMESTAMPTZ,
    pro_since           TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ps_session_id  ON paywall_sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_ps_is_pro      ON paywall_sessions(is_pro);
CREATE INDEX IF NOT EXISTS idx_ps_customer    ON paywall_sessions(stripe_customer_id);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_paywall_session_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_ps_updated_at ON paywall_sessions;
CREATE TRIGGER trg_ps_updated_at
    BEFORE UPDATE ON paywall_sessions
    FOR EACH ROW EXECUTE FUNCTION update_paywall_session_updated_at();

-- View: quick paywall status per session
CREATE OR REPLACE VIEW paywall_status AS
SELECT
    session_id,
    lookup_count,
    is_pro,
    CASE
        WHEN is_pro THEN 'pro'
        WHEN lookup_count >= 3 THEN 'blocked'
        ELSE 'free'
    END AS status,
    3 - LEAST(lookup_count, 3) AS lookups_remaining,
    last_lookup_at,
    created_at
FROM paywall_sessions;
