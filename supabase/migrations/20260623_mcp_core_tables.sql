-- Migration: MCP core tables — API keys, billing events, beta invites, taxi meter
-- Created: 2026-06-23 | Idempotent: safe to re-run, handles pre-existing tables

DO $mcp$
BEGIN

-- ── mcp_api_keys ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS mcp_api_keys (
  id                BIGSERIAL PRIMARY KEY,
  key_hash          TEXT NOT NULL UNIQUE,
  key_prefix        TEXT NOT NULL,
  customer_id       TEXT NOT NULL,
  tier              TEXT NOT NULL DEFAULT 'investor',
  product           TEXT NOT NULL DEFAULT 'biddeed',
  rate_limit_hr     INTEGER NOT NULL DEFAULT 100,
  daily_s1_limit    INTEGER NOT NULL DEFAULT 50,
  is_active         BOOLEAN NOT NULL DEFAULT TRUE,
  stripe_customer_id TEXT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at        TIMESTAMPTZ,
  last_used_at      TIMESTAMPTZ,
  call_count        BIGINT NOT NULL DEFAULT 0
);

-- Add any columns that may be missing on a pre-existing table
ALTER TABLE mcp_api_keys ADD COLUMN IF NOT EXISTS tier               TEXT NOT NULL DEFAULT 'investor';
ALTER TABLE mcp_api_keys ADD COLUMN IF NOT EXISTS product            TEXT NOT NULL DEFAULT 'biddeed';
ALTER TABLE mcp_api_keys ADD COLUMN IF NOT EXISTS rate_limit_hr      INTEGER NOT NULL DEFAULT 100;
ALTER TABLE mcp_api_keys ADD COLUMN IF NOT EXISTS daily_s1_limit     INTEGER NOT NULL DEFAULT 50;
ALTER TABLE mcp_api_keys ADD COLUMN IF NOT EXISTS is_active          BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE mcp_api_keys ADD COLUMN IF NOT EXISTS stripe_customer_id TEXT;
ALTER TABLE mcp_api_keys ADD COLUMN IF NOT EXISTS expires_at         TIMESTAMPTZ;
ALTER TABLE mcp_api_keys ADD COLUMN IF NOT EXISTS last_used_at       TIMESTAMPTZ;
ALTER TABLE mcp_api_keys ADD COLUMN IF NOT EXISTS call_count         BIGINT NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_mcp_api_keys_hash     ON mcp_api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_mcp_api_keys_customer ON mcp_api_keys(customer_id);
CREATE INDEX IF NOT EXISTS idx_mcp_api_keys_tier     ON mcp_api_keys(tier);

-- ── billing_events ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS billing_events (
  id                      BIGSERIAL PRIMARY KEY,
  tool_name               TEXT NOT NULL,
  stream_id               TEXT NOT NULL,
  customer_id             TEXT NOT NULL,
  key_prefix              TEXT NOT NULL,
  unit_price_usd          NUMERIC(10,4) NOT NULL,
  billed_amount           NUMERIC(10,4) NOT NULL,
  quantity                INTEGER NOT NULL DEFAULT 1,
  settled                 BOOLEAN NOT NULL DEFAULT FALSE,
  cert_status             TEXT,
  county                  TEXT,
  params                  JSONB,
  result_summary          TEXT,
  stripe_usage_record_id  TEXT,
  created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  settled_at              TIMESTAMPTZ
);

ALTER TABLE billing_events ADD COLUMN IF NOT EXISTS cert_status            TEXT;
ALTER TABLE billing_events ADD COLUMN IF NOT EXISTS county                 TEXT;
ALTER TABLE billing_events ADD COLUMN IF NOT EXISTS params                 JSONB;
ALTER TABLE billing_events ADD COLUMN IF NOT EXISTS result_summary         TEXT;
ALTER TABLE billing_events ADD COLUMN IF NOT EXISTS stripe_usage_record_id TEXT;
ALTER TABLE billing_events ADD COLUMN IF NOT EXISTS settled_at             TIMESTAMPTZ;
ALTER TABLE billing_events ADD COLUMN IF NOT EXISTS key_prefix             TEXT NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_billing_events_customer ON billing_events(customer_id);
CREATE INDEX IF NOT EXISTS idx_billing_events_stream   ON billing_events(stream_id);
CREATE INDEX IF NOT EXISTS idx_billing_events_tool     ON billing_events(tool_name);
CREATE INDEX IF NOT EXISTS idx_billing_events_created  ON billing_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_billing_events_settled  ON billing_events(settled) WHERE settled = FALSE;

-- ── beta_invites ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS beta_invites (
  id              BIGSERIAL PRIMARY KEY,
  customer_id     TEXT NOT NULL UNIQUE,
  name            TEXT NOT NULL,
  email           TEXT NOT NULL UNIQUE,
  invite_code     TEXT NOT NULL UNIQUE,
  cohort          TEXT NOT NULL DEFAULT 'wave1_brevard_duval',
  counties_active TEXT[] NOT NULL DEFAULT '{}',
  tier            TEXT NOT NULL DEFAULT 'pro',
  api_key_prefix  TEXT,
  invited_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  activated_at    TIMESTAMPTZ,
  notes           TEXT
);

