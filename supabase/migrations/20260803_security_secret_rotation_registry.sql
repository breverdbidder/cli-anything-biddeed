-- Blast-radius reduction: secret rotation registry + weekly Telegram reminder.
-- Deliverables 1+2 of docs/security/vault-audit-2026-08-03.md.
-- Idempotent: table/seed use IF NOT EXISTS + ON CONFLICT, function is CREATE OR REPLACE,
-- cron job is unscheduled-then-rescheduled so re-running this file is a no-op in effect.

CREATE TABLE IF NOT EXISTS public.secret_rotation_registry (
  id bigserial PRIMARY KEY,
  secret_name text UNIQUE NOT NULL,        -- matches vault.secrets name where applicable
  service text NOT NULL,                   -- cloudflare/anthropic/supabase/resend/stripe/etc
  rotation_method text NOT NULL,           -- api_automated/manual_required/cc_dispatch
  last_rotated_at timestamptz,
  rotation_interval_days integer DEFAULT 90,
  next_due_at timestamptz,
  notes text,
  created_at timestamptz DEFAULT now()
);
ALTER TABLE public.secret_rotation_registry ENABLE ROW LEVEL SECURITY;

-- brief's original snippet made next_due_at a GENERATED column via
-- `last_rotated_at + (rotation_interval_days || ' days')::interval` — Postgres rejects
-- this ("generation expression is not immutable"). Re-tested with make_interval() too
-- (provolatile='i', confirmed immutable) and it still fails: `timestamptz + interval` is
-- STABLE not IMMUTABLE, because day/month-interval arithmetic crosses DST boundaries.
-- A generated column can never hold this value. Trigger-maintained column instead.
CREATE OR REPLACE FUNCTION public._secret_rotation_registry_set_next_due()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
BEGIN
  NEW.next_due_at := NEW.last_rotated_at + make_interval(days => NEW.rotation_interval_days);
  RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_secret_rotation_registry_next_due ON public.secret_rotation_registry;
CREATE TRIGGER trg_secret_rotation_registry_next_due
  BEFORE INSERT OR UPDATE OF last_rotated_at, rotation_interval_days
  ON public.secret_rotation_registry
  FOR EACH ROW
  EXECUTE FUNCTION public._secret_rotation_registry_set_next_due();

-- Seed: every name currently in vault.secrets (31 rows, verified live 2026-08-03 via
-- `SELECT name FROM vault.secrets` — the brief's 9-secret list was a stale subset,
-- not the full picture) plus 4 known non-vault secrets the brief names explicitly
-- (deepseek/telegram x2/cloudflare live in GitHub Actions secrets, not vault).
INSERT INTO public.secret_rotation_registry
  (secret_name, service, rotation_method, last_rotated_at, rotation_interval_days, notes)
