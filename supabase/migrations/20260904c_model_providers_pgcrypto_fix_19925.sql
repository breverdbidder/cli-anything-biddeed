-- issue #19925 (C6) follow-up — swap pgsodium secretbox for pgcrypto +
-- Vault, matching a real live constraint discovered in the SAME session that
-- wrote 20260904b_model_providers_19925.sql.
--
-- DEVIATION (live-verified 2026-09-04): 20260904b used
-- pgsodium.crypto_secretbox()/crypto_secretbox_noncegen() directly, gated by
-- the `pgsodium_keyholder`/`pgsodium_keyiduser` roles. Live-tested
-- immediately after applying that migration -- calling
-- biddeed_provider_upsert() failed with `42501 permission denied for
-- function crypto_secretbox_noncegen`. Root cause, confirmed by querying
-- pg_proc.proacl directly: those pgsodium functions are executable only by
-- `supabase_admin`/`pgsodium_keyholder`/`pgsodium_keyiduser`/
-- `pgsodium_keymaker`, and `postgres` (the only role this session's
-- SUPABASE_ACCESS_TOKEN Management-API connection can act as) is not a
-- member of any of them -- confirmed via `GRANT pgsodium_keyholder TO
-- postgres` -> `42501 permission denied to grant role... Only roles with
-- the ADMIN option may grant this role`. This is the same category of
-- platform boundary CLAUDE.md's CREDENTIAL HANDLING section already
-- documents for `REVOKE SELECT ON vault.decrypted_secrets FROM
-- service_role` (dashboard-level supabase_admin access required, not
-- available to this session) -- not something to keep retrying.
--
-- Fix: pgcrypto (already installed, confirmed grantable to postgres with no
-- special role needed -- pgp_sym_encrypt/pgp_sym_decrypt round-tripped in a
-- live test) + a single master passphrase stored in Supabase Vault and read
-- through the EXISTING sanctioned accessor public.vault_secret(name)
-- (plain passthrough, EXECUTE already restricted to postgres+service_role
-- per CLAUDE.md CREDENTIAL HANDLING -- no new grant needed). pgp_sym_encrypt
-- embeds its own per-call random salt/IV inside the returned OpenPGP packet
-- (integrity-protected via MDC in this pgcrypto build), so the app no longer
-- manages a separate nonce column -- key_nonce is dropped as dead weight
-- rather than left as an unused NOT NULL landmine.
--
-- Second live bug caught in the same pass: pgcrypto's functions live in the
-- `extensions` schema in this project, and these functions pin `SET
-- search_path = ''` (defense against search_path hijacking) -- so the first
-- attempt at this fix (`pgp_sym_encrypt(...)` unqualified) 42883'd with
-- "function pgp_sym_encrypt(text, text) does not exist". Fixed by
-- schema-qualifying every pgcrypto call (`extensions.pgp_sym_encrypt` /
-- `extensions.pgp_sym_decrypt`), confirmed by the live round-trip test in
-- docs/spec/19925.md.

-- One-time master key, generated with pgcrypto (already proven callable),
-- stored in Vault, read only inside SECURITY DEFINER functions below --
-- never selected into this session/shell.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM vault.decrypted_secrets WHERE name = 'biddeed_user_providers_master_key') THEN
    PERFORM vault.create_secret(
      encode(gen_random_bytes(32), 'hex'),
      'biddeed_user_providers_master_key',
      'AES/pgp_sym passphrase for public.biddeed_user_providers key_ciphertext (issue #19925 C6)'
    );
  END IF;
END $$;

ALTER TABLE public.biddeed_user_providers DROP CONSTRAINT IF EXISTS biddeed_user_providers_check;
ALTER TABLE public.biddeed_user_providers DROP COLUMN IF EXISTS key_nonce;
ALTER TABLE public.biddeed_user_providers ADD CONSTRAINT biddeed_user_providers_check CHECK (
  (provider = 'ollama' AND base_url IS NOT NULL AND key_ciphertext IS NULL)
  OR
  (provider <> 'ollama' AND key_ciphertext IS NOT NULL AND base_url IS NULL)
);

