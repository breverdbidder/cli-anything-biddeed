-- Migration: mcp_customers — WorkOS AuthKit OAuth wiring for biddeed-mcp
-- Created: 2026-07-01 | Idempotent: safe to re-run
--
-- Context: Sprint 2 — MCP server validates WorkOS-issued OAuth tokens (resource
-- server only, never issues tokens). First OAuth login upserts a row here with
-- stripe_customer_id left NULL; Sprint 3 links Stripe billing to this row.
--
-- CORRECTIVE NOTE: mcp_customers already existed in production (customer_id uuid
-- PK, tier_id FK → mcp_subscription_tiers, email UNIQUE, workos_user_id already
-- present but not unique). An earlier version of this migration incorrectly
-- assumed the table didn't exist and added redundant tier/call_count/
-- last_login_at columns alongside the real tier_id/updated_at. This version
-- drops that mistake and only adds what was actually missing: a UNIQUE
-- constraint on workos_user_id so OAuth login can upsert idempotently.

DO $mcp_customers$
BEGIN

-- Fresh-DB fallback — matches production schema. No-op if table already exists.
CREATE TABLE IF NOT EXISTS mcp_customers (
  customer_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email               TEXT NOT NULL UNIQUE,
  name                TEXT,
  customer_type       TEXT NOT NULL DEFAULT 'human'
                        CHECK (customer_type = ANY (ARRAY['human','agent','broker','enterprise'])),
  tier_id             TEXT NOT NULL DEFAULT 'free',
  stripe_customer_id  TEXT,
  workos_user_id      TEXT,
  api_key_hash        TEXT,
  counties_watched    TEXT[],
  s5_calls_used       INTEGER NOT NULL DEFAULT 0,
  s5_calls_quota      INTEGER NOT NULL DEFAULT 0,
  skip_credits_used   INTEGER NOT NULL DEFAULT 0,
  skip_credits_quota  INTEGER NOT NULL DEFAULT 0,
  active              BOOLEAN NOT NULL DEFAULT TRUE,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Undo the earlier mistaken ADD COLUMNs (redundant with tier_id/updated_at) —
-- safe: only just added, default-only values, nothing depends on them.
ALTER TABLE mcp_customers DROP COLUMN IF EXISTS tier;
ALTER TABLE mcp_customers DROP COLUMN IF EXISTS call_count;
ALTER TABLE mcp_customers DROP COLUMN IF EXISTS last_login_at;

-- workos_user_id already existed + indexed, but not unique — needed for
-- ON CONFLICT-style upsert on first OAuth login. Multiple NULLs remain
-- allowed (bd_*-key-only customers never linked to WorkOS).
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'mcp_customers_workos_user_id_key'
  ) THEN
    ALTER TABLE mcp_customers ADD CONSTRAINT mcp_customers_workos_user_id_key UNIQUE (workos_user_id);
  END IF;
END $$;

END $mcp_customers$;