VALUES
  -- Explicitly named in brief with known status (2026-07-28 census)
  ('anthropic_oauth_bearer',        'anthropic',   'manual_required', NULL,                   60, 'NOT rotated per brief 2026-07-28 status. CC dependency must be traced before rotation — this is the live session credential.'),
  ('anthropic_oauth_refresh_token', 'anthropic',   'manual_required', NULL,                   60, 'Paired with anthropic_oauth_bearer; rotate together.'),
  ('router_proxy_key',              'cliproxy-gateway', 'cc_dispatch', NULL,                  90, 'Self-issued internal key (Hetzner CLIProxyAPI). Can be minted by CC, but consumers (Hetzner env) must be updated manually — Ariel approval required before rollout.'),
  ('resend_api_key',                'resend',      'manual_required', NULL,                   90, 'NOT rotated per brief 2026-07-28 status. See docs/security/vault-audit-2026-08-03.md for API rotation-capability research.'),
  ('mindstudio_bridge_secret',      'mindstudio',  'manual_required', NULL,                   90, 'NOT rotated per brief 2026-07-28 status. See docs/security/vault-audit-2026-08-03.md for API rotation-capability research.'),
  ('service_role_key',              'supabase',    'manual_required', NULL,                   90, 'NOT rotated per brief 2026-07-28 status. Requires Ariel: Dashboard -> Settings -> API -> Regenerate service_role key -> update SUPABASE_SERVICE_ROLE_KEY in GitHub secrets everywhere it is used. Cannot be rotated via API without owner auth.'),
  ('stripe_secret_key',             'stripe',      'manual_required', NULL,                   90, 'Brief: "Do NOT rotate the Stripe live secret key — Stripe rotation requires Ariel manually." Registry row kept for visibility only.'),
  ('stripe_webhook_secret',         'stripe',      'manual_required', NULL,                   90, 'Rotates together with any Stripe endpoint change; Ariel-only.'),
  ('gemini_api_key_biddeed',        'google',      'manual_required', NULL,                   90, 'Google AI Studio key; console-issued, no self-service rotation API confirmed.'),

  -- Remaining vault.secrets (verified live 2026-08-03), default-safe classification
  ('apify_api_token',               'apify',       'manual_required', NULL,                   90, 'Console-issued token; API-based self-rotation capability not confirmed (INFERRED, not tested).'),
  ('claude_code_oauth_access_meta', 'anthropic',   'manual_required', NULL,                   60, 'Metadata blob paired with CC OAuth session state.'),
  ('claudecodeui_admin_password',   'internal',    'manual_required', NULL,                  180, 'Local admin password for claudecodeui app.'),
  ('cli_anything_shared_secret',    'internal',    'cc_dispatch',     NULL,                   90, 'Self-issued shared secret gating cli_anything_get_secret(). Can be minted by CC; consumer rollout is Ariel-approved.'),
  ('dr_backup_passphrase',          'internal',    'manual_required', NULL,                  180, 'Encrypts DR backups. Rotating without a coordinated re-encrypt would strand old backups — Ariel decision required.'),
  ('everest_gh_pat',                'github',      'manual_required', NULL,                   90, 'GTM-22D leaked-and-rotated PAT. 51+ SECURITY DEFINER functions depend on postgres-level vault read of this secret; see CREDENTIAL HANDLING section of CLAUDE.md before touching.'),
  ('fork_heartbeat_token',          'internal',    'cc_dispatch',     NULL,                   90, 'Capability token gating get_vault_secret_gated(). Self-issued.'),
  ('gemini_api_key',                'google',      'manual_required', NULL,                   90, 'Distinct from gemini_api_key_biddeed — CLIProxyAPI free-tier key, noted DEAD/expired in CLAUDE.md stack config.'),
  ('hostaway_account_id',           'hostaway',    'manual_required', NULL,                  180, 'Account identifier, low rotation urgency but tracked for completeness.'),
  ('hostaway_api_key',              'hostaway',    'manual_required', NULL,                   90, 'Property-management integration credential.'),
  ('LAZYWEB_MCP_TOKEN',             'lazyweb',     'manual_required', NULL,                   90, 'MCP server auth token.'),
  ('posthog_personal_api_key',      'posthog',     'manual_required', NULL,                   90, 'Personal API key, rotatable via PostHog UI.'),
  ('posthog_project_key',           'posthog',     'manual_required', NULL,                  180, 'Project (write-only) key, lower sensitivity than personal key.'),
  ('propertyonion_jwt_current',     'propertyonion','manual_required', NULL,                   14, 'Short-lived JWT, likely app-refreshed already; tracked here as a floor in case auto-refresh silently breaks.'),
  ('propertyonion_password',        'propertyonion','manual_required', NULL,                   90, 'Scraping-account password.'),
  ('scraping_proxy_backend',        'internal',    'manual_required', NULL,                   90, 'Proxy backend credential for scraping fleet.'),
  ('supabase_anon_key',             'supabase',    'manual_required', NULL,                  180, 'Public anon key — low sensitivity by design, but regenerable via Dashboard if ever needs invalidating.'),
  ('vercel_api_token',              'vercel',      'manual_required', NULL,                   90, 'Vercel personal access tokens are dashboard-issued; no confirmed self-rotate-via-API path (INFERRED, not tested).'),
  ('vertex_project_id',             'google',      'manual_required', NULL,                  365, 'Static project identifier, not a rotatable credential — tracked only because it lives in vault.secrets.'),
  ('vertex_project_number',         'google',      'manual_required', NULL,                  365, 'Static project identifier, not a rotatable credential.'),
  ('vertex_region',                 'google',      'manual_required', NULL,                  365, 'Static config value, not a rotatable credential.'),
  ('zonewise_webhook_secret',       'internal',    'cc_dispatch',     NULL,                   90, 'Self-issued webhook signing secret. Can be minted by CC; consumer rollout is Ariel-approved.'),
  ('resend_from_address',           'resend',      'manual_required', NULL,                  365, 'Verified sender address, not a credential — tracked for completeness since it lives in vault.secrets.'),

  -- Known non-vault secrets named explicitly in the brief (GitHub Actions secrets)
  ('cloudflare_deploy_token',       'cloudflare',  'manual_required', '2026-07-28T00:00:00Z', 90, 'Lives in GitHub Actions secrets, not vault.secrets. ROTATED 2026-07-28 per brief.'),
  ('anthropic_api_key_ghaw',        'anthropic',   'manual_required', '2026-07-28T00:00:00Z', 60, 'The "Anthropic chatbot key" (new api03 key) referenced in the brief — used by gh-aw workflows via ANTHROPIC_API_KEY GitHub secret, distinct from anthropic_oauth_bearer. Lives in GitHub Actions secrets, not vault.'),
  ('deepseek_api_key',              'deepseek',    'manual_required', NULL,                   90, 'Lives in GitHub Actions secrets, not vault.secrets. Not found under this or any other name in vault.secrets as of 2026-08-03.'),
  ('telegram_bot_token',            'telegram',    'manual_required', NULL,                  180, 'Lives in GitHub Actions secrets as BIDDEED_BOT_TOKEN, not vault.secrets.'),
  ('telegram_chat_id',              'telegram',    'manual_required', NULL,                  365, 'Not a credential (chat ID, not a secret), tracked for completeness. Lives in GitHub Actions secrets as BIDDEED_BOT_CHAT_ID.')
