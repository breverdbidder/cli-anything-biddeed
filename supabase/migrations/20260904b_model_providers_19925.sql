-- issue #19925 (C6) — model providers for Deed: BYOK + Ollama config +
-- free-tier rate limiting.
--
-- public.biddeed_user_providers stores per-user provider configuration for
-- "bring your own key" (anthropic/openai/deepseek/gemini/openrouter) and for
-- Ollama (base_url + model, no key). API keys are encrypted at rest with
-- pgsodium secretbox using a per-row nonce and a server-managed key
-- (pgsodium.create_key) whose raw bytes are never selectable via SQL --
-- crypto_secretbox(...,key_uuid)/crypto_secretbox_open(...,key_uuid) use the
-- key by reference only. The table itself is fully locked down (RLS on,
-- zero policies, REVOKE ALL from PUBLIC/anon/authenticated/service_role) --
-- the only way to read or write it is through the SECURITY DEFINER
-- functions below, all owned by postgres (owners bypass RLS + implicitly
-- retain EXECUTE on their own functions) with EXECUTE explicitly granted
-- only to service_role. This matches CLAUDE.md's CREDENTIAL HANDLING
-- mandate: the Worker (the only service_role key holder) calls
-- biddeed_provider_get_decrypted()/get_active_decrypted() at request time
-- and uses the plaintext key in-memory to call the provider directly -- the
-- key is never echoed back to the browser (list/upsert return last 4 only)
-- and never logged.
--
-- owner_email trust model matches issue #19829 P1 (see
-- 20260904a_chat_persistence_19829_p1.sql): this app has no Clerk/Supabase
-- Auth, so owner_email here is always derived server-side by the Worker from
-- its signed chat-session token (chatHmacKey/verifyChatToken in
-- src/worker.js) before calling these functions -- never trusted from a raw
-- client-supplied value.

CREATE TABLE IF NOT EXISTS public.biddeed_user_providers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_email text NOT NULL,
  provider text NOT NULL CHECK (provider IN ('anthropic', 'openai', 'deepseek', 'gemini', 'openrouter', 'ollama')),
  key_ciphertext bytea,
  key_nonce bytea,
  key_last4 text,
  base_url text,
  model text,
  cap_tokens bigint,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  last_used_at timestamptz,
  disabled_at timestamptz,
  UNIQUE (owner_email, provider),
  CHECK (
    (provider = 'ollama' AND base_url IS NOT NULL AND key_ciphertext IS NULL AND key_nonce IS NULL)
    OR
    (provider <> 'ollama' AND key_ciphertext IS NOT NULL AND key_nonce IS NOT NULL AND base_url IS NULL)
  )
);
CREATE INDEX IF NOT EXISTS biddeed_user_providers_owner_idx ON public.biddeed_user_providers (owner_email);
CREATE INDEX IF NOT EXISTS biddeed_user_providers_active_idx ON public.biddeed_user_providers (owner_email) WHERE is_active AND disabled_at IS NULL;

ALTER TABLE public.biddeed_user_providers ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.biddeed_user_providers FROM PUBLIC, anon, authenticated, service_role;

-- Server-managed pgsodium key. Idempotent: pgsodium.create_key() has no
-- built-in "IF NOT EXISTS", so guard manually against re-running this
-- migration creating a second key with the same name (which would orphan
-- ciphertext encrypted under the first one).
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pgsodium.valid_key WHERE name = 'biddeed_user_providers_key') THEN
    PERFORM pgsodium.create_key(key_type => 'secretbox', name => 'biddeed_user_providers_key');
  END IF;
END $$;

-- ── biddeed_provider_upsert — Worker-only. Encrypts p_api_key (BYOK) or
-- stores base_url (Ollama), sets the saved provider active and deactivates
-- any other provider for the same owner (single active BYOK/Ollama provider
-- routes a user's chat at a time). Returns metadata only (last4, never the
-- key). ──────────────────────────────────────────────────────────────────
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
  v_key_id uuid;
  v_nonce bytea;
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
    SELECT id INTO v_key_id FROM pgsodium.valid_key WHERE name = 'biddeed_user_providers_key';
    IF v_key_id IS NULL THEN
      RAISE EXCEPTION 'encryption key not provisioned';
    END IF;
    v_nonce := pgsodium.crypto_secretbox_noncegen();
    v_ciphertext := pgsodium.crypto_secretbox(convert_to(p_api_key, 'utf8'), v_nonce, v_key_id);
    v_last4 := right(p_api_key, 4);
    INSERT INTO public.biddeed_user_providers (owner_email, provider, key_ciphertext, key_nonce, key_last4, model, cap_tokens, is_active)
    VALUES (v_owner, p_provider, v_ciphertext, v_nonce, v_last4, p_model, p_cap_tokens, true)
    ON CONFLICT (owner_email, provider) DO UPDATE SET
      key_ciphertext = EXCLUDED.key_ciphertext, key_nonce = EXCLUDED.key_nonce, key_last4 = EXCLUDED.key_last4,
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
REVOKE ALL ON FUNCTION public.biddeed_provider_upsert(text, text, text, text, text, bigint) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.biddeed_provider_upsert(text, text, text, text, text, bigint) TO service_role;

