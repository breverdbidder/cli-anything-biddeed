-- Migration: B2C trial activation loop — signup -> mcp_api_keys -> activation email
-- Created: 2026-07-02 | Idempotent: safe to re-run
-- Dispatch: 5a22e71a-f0c8-4f9c-beec-217803e3221f
--
-- Email delivery audit (repo GH secrets via `gh secret list` + Supabase vault via
-- vault.decrypted_secrets): no RESEND_API_KEY / SENDGRID_API_KEY / SMTP_* / gmail
-- credential exists anywhere. Per mission rules, key creation must not stall on
-- this — emails are queued to b2c_activation_outbox (pending) and a one-time
-- Telegram alert is fired via the existing fire_workflow_dispatch() ->
-- telegram-notify.yml path (same mechanism already used by the
-- gold-48h-throughput-checkpoint cron job) naming the exact secrets checked.

DO $b2c$
BEGIN

-- ── b2c_activation_outbox — pending activation emails (no send capability yet) ─
CREATE TABLE IF NOT EXISTS public.b2c_activation_outbox (
  id             BIGSERIAL PRIMARY KEY,
  signup_id      UUID NOT NULL REFERENCES public.b2c_trial_signups(id),
  email          TEXT NOT NULL,
  subject        TEXT NOT NULL,
  body_text      TEXT NOT NULL,
  api_key_prefix TEXT NOT NULL,
  status         TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','sent','failed')),
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  sent_at        TIMESTAMPTZ,
  error          TEXT
);

CREATE INDEX IF NOT EXISTS idx_b2c_activation_outbox_status
  ON public.b2c_activation_outbox(status) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_b2c_activation_outbox_signup
  ON public.b2c_activation_outbox(signup_id);

-- NOTE: RLS intentionally NOT enabled — service-role-only access, same convention
-- as mcp_api_keys / billing_events (see 20260623_mcp_core_tables.sql).

-- ── b2c_activation_config — singleton flag: fire the missing-email-secret alert once ──
CREATE TABLE IF NOT EXISTS public.b2c_activation_config (
  id                      INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  missing_secret_notified BOOLEAN NOT NULL DEFAULT FALSE,
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
INSERT INTO public.b2c_activation_config (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

END $b2c$;

-- ── public.b2c_activate_signups() ────────────────────────────────────────────
-- Idempotent, batch-safe (FOR UPDATE SKIP LOCKED). Per-row exception handling —
-- one bad signup can't block the rest of the batch; failed rows stay status='new'
-- and retry next tick.
CREATE OR REPLACE FUNCTION public.b2c_activate_signups()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public', 'extensions'
AS $fn$
DECLARE
  v_row              RECORD;
  v_customer_id      UUID;
  v_api_key          TEXT;
  v_key_hash         TEXT;
  v_key_prefix       TEXT;
  v_expires_at       TIMESTAMPTZ;
  v_activated        INT := 0;
  v_errors           JSONB := '[]'::jsonb;
  v_already_notified BOOLEAN;
BEGIN
  FOR v_row IN
    SELECT * FROM public.b2c_trial_signups
    WHERE status = 'new'
    ORDER BY created_at
    FOR UPDATE SKIP LOCKED
  LOOP
    BEGIN
      v_api_key    := 'bd_trial_' || translate(encode(gen_random_bytes(18), 'base64'), '/+=', '_-');
      v_key_hash   := encode(digest(v_api_key, 'sha256'), 'hex');
      v_key_prefix := left(v_api_key, 14);
      v_expires_at := now() + interval '30 days';

      SELECT customer_id INTO v_customer_id
      FROM public.mcp_customers
      WHERE lower(email) = lower(v_row.email)
      LIMIT 1;

      IF v_customer_id IS NULL THEN
        INSERT INTO public.mcp_customers (email, tier_id, customer_type)
        VALUES (lower(v_row.email), 'investor', 'human')
        RETURNING customer_id INTO v_customer_id;
      END IF;

      INSERT INTO public.mcp_api_keys
        (customer_id, key_prefix, key_hash, server, tier, product,
         rate_limit_hr, daily_s1_limit, is_active, active, expires_at)
      VALUES
        (v_customer_id, v_key_prefix, v_key_hash, 'biddeed', 'investor', 'biddeed',
         100, 9999, TRUE, TRUE, v_expires_at);

      INSERT INTO public.b2c_activation_outbox
        (signup_id, email, subject, body_text, api_key_prefix)
      VALUES (
        v_row.id,
        v_row.email,
        'Your BidDeed.AI 30-day trial key',
        format($body$Hi,

Your BidDeed.AI 30-day Investor trial is active. No credit card required.

Activation key: %s
Expires: %s

Quickstart — add to your Claude Desktop / Claude Code MCP config:

{
  "mcpServers": {
    "biddeed": {
      "command": "npx",
      "args": ["-y", "biddeed-mcp"],
      "env": { "BIDDEED_API_KEY": "%s" }
    }
  }
}

Full install steps: biddeed.ai/mcp/install

— BidDeed.AI$body$,
          v_api_key, to_char(v_expires_at, 'YYYY-MM-DD'), v_api_key
        ),
        v_key_prefix
      );

      UPDATE public.b2c_trial_signups SET status = 'activated' WHERE id = v_row.id;
      v_activated := v_activated + 1;
    EXCEPTION WHEN OTHERS THEN
      v_errors := v_errors || jsonb_build_object('email', v_row.email, 'error', SQLERRM);
    END;
  END LOOP;

  -- One-time alert: no email-send secret exists yet (checked RESEND_API_KEY,
  -- SENDGRID_API_KEY, SMTP_HOST, gmail API — none found, 2026-07-02). Best-effort;
  -- never lets a notify failure block activation.
  SELECT missing_secret_notified INTO v_already_notified
  FROM public.b2c_activation_config WHERE id = 1;

  IF NOT v_already_notified THEN
    BEGIN
      PERFORM public.fire_workflow_dispatch(
        'breverdbidder/cli-anything-biddeed',
        'telegram-notify.yml',
        'main',
        jsonb_build_object('message',
          'B2C trial activation loop is LIVE — mcp_api_keys are being created and emails ' ||
          'queued to b2c_activation_outbox, but no email-send secret exists. Checked: ' ||
          'RESEND_API_KEY, SENDGRID_API_KEY, SMTP_HOST, gmail API — none found in repo ' ||
          'secrets or Supabase vault. Add RESEND_API_KEY (or equivalent) as a GH secret + ' ||
          'vault entry to unblock actual delivery. Key creation is NOT stalled on this.')
      );
    EXCEPTION WHEN OTHERS THEN
      NULL;
    END;
    UPDATE public.b2c_activation_config
    SET missing_secret_notified = TRUE, updated_at = now()
    WHERE id = 1;
  END IF;

  RETURN jsonb_build_object('activated', v_activated, 'errors', v_errors);
END;
$fn$;

-- ── pg_cron: every 5 minutes (matches "keys emailed same day" promise on the page) ──
SELECT cron.schedule('b2c-trial-activation-tick', '*/5 * * * *', $$SELECT public.b2c_activate_signups();$$)
WHERE NOT EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'b2c-trial-activation-tick');
