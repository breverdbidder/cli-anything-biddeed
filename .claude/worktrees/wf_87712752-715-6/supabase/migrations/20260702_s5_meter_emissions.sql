-- Migration: s5_meter_emissions — Stripe Billing Meter emission log for S5 (Shapira Formula)
-- Created: 2026-07-02 | Idempotent: safe to re-run
-- Dispatch: 858e13e7-50b9-4151-9633-af077526770a (SPRINT3 P0-2)
--
-- Records every attempt to emit an S5 usage aggregate (bd_key x hourly window) to the
-- Stripe Billing Meter API (event_name='s5_predict_auction_outcome'). Source rows come
-- from billing_events WHERE stream_id='s5'. usage_source_ref uniquely identifies the
-- (bd_key, window) pair so re-running the emitter never double-emits the same usage.
--
-- stripe_accepted=FALSE with error='no_customer_mapping' is a VALID terminal state —
-- it means the pipeline ran correctly but mcp_api_keys.stripe_customer_id was NULL for
-- that key at emission time (expected: no Stripe customers exist yet, Customers=Read only).

CREATE TABLE IF NOT EXISTS s5_meter_emissions (
  emission_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  usage_source_ref    TEXT NOT NULL UNIQUE,
  bd_key              TEXT NOT NULL,
  stripe_customer_id  TEXT,
  quantity            INTEGER NOT NULL,
  emitted_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  stripe_accepted     BOOLEAN NOT NULL DEFAULT FALSE,
  stripe_event_id     TEXT,
  error               TEXT
);

ALTER TABLE s5_meter_emissions ADD COLUMN IF NOT EXISTS stripe_customer_id TEXT;
ALTER TABLE s5_meter_emissions ADD COLUMN IF NOT EXISTS stripe_event_id    TEXT;
ALTER TABLE s5_meter_emissions ADD COLUMN IF NOT EXISTS error              TEXT;

CREATE INDEX IF NOT EXISTS idx_s5_meter_emissions_bd_key   ON s5_meter_emissions(bd_key);
CREATE INDEX IF NOT EXISTS idx_s5_meter_emissions_unmapped ON s5_meter_emissions(bd_key) WHERE stripe_accepted = FALSE;

-- NOTE: RLS intentionally NOT enabled — matches billing_events / mcp_api_keys convention.
-- Accessed only via service role key (scripts/s5-meter-emit.js). Application-layer
-- protection (API key validation, Stripe key vault-first resolution) is the security
-- boundary. Service role key bypasses RLS anyway, so RLS adds no protection here.