ALTER TABLE beta_invites ADD COLUMN IF NOT EXISTS tier           TEXT NOT NULL DEFAULT 'pro';
ALTER TABLE beta_invites ADD COLUMN IF NOT EXISTS cohort         TEXT NOT NULL DEFAULT 'wave1_brevard_duval';
ALTER TABLE beta_invites ADD COLUMN IF NOT EXISTS counties_active TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE beta_invites ADD COLUMN IF NOT EXISTS api_key_prefix TEXT;
ALTER TABLE beta_invites ADD COLUMN IF NOT EXISTS activated_at   TIMESTAMPTZ;
ALTER TABLE beta_invites ADD COLUMN IF NOT EXISTS notes          TEXT;

CREATE INDEX IF NOT EXISTS idx_beta_invites_email  ON beta_invites(email);
CREATE INDEX IF NOT EXISTS idx_beta_invites_code   ON beta_invites(invite_code);
CREATE INDEX IF NOT EXISTS idx_beta_invites_cohort ON beta_invites(cohort);

-- ── taxi_meter_streams ────────────────────────────────────────────────────────
-- Config table (6 rows, no user data) — drop+recreate to clear any partial schema.
-- CASCADE drops dependent view (v_revenue_by_stream) + FK constraints on other tables.
DROP TABLE IF EXISTS taxi_meter_tools CASCADE;
DROP TABLE IF EXISTS taxi_meter_streams CASCADE;

CREATE TABLE taxi_meter_streams (
  id             BIGSERIAL PRIMARY KEY,
  stream_id      TEXT NOT NULL UNIQUE,
  name           TEXT NOT NULL,
  unit_price_usd NUMERIC(10,4) NOT NULL,
  gate_tier      TEXT NOT NULL,
  billing_type   TEXT NOT NULL DEFAULT 'per_call',
  stripe_metered BOOLEAN NOT NULL DEFAULT FALSE,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO taxi_meter_streams (stream_id, name, unit_price_usd, gate_tier, billing_type, stripe_metered) VALUES
  ('s1',  'Discovery',       0.0500, 'free',       'per_call',       FALSE),
  ('s2',  'Qualification',   0.4000, 'investor',   'per_call',       FALSE),
  ('s3',  'Fusion',          5.0000, 'pro',        'per_call',       FALSE),
  ('s4',  'Monitoring',      0.0000, 'pro',        'subscription',   FALSE),
  ('s5',  'Shapira Formula', 25.0000,'pro',        'per_call',       TRUE),
  ('fee', 'Close-and-Fee',   0.0000, 'enterprise', 'transaction_pct',FALSE);

-- ── taxi_meter_tools ──────────────────────────────────────────────────────────
-- Config table (25 rows, no user data) — recreated above via DROP
CREATE TABLE taxi_meter_tools (
  id         BIGSERIAL PRIMARY KEY,
  tool_name  TEXT NOT NULL UNIQUE,
  stream_id  TEXT NOT NULL,
  gate_cert  BOOLEAN NOT NULL DEFAULT FALSE,
  product    TEXT NOT NULL DEFAULT 'biddeed',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO taxi_meter_tools (tool_name, stream_id, gate_cert, product) VALUES
  ('search_auctions',          's1', FALSE, 'biddeed'),
  ('get_auction_detail',       's1', FALSE, 'biddeed'),
  ('browse_deals',             's1', FALSE, 'biddeed'),
  ('get_deposit_requirements', 's1', FALSE, 'biddeed'),
  ('find_local_partners',      's1', FALSE, 'biddeed'),
  ('get_interest_rate',        's1', FALSE, 'biddeed'),
  ('search_properties',        's1', FALSE, 'biddeed'),
  ('search_distressed',        's2', FALSE, 'biddeed'),
  ('get_owner_intel',          's2', FALSE, 'biddeed'),
  ('get_lien_stack',           's2', FALSE, 'biddeed'),
  ('get_rent_estimate',        's2', FALSE, 'biddeed'),
  ('analyze_market',           's2', FALSE, 'biddeed'),
  ('get_zip_market_data',      's2', FALSE, 'biddeed'),
  ('get_property_detail',      's2', FALSE, 'biddeed'),
  ('check_zoning',             's3', FALSE, 'zonewise'),
  ('underwrite_deal',          's3', FALSE, 'biddeed'),
  ('analyze_coliving',         's3', FALSE, 'biddeed'),
  ('get_sales_comps',          's3', FALSE, 'biddeed'),
  ('generate_deal_memo',       's3', FALSE, 'biddeed'),
  ('get_bid_package',          's3', FALSE, 'biddeed'),
  ('get_title_chain',          's3', FALSE, 'biddeed'),
  ('get_market_data',          's3', FALSE, 'biddeed'),
  ('skip_trace',               's3', FALSE, 'biddeed'),
  ('watch_auction',            's4', FALSE, 'biddeed'),
  ('predict_auction_outcome',  's5', TRUE,  'biddeed');

-- NOTE: RLS intentionally NOT enabled here.
-- These tables are accessed only via service role key in the MCP server (auth.js).
-- Application-layer protection (API key validation) is the security boundary.
-- Service role key bypasses RLS anyway, so RLS adds no protection for this use case.

END $mcp$;
