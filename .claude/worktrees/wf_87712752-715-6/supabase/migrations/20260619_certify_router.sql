-- ============================================================
-- CERTIFY ROUTER: Haiku→Sonnet→Opus tiered verification
-- Migration: 20260619_certify_router.sql
-- ============================================================
-- Invariant: authority='gate' on every cert row.
-- LLM tiers may VETO (escalate) a gate pass, never GRANT one.
-- No model can flip a hard-gate FAIL to PASS.
-- ============================================================

-- Live tunables (floors/rate read from DB, no redeploy)
CREATE TABLE IF NOT EXISTS public.certify_router_config (
  key          TEXT PRIMARY KEY,
  value_num    NUMERIC,
  value_text   TEXT,
  updated_at   TIMESTAMPTZ DEFAULT now()
);

INSERT INTO public.certify_router_config (key, value_num, value_text) VALUES
  ('haiku_confidence_floor', 0.90,   NULL),
  ('sonnet_confidence_floor', 0.85,  NULL),
  ('shadow_audit_rate',       0.10,  NULL),
  ('min_tier',                NULL,  'haiku')
ON CONFLICT (key) DO NOTHING;

-- Per-cert tier provenance trail (Honesty V3)
CREATE TABLE IF NOT EXISTS public.certify_tier_trail (
  id              SERIAL PRIMARY KEY,
  county_slug     TEXT NOT NULL,
  run_id          TEXT NOT NULL,

  -- T0 deterministic gate (VERIFIED)
  gate_pass_count INTEGER,
  gate_verdict    TEXT NOT NULL CHECK (gate_verdict IN ('pass','fail')),
  gate_letters    JSONB,                        -- {A: true/false, B: ..., ...}
  gate_detail     JSONB,                        -- per-letter metric + detail

  -- T1 Haiku screen (INFERRED)
  t1_verdict      TEXT CHECK (t1_verdict IN ('clean','escalate','skipped')),
  t1_confidence   NUMERIC(4,3),
  t1_reason       TEXT,
  t1_raw          TEXT,
  t1_tokens_in    INTEGER,
  t1_tokens_out   INTEGER,

  -- T2 Sonnet screen (INFERRED)
  t2_verdict      TEXT CHECK (t2_verdict IN ('clean','escalate','skipped')),
  t2_confidence   NUMERIC(4,3),
  t2_reason       TEXT,
  t2_raw          TEXT,
  t2_tokens_in    INTEGER,
  t2_tokens_out   INTEGER,

  -- T3 Opus review (VERIFIED — Opus diagnoses, not screens)
  t3_invoked      BOOLEAN DEFAULT FALSE,
  t3_diagnosis    TEXT,
  t3_tokens_in    INTEGER,
  t3_tokens_out   INTEGER,

  -- Final outcome
  final_certify   BOOLEAN NOT NULL,
  final_tier      TEXT NOT NULL CHECK (final_tier IN ('gate_fail','t1','t2','t3','gate_only')),
  authority       TEXT NOT NULL DEFAULT 'gate' CHECK (authority = 'gate'),

  -- Shadow audit self-correction
  shadow_audited        BOOLEAN DEFAULT FALSE,
  shadow_audit_agreed   BOOLEAN,
  shadow_audit_at       TIMESTAMPTZ,
  shadow_audit_reason   TEXT,

  created_at      TIMESTAMPTZ DEFAULT now(),

  UNIQUE (run_id, county_slug)
);

CREATE INDEX IF NOT EXISTS idx_ctt_county ON public.certify_tier_trail (county_slug);
CREATE INDEX IF NOT EXISTS idx_ctt_run    ON public.certify_tier_trail (run_id);
CREATE INDEX IF NOT EXISTS idx_ctt_cert   ON public.certify_tier_trail (final_certify, created_at);
CREATE INDEX IF NOT EXISTS idx_ctt_shadow ON public.certify_tier_trail (shadow_audited, final_certify);

