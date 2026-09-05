-- GTM-4 (#20033): LMS Connections page -- one-tap OAuth for Meta/TikTok/X,
-- tokens straight to the vault, status tiles.
--
-- Reuses existing infrastructure rather than inventing new tables (K2 /
-- SEARCH-FIRST MANDATE): public.gha_credential_sync_log already provides an
-- audit trail with the exact shape an OAuth-token vault write needs
-- (github_secret_name, vault_secret_name, action, prev/new sha256) -- see
-- 20260803_telegram_vault_sync_whitelist.sql / 20260901g_lms_credential_reset_whitelist.sql
-- for the precedent this migration follows. public.social_token_health and
-- public.youtube_token_health (both from #20029/CP3g, 20260903f_*.sql)
-- already hold per-platform health state -- read/written here, not
-- redefined. No new table. RLS already enabled on all three with no
-- anon/authenticated policy (service_role only) -- unchanged.

-- ---------------------------------------------------------------------------
-- 1. Whitelist-gated OAuth token -> vault write, one function for all three
--    platforms (same posture as sync_credential_from_gha): explicit
--    per-platform allow-list of vault secret names, reject anything else,
--    idempotent create-or-update, full audit row every call (including
--    rejections). EXECUTE restricted to service_role only -- this Worker
--    always calls Supabase via SUPABASE_SERVICE_KEY (see src/index.js
--    header), so the human-access boundary is the LMS session cookie/login
--    that already gates every /connections/* route, not a second DB-level
--    gate. Unlike ff_batch_approve_authenticated()/reel_variant_review_
--    authenticated() (issue #19745/#20029 pattern), this is not an
--    unforgeable-approval action -- it's server-side OAuth token storage
--    after Ariel's own browser completed the provider's consent screen, so
--    service_role is the correct, sufficient gate.
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.lms_oauth_vault_write(
  p_platform          text,
  p_vault_secret_name text,
  p_value             text
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = 'vault', 'public', 'extensions'
AS $function$
DECLARE
  v_allowed_map  jsonb := jsonb_build_object(
    'meta',   jsonb_build_array('meta_page_access_token', 'meta_page_id', 'ig_business_account_id', 'meta_user_token_expires_at'),
    'tiktok', jsonb_build_array('tiktok_access_token', 'tiktok_refresh_token', 'tiktok_open_id', 'tiktok_token_expires_at'),
    'x',      jsonb_build_array('x_access_token', 'x_refresh_token')
  );
  v_allowed_names jsonb;
  v_existing_id   uuid;
  v_existing_val  text;
  v_prev_sha      text;
  v_new_sha       text;
  v_action        text;
BEGIN
  v_allowed_names := v_allowed_map -> p_platform;
  IF v_allowed_names IS NULL THEN
    INSERT INTO public.gha_credential_sync_log
      (github_secret_name, vault_secret_name, action, error_message)
    VALUES ('oauth:' || COALESCE(p_platform, 'null'), p_vault_secret_name, 'error', 'unknown_platform');
    RETURN jsonb_build_object('action', 'error', 'reason', 'unknown_platform');
  END IF;

  IF NOT (v_allowed_names ? p_vault_secret_name) THEN
    INSERT INTO public.gha_credential_sync_log
      (github_secret_name, vault_secret_name, action, error_message)
    VALUES ('oauth:' || p_platform, p_vault_secret_name, 'error', 'vault_secret_name not whitelisted for this platform');
    RETURN jsonb_build_object('action', 'error', 'reason', 'not_whitelisted');
  END IF;

  IF p_value IS NULL OR p_value = '' THEN
    INSERT INTO public.gha_credential_sync_log
      (github_secret_name, vault_secret_name, action, error_message)
    VALUES ('oauth:' || p_platform, p_vault_secret_name, 'error', 'empty value');
    RETURN jsonb_build_object('action', 'error', 'reason', 'empty_value');
  END IF;

  v_new_sha := encode(extensions.digest(p_value, 'sha256'), 'hex');

  SELECT s.id, ds.decrypted_secret
    INTO v_existing_id, v_existing_val
  FROM vault.secrets s
  LEFT JOIN vault.decrypted_secrets ds ON ds.id = s.id
  WHERE s.name = p_vault_secret_name
  LIMIT 1;

  IF v_existing_id IS NULL THEN
    PERFORM vault.create_secret(
      p_value,
      p_vault_secret_name,
      format('OAuth token stored via LMS /connections (issue #20033), platform=%s. Managed by lms_oauth_vault_write -- do not edit manually.', p_platform)
    );
    v_action := 'created';
    v_prev_sha := NULL;
  ELSE
    v_prev_sha := encode(extensions.digest(v_existing_val, 'sha256'), 'hex');
    IF v_prev_sha = v_new_sha THEN
      v_action := 'no_change';
    ELSE
      PERFORM vault.update_secret(v_existing_id, p_value);
      v_action := 'updated';
    END IF;
  END IF;

  INSERT INTO public.gha_credential_sync_log
    (github_secret_name, vault_secret_name, action, prev_value_sha256, new_value_sha256)
  VALUES ('oauth:' || p_platform, p_vault_secret_name, v_action, v_prev_sha, v_new_sha);

  RETURN jsonb_build_object(
    'action', v_action,
    'vault_name', p_vault_secret_name,
    'changed', v_action IN ('created', 'updated')
  );

EXCEPTION WHEN OTHERS THEN
  INSERT INTO public.gha_credential_sync_log
    (github_secret_name, vault_secret_name, action, error_message)
  VALUES ('oauth:' || COALESCE(p_platform, 'null'), p_vault_secret_name, 'error', SQLERRM);
  RETURN jsonb_build_object('action', 'error', 'reason', SQLERRM);
END;
$function$;

REVOKE ALL ON FUNCTION public.lms_oauth_vault_write(text, text, text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.lms_oauth_vault_write(text, text, text) TO service_role;

-- ---------------------------------------------------------------------------
-- 2. Health upsert -- used both by the OAuth callback (immediate flip on
--    connect) and the Worker's 6h scheduled() cron probe. Read-modify-write
--    on consecutive_failures needs to happen inside the DB, not the Worker,
--    to stay correct under concurrent cron + callback writes.
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.lms_connections_health_upsert(
  p_platform text,
  p_healthy  boolean,
  p_detail   text
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = 'public'
AS $function$
DECLARE
  v_failures int;
BEGIN
  INSERT INTO public.social_token_health (platform, checked_at, healthy, detail, consecutive_failures)
  VALUES (p_platform, now(), p_healthy, p_detail, CASE WHEN p_healthy THEN 0 ELSE 1 END)
  ON CONFLICT (platform) DO UPDATE SET
    checked_at = now(),
    healthy = EXCLUDED.healthy,
    detail = EXCLUDED.detail,
    consecutive_failures = CASE WHEN EXCLUDED.healthy THEN 0 ELSE public.social_token_health.consecutive_failures + 1 END,
    updated_at = now()
  RETURNING consecutive_failures INTO v_failures;

  RETURN jsonb_build_object('ok', true, 'platform', p_platform, 'healthy', p_healthy, 'consecutive_failures', v_failures);
END;
$function$;

REVOKE ALL ON FUNCTION public.lms_connections_health_upsert(text, boolean, text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.lms_connections_health_upsert(text, boolean, text) TO service_role;

-- ---------------------------------------------------------------------------
-- 3. Aggregated read for the /connections tiles -- one round trip instead of
--    the Worker doing two separate rpc() calls + client-side merge.
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.lms_connections_status()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = 'public'
AS $function$
DECLARE
  v_social jsonb;
  v_youtube jsonb;
BEGIN
  SELECT COALESCE(jsonb_agg(jsonb_build_object(
           'platform', platform, 'healthy', healthy, 'detail', detail,
           'checked_at', checked_at, 'consecutive_failures', consecutive_failures
         ) ORDER BY platform), '[]'::jsonb)
    INTO v_social
  FROM public.social_token_health;

  SELECT jsonb_build_object('ok', ok, 'checked_at', checked_at, 'error', error)
    INTO v_youtube
  FROM public.youtube_token_health
  ORDER BY checked_at DESC
  LIMIT 1;

  RETURN jsonb_build_object('social', v_social, 'youtube', COALESCE(v_youtube, 'null'::jsonb));
END;
$function$;

REVOKE ALL ON FUNCTION public.lms_connections_status() FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.lms_connections_status() TO service_role;

-- ---------------------------------------------------------------------------
-- 4. Seed the missing `typefully` row -- #20029's inventory found zero rows
--    (table only seeded instagram/facebook/tiktok/x/linkedin_company).
--    Typefully has no OAuth (static API key, checked live by the cron probe
--    per issue scope item 5), but it needs a row to appear on the tiles grid
--    at all before the first probe runs.
-- ---------------------------------------------------------------------------

INSERT INTO public.social_token_health (platform, checked_at, healthy, detail, consecutive_failures)
VALUES ('typefully', now(), false, 'NOT_CONFIGURED -- TYPEFULLY_API_KEY not set as a Worker secret', 0)
ON CONFLICT (platform) DO NOTHING;
