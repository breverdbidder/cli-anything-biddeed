-- Migration: MCP core tables — API keys, billing events, beta invites, taxi meter
-- Created: 2026-06-23

-- ── mcp_api_keys ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS mcp_api_keys (
  id                BIGSERIAL PRIMARY KEY,
  key_hash          TEXT NOT NULL UNIQUE,   -- SHA-256 of bd_live_xxx or zw_live_xxx
  key_prefix        TEXT NOT NULL,          -- first 14 chars for display (bd_live_xxxxxx)
  customer_id       TEXT NOT NULL,          -- matches beta_invites.customer_id
  tier              TEXT NOT NULL DEFAULT 'investor', -- free/investor/pro/proplus/enterprise
  product           TEXT NOT NULL DEFAULT 'biddeed',  -- biddeed/zonewise
  rate_limit_hr     INTEGER NOT NULL DEFAULT 100,
  daily_s1_limit    INTEGER NOT NULL DEFAULT 50,      -- free tier: 50 S1/day
  is_active         BOOLEAN NOT NULL DEFAULT TRUE,
  stripe_customer_id TEXT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at        TIMESTAMPTZ,
  last_used_at      TIMESTAMPTZ,
  call_count        BIGINT NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_mcp_api_keys_hash       ON mcp_api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_mcp_api_keys_customer   ON mcp_api_keys(customer_id);
CREATE INDEX IF NOT EXISTS idx_mcp_api_keys_tier       ON mcp_api_keys(tier);

-- ── billing_events ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS billing_events (
  id                      BIGSERIAL PRIMARY KEY,
  tool_name               TEXT NOT NULL,
  stream_id               TEXT NOT NULL,        -- s1/s2/s3/s4/s5/fee
  customer_id             TEXT NOT NULL,
  key_prefix              TEXT NOT NULL,
  unit_price_usd          NUMERIC(10,4) NOT NULL,
  billed_amount           NUMERIC(10,4) NOT NULL,
  quantity                INTEGER NOT NULL DEFAULT 1,
  settled                 BOOLEAN NOT NULL DEFAULT FALSE,
  cert_status             TEXT,                 -- certified/uncertified (S5 only)
  county                  TEXT,
  params                  JSONB,                -- sanitized call params
  result_summary          TEXT,
  stripe_usage_record_id  TEXT,                 -- S5 Stripe metered billing
  created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  settled_at              TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_billing_events_customer    ON billing_events(customer_id);
CREATE INDEX IF NOT EXISTS idx_billing_events_stream      ON billing_events(stream_id);
CREATE INDEX IF NOT EXISTS idx_billing_events_tool        ON billing_events(tool_name);
CREATE INDEX IF NOT EXISTS idx_billing_events_created     ON billing_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_billing_events_settled     ON billing_events(settled) WHERE settled = FALSE;

-- ── beta_invites ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS beta_invites (
  id                BIGSERIAL PRIMARY KEY,
  customer_id       TEXT NOT NULL UNIQUE,      -- bd_cust_xxxx (generated)
  name              TEXT NOT NULL,
  email             TEXT NOT NULL UNIQUE,
  invite_code       TEXT NOT NULL UNIQUE,      -- BREVARD-xxxx-xxxx
  cohort            TEXT NOT NULL DEFAULT 'wave1_brevard_duval',
  counties_active   TEXT[] NOT NULL DEFAULT '{}',
  tier              TEXT NOT NULL DEFAULT 'pro',
  api_key_prefix    TEXT,                       -- set after key generated
  invited_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  activated_at      TIMESTAMPTZ,
  notes             TEXT
);

CREATE INDEX IF NOT EXISTS idx_beta_invites_email      ON beta_invites(email);
CREATE INDEX IF NOT EXISTS idx_beta_invites_code       ON beta_invites(invite_code);
CREATE INDEX IF NOT EXISTS idx_beta_invites_cohort     ON beta_invites(cohort);

-- ── taxi_meter_streams ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS taxi_meter_streams (
  id              BIGSERIAL PRIMARY KEY,
  stream_id       TEXT NOT NULL UNIQUE,
  name            TEXT NOT NULL,
  unit_price_usd  NUMERIC(10,4) NOT NULL,
  gate_tier       TEXT NOT NULL,
  billing_type    TEXT NOT NULL DEFAULT 'per_call',  -- per_call/subscription/transaction_pct
  stripe_metered  BOOLEAN NOT NULL DEFAULT FALSE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO taxi_meter_streams (stream_id, name, unit_price_usd, gate_tier, billing_type, stripe_metered) VALUES
  ('s1',  'Discovery',       0.0500, 'free',       'per_call',       FALSE),
  ('s2',  'Qualification',   0.4000, 'investor',   'per_call',       FALSE),
  ('s3',  'Fusion',          5.0000, 'pro',        'per_call',       FALSE),
  ('s4',  'Monitoring',      0.0000, 'pro',        'subscription',   FALSE),
  ('s5',  'Shapira Formula', 25.0000,'pro',        'per_call',       TRUE),
  ('fee', 'Close-and-Fee',   0.0000, 'enterprise', 'transaction_pct',FALSE)
ON CONFLICT (stream_id) DO NOTHING;

-- ── taxi_meter_tools ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS taxi_meter_tools (
  id          BIGSERIAL PRIMARY KEY,
  tool_name   TEXT NOT NULL UNIQUE,
  stream_id   TEXT NOT NULL REFERENCES taxi_meter_streams(stream_id),
  gate_cert   BOOLEAN NOT NULL DEFAULT FALSE,   -- requires gold standard cert?
  product     TEXT NOT NULL DEFAULT 'biddeed',  -- biddeed/zonewise
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO taxi_meter_tools (tool_name, stream_id, gate_cert, product) VALUES
  -- S1 Discovery
  ('search_auctions',          's1', FALSE, 'biddeed'),
  ('get_auction_detail',       's1', FALSE, 'biddeed'),
  ('browse_deals',             's1', FALSE, 'biddeed'),
  ('get_deposit_requirements', 's1', FALSE, 'biddeed'),
  ('find_local_partners',      's1', FALSE, 'biddeed'),
  ('get_interest_rate',        's1', FALSE, 'biddeed'),
  ('search_properties',        's1', FALSE, 'biddeed'),
  -- S2 Qualification
  ('search_distressed',        's2', FALSE, 'biddeed'),
  ('get_owner_intel',          's2', FALSE, 'biddeed'),
  ('get_lien_stack',           's2', FALSE, 'biddeed'),
  ('get_rent_estimate',        's2', FALSE, 'biddeed'),
  ('analyze_market',           's2', FALSE, 'biddeed'),
  ('get_zip_market_data',      's2', FALSE, 'biddeed'),
  ('get_property_detail',      's2', FALSE, 'biddeed'),
  -- S3 Fusion
  ('check_zoning',             's3', FALSE, 'zonewise'),
  ('underwrite_deal',          's3', FALSE, 'biddeed'),
  ('analyze_coliving',         's3', FALSE, 'biddeed'),
  ('get_sales_comps',          's3', FALSE, 'biddeed'),
  ('generate_deal_memo',       's3', FALSE, 'biddeed'),
  ('get_bid_package',          's3', FALSE, 'biddeed'),
  ('get_title_chain',          's3', FALSE, 'biddeed'),
  ('get_market_data',          's3', FALSE, 'biddeed'),
  ('skip_trace',               's3', FALSE, 'biddeed'),
  -- S4 Monitoring
  ('watch_auction',            's4', FALSE, 'biddeed'),
  -- S5 Shapira Formula — CERT REQUIRED
  ('predict_auction_outcome',  's5', TRUE,  'biddeed')
ON CONFLICT (tool_name) DO NOTHING;

-- ── RLS: billing_events + mcp_api_keys (service role only) ───────────────────
ALTER TABLE billing_events     ENABLE ROW LEVEL SECURITY;
ALTER TABLE mcp_api_keys       ENABLE ROW LEVEL SECURITY;
ALTER TABLE beta_invites        ENABLE ROW LEVEL SECURITY;
ALTER TABLE taxi_meter_streams  ENABLE ROW LEVEL SECURITY;
ALTER TABLE taxi_meter_tools    ENABLE ROW LEVEL SECURITY;

-- Service role bypasses RLS — idempotent: drop before re-create
DO $$ BEGIN
  DROP POLICY IF EXISTS "service_role_all" ON billing_events;
  DROP POLICY IF EXISTS "service_role_all" ON mcp_api_keys;
  DROP POLICY IF EXISTS "service_role_all" ON beta_invites;
  DROP POLICY IF EXISTS "service_role_all" ON taxi_meter_streams;
  DROP POLICY IF EXISTS "service_role_all" ON taxi_meter_tools;

  CREATE POLICY "service_role_all" ON billing_events    FOR ALL USING (auth.role() = 'service_role');
  CREATE POLICY "service_role_all" ON mcp_api_keys      FOR ALL USING (auth.role() = 'service_role');
  CREATE POLICY "service_role_all" ON beta_invites       FOR ALL USING (auth.role() = 'service_role');
  CREATE POLICY "service_role_all" ON taxi_meter_streams FOR ALL USING (auth.role() = 'service_role');
  CREATE POLICY "service_role_all" ON taxi_meter_tools   FOR ALL USING (auth.role() = 'service_role');
END $$;