CREATE OR REPLACE FUNCTION public.biddeed_provider_upsert(
  p_owner_email text,
  p_provider text,
  p_api_key text DEFAULT NULL,
  p_base_url text DEFAULT NULL,
  p_model text DEFAULT NULL,
  p_cap_tokens bigint DEFAULT NULL
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
  v_master text;
  v_ciphertext bytea;
  v_last4 text;
  v_owner text := lower(trim(p_owner_email));
  v_row public.biddeed_user_providers;
BEGIN
  IF v_owner IS NULL OR v_owner = '' THEN
    RAISE EXCEPTION 'owner_email required';
  END IF;
  IF p_provider NOT IN ('anthropic', 'openai', 'deepseek', 'gemini', 'openrouter', 'ollama') THEN
    RAISE EXCEPTION 'invalid provider %', p_provider;
  END IF;

  UPDATE public.biddeed_user_providers SET is_active = false
  WHERE owner_email = v_owner AND provider <> p_provider;

  IF p_provider = 'ollama' THEN
    IF p_base_url IS NULL OR p_base_url = '' THEN
      RAISE EXCEPTION 'base_url required for ollama';
    END IF;
    INSERT INTO public.biddeed_user_providers (owner_email, provider, base_url, model, cap_tokens, is_active)
    VALUES (v_owner, p_provider, p_base_url, p_model, p_cap_tokens, true)
    ON CONFLICT (owner_email, provider) DO UPDATE SET
      base_url = EXCLUDED.base_url, model = EXCLUDED.model, cap_tokens = EXCLUDED.cap_tokens,
      is_active = true, disabled_at = NULL
    RETURNING * INTO v_row;
  ELSE
    IF p_api_key IS NULL OR length(p_api_key) < 8 THEN
      RAISE EXCEPTION 'a valid api_key is required for %', p_provider;
    END IF;
    v_master := public.vault_secret('biddeed_user_providers_master_key');
    IF v_master IS NULL THEN
      RAISE EXCEPTION 'encryption key not provisioned';
    END IF;
    v_ciphertext := extensions.pgp_sym_encrypt(p_api_key, v_master);
    v_last4 := right(p_api_key, 4);
    INSERT INTO public.biddeed_user_providers (owner_email, provider, key_ciphertext, key_last4, model, cap_tokens, is_active)
    VALUES (v_owner, p_provider, v_ciphertext, v_last4, p_model, p_cap_tokens, true)
    ON CONFLICT (owner_email, provider) DO UPDATE SET
      key_ciphertext = EXCLUDED.key_ciphertext, key_last4 = EXCLUDED.key_last4,
      model = EXCLUDED.model, cap_tokens = EXCLUDED.cap_tokens, is_active = true, disabled_at = NULL
    RETURNING * INTO v_row;
  END IF;

  RETURN jsonb_build_object(
    'provider', v_row.provider, 'model', v_row.model, 'base_url', v_row.base_url,
    'cap_tokens', v_row.cap_tokens, 'last4', v_row.key_last4, 'is_active', v_row.is_active,
    'created_at', v_row.created_at
  );
END;
$$;

CREATE OR REPLACE FUNCTION public.biddeed_provider_get_decrypted(p_owner_email text, p_provider text)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
  v_row public.biddeed_user_providers;
  v_master text;
  v_api_key text;
BEGIN
  SELECT * INTO v_row FROM public.biddeed_user_providers
  WHERE owner_email = lower(trim(p_owner_email)) AND provider = p_provider AND disabled_at IS NULL
  LIMIT 1;
  IF NOT FOUND THEN RETURN NULL; END IF;

  UPDATE public.biddeed_user_providers SET last_used_at = now() WHERE id = v_row.id;

  IF v_row.provider = 'ollama' THEN
    RETURN jsonb_build_object('provider', v_row.provider, 'base_url', v_row.base_url, 'model', v_row.model, 'cap_tokens', v_row.cap_tokens);
  END IF;

  v_master := public.vault_secret('biddeed_user_providers_master_key');
  v_api_key := extensions.pgp_sym_decrypt(v_row.key_ciphertext, v_master);
  RETURN jsonb_build_object('provider', v_row.provider, 'api_key', v_api_key, 'model', v_row.model, 'cap_tokens', v_row.cap_tokens);
END;
$$;

-- Function signatures are unchanged from 20260904b, so the REVOKE/GRANT
-- EXECUTE statements already applied there still hold (CREATE OR REPLACE
-- preserves existing grants). Re-asserted here anyway, defensively, in case
-- this file is ever applied to a fresh database out of order relative to
-- 20260904b's GRANTs.
REVOKE ALL ON FUNCTION public.biddeed_provider_upsert(text, text, text, text, text, bigint) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.biddeed_provider_upsert(text, text, text, text, text, bigint) TO service_role;
REVOKE ALL ON FUNCTION public.biddeed_provider_get_decrypted(text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.biddeed_provider_get_decrypted(text, text) TO service_role;
