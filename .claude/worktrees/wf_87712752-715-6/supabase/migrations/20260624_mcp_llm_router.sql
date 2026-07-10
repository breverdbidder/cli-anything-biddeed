-- MCP → claude-router v4: DB objects
-- Creates llm_requests table (if not exists), adds source/tool_name/tier columns,
-- and vault accessor functions used by the claude-router edge function.

-- 1. Ensure llm_requests exists with all needed columns
CREATE TABLE IF NOT EXISTS public.llm_requests (
  id            bigserial PRIMARY KEY,
  created_at    timestamptz DEFAULT now(),
  source        text,
  tool_name     text,
  provider      text,
  tier          text,
  model         text,
  input_tokens  int,
  output_tokens int,
  cost_usd      numeric(12,8),
  latency_ms    int,
  request_id    text
);

-- Idempotent column adds — safe even if table already existed with extra columns
ALTER TABLE public.llm_requests ADD COLUMN IF NOT EXISTS source text;
ALTER TABLE public.llm_requests ADD COLUMN IF NOT EXISTS tool_name text;
ALTER TABLE public.llm_requests ADD COLUMN IF NOT EXISTS tier text;
ALTER TABLE public.llm_requests ADD COLUMN IF NOT EXISTS request_id text;
ALTER TABLE public.llm_requests ADD COLUMN IF NOT EXISTS input_tokens int;
ALTER TABLE public.llm_requests ADD COLUMN IF NOT EXISTS output_tokens int;
ALTER TABLE public.llm_requests ADD COLUMN IF NOT EXISTS cost_usd numeric(12,8);
ALTER TABLE public.llm_requests ADD COLUMN IF NOT EXISTS latency_ms int;

CREATE INDEX IF NOT EXISTS llm_requests_source_idx ON public.llm_requests (source);
CREATE INDEX IF NOT EXISTS llm_requests_created_idx ON public.llm_requests (created_at DESC);

-- 2. Vault secret reader (SECURITY DEFINER — vault is only accessible to service_role)
CREATE OR REPLACE FUNCTION public.get_vault_secret_mcp(p_name text)
RETURNS text
LANGUAGE sql
SECURITY DEFINER
SET search_path = vault, public
AS $$
  SELECT decrypted_secret
  FROM vault.decrypted_secrets
  WHERE name = p_name
  LIMIT 1;
$$;

-- 3. Proxy key validator — returns true if p_key matches vault.router_proxy_key
CREATE OR REPLACE FUNCTION public.claude_router_validate_key(p_key text)
RETURNS boolean
LANGUAGE sql
SECURITY DEFINER
SET search_path = vault, public
AS $$
  SELECT EXISTS(
    SELECT 1
    FROM vault.decrypted_secrets
    WHERE name = 'router_proxy_key'
      AND decrypted_secret = p_key
  );
$$;

-- Safe defaults for required columns when inserting MCP router rows
-- 'direct' = allowed value in llm_requests_stage_check constraint
ALTER TABLE public.llm_requests ALTER COLUMN stage    SET DEFAULT 'direct';
ALTER TABLE public.llm_requests ALTER COLUMN messages SET DEFAULT '[]'::jsonb;

-- RLS bypass policy for service_role (claude-router edge fn uses service_role key)
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'llm_requests' AND policyname = 'mcp_router_insert'
  ) THEN
    CREATE POLICY mcp_router_insert ON public.llm_requests
      FOR INSERT TO service_role WITH CHECK (true);
  END IF;
END $$;

GRANT EXECUTE ON FUNCTION public.get_vault_secret_mcp(text)      TO service_role;
GRANT EXECUTE ON FUNCTION public.claude_router_validate_key(text) TO service_role;
GRANT INSERT, SELECT ON public.llm_requests TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.llm_requests_id_seq TO service_role;
