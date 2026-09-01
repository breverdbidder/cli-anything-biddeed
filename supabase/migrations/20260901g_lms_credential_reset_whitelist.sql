-- P1: self-service LMS credential reset workflow (issue: LMS/admin forgot-password).
-- Extends sync_credential_from_gha's whitelist so
-- .github/workflows/lms-credential-reset.yml can propagate a freshly
-- generated LMS_AUTH_USER/LMS_AUTH_PASS pair into vault.secrets the same
-- gated way every other GHA->vault write already works (see
-- 20260803_telegram_vault_sync_whitelist.sql for the prior precedent).
-- No new SQL surface — reuses the existing SECURITY DEFINER function,
-- whitelist-gated, audit-logged to gha_credential_sync_log.
CREATE OR REPLACE FUNCTION public.sync_credential_from_gha(p_github_secret_name text, p_vault_secret_name text, p_value text, p_workflow_run_id bigint DEFAULT NULL::bigint, p_workflow_run_url text DEFAULT NULL::text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'vault', 'public', 'extensions'
AS $function$
DECLARE
  v_allowed_map  jsonb;
  v_expected_vault_name text;
  v_existing_id  uuid;
  v_existing_val text;
  v_prev_sha     text;
  v_new_sha      text;
  v_action       text;
BEGIN
  -- WHITELIST: explicit GH-secret → vault-name mapping. Anything not here is
  -- rejected. ANTHROPIC_API_KEY intentionally absent per ariel-rule.
  v_allowed_map := jsonb_build_object(
    'CLAUDE_CODE_OAUTH_TOKEN',   'anthropic_oauth_bearer',
    'CLAUDE_CODE_REFRESH_TOKEN', 'anthropic_oauth_refresh_token',
    'GEMINI_API_KEY',            'gemini_api_key',
    'BIDDEED_BOT_TOKEN',         'telegram_bot_token',
    'BIDDEED_BOT_CHAT_ID',       'telegram_chat_id',
    'LMS_AUTH_USER',             'lms_auth_user',
    'LMS_AUTH_PASS',             'lms_auth_pass'
  );

  -- Hard block on the banned secret regardless of how it's named
  IF UPPER(p_github_secret_name) IN ('ANTHROPIC_API_KEY','ANTHROPIC_APIKEY','CLAUDE_API_KEY') THEN
    INSERT INTO public.gha_credential_sync_log
      (github_secret_name, vault_secret_name, action, workflow_run_id, workflow_run_url, error_message)
    VALUES (p_github_secret_name, p_vault_secret_name, 'skipped_banned',
            p_workflow_run_id, p_workflow_run_url,
            'BLOCKED per ariel-rule: anthropic_api_key path is not permitted');
    RETURN jsonb_build_object('action','skipped_banned','reason','ariel_rule');
  END IF;

  -- Whitelist enforcement
  v_expected_vault_name := v_allowed_map ->> p_github_secret_name;
  IF v_expected_vault_name IS NULL THEN
    INSERT INTO public.gha_credential_sync_log
      (github_secret_name, vault_secret_name, action, workflow_run_id, workflow_run_url, error_message)
    VALUES (p_github_secret_name, p_vault_secret_name, 'error',
            p_workflow_run_id, p_workflow_run_url,
            'github_secret_name not in whitelist');
    RETURN jsonb_build_object('action','error','reason','not_whitelisted');
  END IF;

  -- Caller must use the canonical vault name
  IF v_expected_vault_name <> p_vault_secret_name THEN
    INSERT INTO public.gha_credential_sync_log
      (github_secret_name, vault_secret_name, action, workflow_run_id, workflow_run_url, error_message)
    VALUES (p_github_secret_name, p_vault_secret_name, 'error',
            p_workflow_run_id, p_workflow_run_url,
            format('vault name mismatch: expected %s got %s', v_expected_vault_name, p_vault_secret_name));
    RETURN jsonb_build_object('action','error','reason','vault_name_mismatch',
                              'expected', v_expected_vault_name);
  END IF;

  -- Empty or null value is a soft error (don't break the chain)
  IF p_value IS NULL OR p_value = '' THEN
    INSERT INTO public.gha_credential_sync_log
      (github_secret_name, vault_secret_name, action, workflow_run_id, workflow_run_url, error_message)
    VALUES (p_github_secret_name, p_vault_secret_name, 'error',
            p_workflow_run_id, p_workflow_run_url,
            'empty value');
    RETURN jsonb_build_object('action','error','reason','empty_value');
  END IF;

  v_new_sha := encode(extensions.digest(p_value, 'sha256'), 'hex');

  -- Look up existing entry
  SELECT s.id, ds.decrypted_secret
    INTO v_existing_id, v_existing_val
  FROM vault.secrets s
  LEFT JOIN vault.decrypted_secrets ds ON ds.id = s.id
  WHERE s.name = p_vault_secret_name
  LIMIT 1;

  IF v_existing_id IS NULL THEN
    -- Create new vault entry
    PERFORM vault.create_secret(
      p_value,
      p_vault_secret_name,
      format('Synced from GitHub secret %s. Managed by sync_credential_from_gha — do not edit manually.', p_github_secret_name)
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
    (github_secret_name, vault_secret_name, action,
     prev_value_sha256, new_value_sha256,
     workflow_run_id, workflow_run_url)
  VALUES (p_github_secret_name, p_vault_secret_name, v_action,
          v_prev_sha, v_new_sha,
          p_workflow_run_id, p_workflow_run_url);

  RETURN jsonb_build_object(
    'action',       v_action,
    'vault_name',   p_vault_secret_name,
    'prev_sha8',    LEFT(COALESCE(v_prev_sha,''),8),
    'new_sha8',     LEFT(v_new_sha,8),
    'changed',      v_action IN ('created','updated')
  );

EXCEPTION WHEN OTHERS THEN
  INSERT INTO public.gha_credential_sync_log
    (github_secret_name, vault_secret_name, action, workflow_run_id, workflow_run_url, error_message)
  VALUES (p_github_secret_name, p_vault_secret_name, 'error',
          p_workflow_run_id, p_workflow_run_url,
          SQLERRM);
  RETURN jsonb_build_object('action','error','reason', SQLERRM);
END;
$function$;