ON CONFLICT (secret_name) DO NOTHING;

-- Weekly reminder: anything due within 14 days, or never tracked as rotated at all
-- (last_rotated_at IS NULL), fires one Telegram alert per secret via the existing
-- fire_workflow_dispatch() -> telegram-notify.yml path (no bot token touches this DB).
CREATE OR REPLACE FUNCTION public.check_secret_rotation_due()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $function$
DECLARE
  v_row RECORD;
  v_count integer := 0;
  v_dispatch jsonb;
BEGIN
  FOR v_row IN
    SELECT secret_name, service, rotation_method, last_rotated_at, next_due_at
    FROM public.secret_rotation_registry
    WHERE next_due_at < now() + INTERVAL '14 days'
       OR last_rotated_at IS NULL
    ORDER BY (last_rotated_at IS NULL) DESC, next_due_at NULLS FIRST
  LOOP
    v_count := v_count + 1;

    v_dispatch := public.fire_workflow_dispatch(
      'breverdbidder/cli-anything-biddeed',
      'telegram-notify.yml',
      'main',
      jsonb_build_object('message',
        '🔑 *Secret Rotation Due* — `' || v_row.secret_name || '` (' || v_row.service || ') ' ||
        CASE WHEN v_row.last_rotated_at IS NULL
          THEN 'has never been tracked as rotated'
          ELSE 'last rotated ' || (extract(day FROM now() - v_row.last_rotated_at))::text || ' days ago'
        END ||
        '. Due: ' || COALESCE(v_row.next_due_at::text, 'unknown') ||
        '. Method: ' || v_row.rotation_method
      )
    );

    INSERT INTO public.agent_ops_log (dispatch_id, task, status, evidence, severity)
    VALUES (
      'secret-rotation-check',
      'blast-radius-reduction-2026-08-03',
      'VERIFIED',
      'Alert fired for ' || v_row.secret_name || ': ' || v_dispatch::text,
      'warn'
    );
  END LOOP;

  RETURN jsonb_build_object('checked_at', now(), 'alerts_fired', v_count);
END;
$function$;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'secret-rotation-check') THEN
    PERFORM cron.unschedule('secret-rotation-check');
  END IF;
END $$;

SELECT cron.schedule('secret-rotation-check', '0 9 * * 1',
  $$SELECT public.check_secret_rotation_due()$$);