-- Per-run telemetry (tier mix + token spend + weekly Opus-reduction %)
CREATE TABLE IF NOT EXISTS public.certify_router_run (
  id                  SERIAL PRIMARY KEY,
  run_id              TEXT NOT NULL UNIQUE,

  -- Tier mix
  counties_total      INTEGER DEFAULT 0,
  counties_gate_fail  INTEGER DEFAULT 0,
  counties_t1_cert    INTEGER DEFAULT 0,
  counties_t2_cert    INTEGER DEFAULT 0,
  counties_t3_review  INTEGER DEFAULT 0,

  -- Token spend
  t1_tokens_total     INTEGER DEFAULT 0,
  t2_tokens_total     INTEGER DEFAULT 0,
  t3_tokens_total     INTEGER DEFAULT 0,

  -- Estimated cost (cents)
  cost_cents_haiku    NUMERIC(10,4) DEFAULT 0,
  cost_cents_sonnet   NUMERIC(10,4) DEFAULT 0,
  cost_cents_opus     NUMERIC(10,4) DEFAULT 0,
  cost_cents_total    NUMERIC(10,4) DEFAULT 0,

  -- Config snapshot at time of run
  haiku_floor_used    NUMERIC(4,3),
  sonnet_floor_used   NUMERIC(4,3),
  shadow_rate_used    NUMERIC(4,3),

  -- Shadow audit tighten events
  shadow_tighten_events INTEGER DEFAULT 0,

  started_at          TIMESTAMPTZ DEFAULT now(),
  completed_at        TIMESTAMPTZ,

  trigger_source      TEXT DEFAULT 'manual'  -- 'manual','cron','dispatch'
);

-- Weekly view: Opus-reduction % vs a hypothetical all-Opus baseline
CREATE OR REPLACE VIEW public.v_certify_cost_weekly AS
SELECT
  date_trunc('week', started_at)::DATE               AS week_start,
  COUNT(*)                                            AS runs,
  SUM(counties_total)                                 AS counties_processed,
  SUM(counties_t1_cert)                               AS t1_certs,
  SUM(counties_t2_cert)                               AS t2_certs,
  SUM(counties_t3_review)                             AS t3_reviews,
  ROUND(SUM(cost_cents_total)::NUMERIC, 2)            AS actual_cost_cents,
  -- Hypothetical all-Opus cost (same counties, all at Opus rate)
  ROUND((SUM(counties_total) * 0.023 * 100)::NUMERIC, 2) AS opus_only_cost_cents,
  ROUND(
    100.0 - (SUM(cost_cents_total) / NULLIF(SUM(counties_total) * 0.023 * 100, 0)) * 100,
    1
  )                                                   AS opus_reduction_pct
FROM public.certify_router_run
GROUP BY 1
ORDER BY 1 DESC;

-- Convenience function to read a config value
CREATE OR REPLACE FUNCTION public.certify_config_num(p_key TEXT) RETURNS NUMERIC
LANGUAGE sql STABLE AS $$
  SELECT value_num FROM public.certify_router_config WHERE key = p_key;
$$;

CREATE OR REPLACE FUNCTION public.certify_config_text(p_key TEXT) RETURNS TEXT
LANGUAGE sql STABLE AS $$
  SELECT value_text FROM public.certify_router_config WHERE key = p_key;
$$;

-- Shadow-audit auto-tighten trigger
-- When a shadow audit disagrees: raise rate to 0.25, lower floors by 0.05, set min_tier='sonnet'
CREATE OR REPLACE FUNCTION public.certify_shadow_tighten() RETURNS VOID
LANGUAGE plpgsql AS $$
BEGIN
  UPDATE public.certify_router_config SET
    value_num  = LEAST(0.25, value_num + 0.05),
    updated_at = now()
  WHERE key = 'shadow_audit_rate';

  UPDATE public.certify_router_config SET
    value_num  = GREATEST(0.70, value_num - 0.05),
    updated_at = now()
  WHERE key IN ('haiku_confidence_floor', 'sonnet_confidence_floor');

  UPDATE public.certify_router_config SET
    value_text = 'sonnet',
    updated_at = now()
  WHERE key = 'min_tier';
END;
$$;

GRANT SELECT ON public.certify_router_config    TO anon, authenticated;
GRANT SELECT ON public.certify_tier_trail       TO anon, authenticated;
GRANT SELECT ON public.certify_router_run       TO anon, authenticated;
GRANT SELECT ON public.v_certify_cost_weekly    TO anon, authenticated;
GRANT INSERT, UPDATE ON public.certify_tier_trail    TO service_role;
GRANT INSERT, UPDATE ON public.certify_router_run    TO service_role;
GRANT UPDATE ON public.certify_router_config         TO service_role;

COMMENT ON TABLE public.certify_router_config IS
  'Live tunables for certify router. Floors/rates read per-run — no redeploy needed.';
COMMENT ON TABLE public.certify_tier_trail IS
  'Per-cert tier provenance (Honesty V3). authority=gate always; model screens are INFERRED.';
COMMENT ON TABLE public.certify_router_run IS
  'Per-run telemetry: tier mix, token spend, weekly Opus-reduction %.';
COMMENT ON VIEW public.v_certify_cost_weekly IS
  'Weekly cost telemetry showing actual cost vs hypothetical all-Opus baseline.';
