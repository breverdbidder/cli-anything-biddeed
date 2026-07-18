-- GTM-22 Task 2 + Task 3: idempotency keys + charge-ordering instrumentation
-- for the biddeed-mcp billing path. See issue #12775.

-- Task 2: idempotency keys on every billable tool call. DB-level unique
-- constraint (primary key) is the source of truth — application code races
-- to INSERT and loses gracefully on conflict, never on a check-then-act read.
CREATE TABLE IF NOT EXISTS public.mcp_idempotency_keys (
  idempotency_key text PRIMARY KEY,
  customer_id     uuid NOT NULL,
  tool_name       text NOT NULL,
  status          text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'completed')),
  response_json   jsonb,
  is_error        boolean NOT NULL DEFAULT false,
  billing_event_id uuid,
  duplicate_count integer NOT NULL DEFAULT 0,
  created_at      timestamptz NOT NULL DEFAULT now(),
  completed_at    timestamptz,
  expires_at      timestamptz NOT NULL DEFAULT (now() + interval '24 hours')
);

CREATE INDEX IF NOT EXISTS idx_mcp_idempotency_keys_expires_at
  ON public.mcp_idempotency_keys (expires_at);

CREATE INDEX IF NOT EXISTS idx_mcp_idempotency_keys_customer
  ON public.mcp_idempotency_keys (customer_id, created_at);

COMMENT ON TABLE public.mcp_idempotency_keys IS
  'GTM-22 Task 2 — dedup ledger for MCP tool calls. Key = sha256(apiKeyHash:toolName:jsonRpcId:bodyHash). '
  'A row in status=completed with a duplicate retry is served from response_json with zero additional billing.';

-- Task 3: per-call charge outcome log, feeds charge_failure_rate.
CREATE TABLE IF NOT EXISTS public.mcp_charge_events (
  id          bigserial PRIMARY KEY,
  customer_id uuid,
  tool_name   text NOT NULL,
  stream_id   text,
  outcome     text NOT NULL CHECK (outcome IN (
                'charged', 'blocked_allowance', 'blocked_stripe', 'serialization_error', 'tool_error'
              )),
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_mcp_charge_events_created_at
  ON public.mcp_charge_events (created_at);

COMMENT ON TABLE public.mcp_charge_events IS
  'GTM-22 Task 3 — one row per tool-call charge decision. outcome=charged is the '
  'happy path; blocked_allowance/blocked_stripe are Failure-A guard trips; '
  'serialization_error is a Failure-B guard trip. Feeds v_mcp_charge_failure_rate_15m.';

-- Rolling 15-minute charge_failure_rate — Sentinel polls this view.
CREATE OR REPLACE VIEW public.v_mcp_charge_failure_rate_15m AS
SELECT
  count(*) FILTER (WHERE outcome <> 'charged' AND outcome <> 'tool_error') AS blocked_count,
  count(*) AS total_count,
  CASE WHEN count(*) = 0 THEN 0
       ELSE round(
         100.0 * count(*) FILTER (WHERE outcome <> 'charged' AND outcome <> 'tool_error') / count(*),
         2
       )
  END AS charge_failure_rate_pct
FROM public.mcp_charge_events
WHERE created_at > now() - interval '15 minutes';

COMMENT ON VIEW public.v_mcp_charge_failure_rate_15m IS
  'GTM-22 Task 3 — Sentinel alerts when charge_failure_rate_pct > 2 over this rolling 15-minute window.';