-- ── biddeed_provider_list — metadata only (no key material ever leaves
-- this function set). ───────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.biddeed_provider_list(p_owner_email text)
RETURNS SETOF jsonb
LANGUAGE sql
SECURITY DEFINER
SET search_path = ''
AS $$
  SELECT jsonb_build_object(
    'provider', provider, 'model', model, 'base_url', base_url, 'cap_tokens', cap_tokens,
    'last4', key_last4, 'is_active', is_active, 'created_at', created_at,
    'last_used_at', last_used_at, 'disabled_at', disabled_at
  )
  FROM public.biddeed_user_providers
  WHERE owner_email = lower(trim(p_owner_email))
  ORDER BY created_at DESC;
$$;
REVOKE ALL ON FUNCTION public.biddeed_provider_list(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.biddeed_provider_list(text) TO service_role;

-- ── biddeed_provider_delete — hard delete, scoped to owner+provider. ─────
CREATE OR REPLACE FUNCTION public.biddeed_provider_delete(p_owner_email text, p_provider text)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE v_deleted int;
BEGIN
  DELETE FROM public.biddeed_user_providers
  WHERE owner_email = lower(trim(p_owner_email)) AND provider = p_provider;
  GET DIAGNOSTICS v_deleted = ROW_COUNT;
  RETURN v_deleted > 0;
END;
$$;
REVOKE ALL ON FUNCTION public.biddeed_provider_delete(text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.biddeed_provider_delete(text, text) TO service_role;

-- ── biddeed_provider_get_decrypted — INTERNAL, sensitive. Decrypts and
-- returns the plaintext key for owner+provider, scoped strictly to that
-- owner (cross-user calls simply return NULL — proven in docs/spec/19925.md).
-- Bumps last_used_at as a side effect. service_role only; the Worker uses
-- this in-memory to call the provider directly, never returns api_key to
-- the browser, never logs it. ─────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.biddeed_provider_get_decrypted(p_owner_email text, p_provider text)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
  v_row public.biddeed_user_providers;
  v_key_id uuid;
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

  SELECT id INTO v_key_id FROM pgsodium.valid_key WHERE name = 'biddeed_user_providers_key';
  v_api_key := convert_from(pgsodium.crypto_secretbox_open(v_row.key_ciphertext, v_row.key_nonce, v_key_id), 'utf8');
  RETURN jsonb_build_object('provider', v_row.provider, 'api_key', v_api_key, 'model', v_row.model, 'cap_tokens', v_row.cap_tokens);
END;
$$;
REVOKE ALL ON FUNCTION public.biddeed_provider_get_decrypted(text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.biddeed_provider_get_decrypted(text, text) TO service_role;

-- ── biddeed_provider_get_active_decrypted — INTERNAL, sensitive. Same
-- contract as above, but resolves "whichever provider is this owner's
-- active one" -- what /chat/api calls when X-Chat-Provider: byok|ollama. ──
CREATE OR REPLACE FUNCTION public.biddeed_provider_get_active_decrypted(p_owner_email text)
RETURNS jsonb
LANGUAGE sql
SECURITY DEFINER
SET search_path = ''
AS $$
  SELECT public.biddeed_provider_get_decrypted(p_owner_email, provider)
  FROM public.biddeed_user_providers
  WHERE owner_email = lower(trim(p_owner_email)) AND is_active = true AND disabled_at IS NULL
  LIMIT 1;
$$;
REVOKE ALL ON FUNCTION public.biddeed_provider_get_active_decrypted(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.biddeed_provider_get_active_decrypted(text) TO service_role;

-- ── Free-tier hard rate limit ─────────────────────────────────────────────
-- Anonymous/free-tier chat (X-Chat-Provider: free, routed to claude-router's
-- new `free` tier -- see supabase/functions/claude-router/index.ts) gets a
-- much tighter cap than the existing multi-window chat_rate_check_v2 IP
-- limiter, tracked separately so tightening/loosening the free tier never
-- touches the existing paid/Smart-Router rate limits. Same anon-EXECUTE
-- shape as chat_rate_check_v2 (20260731t_chat_rate_limit_v2_multiwindow.sql)
-- since the Worker calls this with SUPABASE_KEY (anon), not service_role.
CREATE TABLE IF NOT EXISTS public.biddeed_free_tier_hits (
  ip_hash text NOT NULL,
  day date NOT NULL DEFAULT CURRENT_DATE,
  hits int NOT NULL DEFAULT 0,
  PRIMARY KEY (ip_hash, day)
);
ALTER TABLE public.biddeed_free_tier_hits ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.biddeed_free_tier_hits FROM PUBLIC, anon, authenticated;

CREATE OR REPLACE FUNCTION public.biddeed_free_tier_rate_check(p_ip_hash text, p_max_per_day int DEFAULT 8)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE v_hits int;
BEGIN
  INSERT INTO public.biddeed_free_tier_hits (ip_hash, day, hits)
  VALUES (p_ip_hash, CURRENT_DATE, 1)
  ON CONFLICT (ip_hash, day) DO UPDATE SET hits = public.biddeed_free_tier_hits.hits + 1
  RETURNING hits INTO v_hits;

  RETURN jsonb_build_object('allowed', v_hits <= p_max_per_day, 'hits', v_hits, 'limit', p_max_per_day);
END;
$$;
REVOKE ALL ON FUNCTION public.biddeed_free_tier_rate_check(text, int) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.biddeed_free_tier_rate_check(text, int) TO anon;
