-- SPRINT4 H1 P0: light WorkOS OAuth on mcp.biddeed.ai — status update
-- dispatch_id: 8bbecf95-cbfa-4643-9749-d95daef6c584
--
-- Extend directory_readiness.status to allow 'blocked_on_key' and
-- 'env_mismatch' (both explicitly required by this mission's task 1/task 4
-- instructions) alongside the existing pass/fail/human_needed values.
-- Non-destructive: widens a CHECK constraint only, no data rewritten.

ALTER TABLE public.directory_readiness DROP CONSTRAINT IF EXISTS directory_readiness_status_check;
ALTER TABLE public.directory_readiness ADD CONSTRAINT directory_readiness_status_check
  CHECK (status IN ('pass', 'fail', 'human_needed', 'blocked_on_key', 'env_mismatch'));

-- oauth_flow: blocked on vault key, with an independent, already-verified
-- finding that will matter the moment the key lands.
INSERT INTO public.directory_readiness (item, status, evidence)
SELECT
  'oauth_flow',
  'blocked_on_key',
  'public.vault_secret(''workos_api_key'') returns NULL — checked live via RPC on 2026-07-03 14:12 UTC '
  'under 5 plausible names (workos_api_key, WORKOS_API_KEY, workos_secret_key, workos_secret, '
  'workos_client_secret), all NULL. Confirmed independently on the live deployment: a tools/call '
  'against https://mcp.biddeed.ai/api/mcp with a JWT-shaped Bearer token returns AUTH_ERROR '
  '"WORKOS_API_KEY and WORKOS_CLIENT_ID must both be set..." (requireWorkosEnv() throwing in '
  'packages/biddeed-mcp/src/oauth.js), i.e. the Vercel env vars are not set either — consistent, '
  'not guessed. Per mission task 1, exiting cleanly here without setting Vercel env vars; re-fire '
  'once Ariel pastes the key into vault will pick this back up.'
  ' '
  'INDEPENDENT FINDING (does not require the key, so recorded now): curl of '
  'https://api.workos.com/user_management/authorize?client_id=client_01KWM0DPZH9KHVSQ6T0V7C8087 '
  '(the WORKOS_CLIENT_ID named in this mission, Sprint1 config) returns HTTP 302 to '
  'https://cheerful-universe-46-staging.authkit.app/bootstrap?... — the AuthKit hostname itself '
  'contains "staging". This means client_01KWM0DPZH9KHVSQ6T0V7C8087 is registered against a STAGING '
  'WorkOS AuthKit environment. If the workos_api_key Ariel pastes is a Production-environment API '
  'key, task 4''s validation will fail with a client/environment mismatch — per mission instructions '
  'this must be reported as status=''env_mismatch'' with exact evidence once the key is available and '
  'tested, not silently guessed at now. Recorded here as CONFIRMED (via curl, not inferred) so the '
  're-fire does not have to rediscover it.'
  ' '
  'ALSO FIXED IN THIS PASS (independent of the key, safe, deployed, verified): the WWW-Authenticate '
  '401 header''s resource_metadata URL was malformed — it concatenated MCP_PUBLIC_URL (which already '
  'includes /api/mcp) with /.well-known/oauth-protected-resource, producing '
  'https://mcp.biddeed.ai/api/mcp/.well-known/oauth-protected-resource, which 404s. Fixed in '
  'packages/biddeed-mcp/src/http.js (wwwAuthenticateHeader now derives the metadata URL from the '
  'resource URL''s origin only) and redeployed to production via vercel CLI (deployment '
  'dpl_283BFnAK4WCyWGr88ahXYguH3Vz1, aliased to mcp.biddeed.ai). Re-verified live 2026-07-03 ~14:15 '
  'UTC: 401 response now advertises resource_metadata="https://mcp.biddeed.ai/.well-known/'
  'oauth-protected-resource", which returns HTTP 200 with the correct RFC 9728 document. Also '
  're-confirmed the existing bd_ key path is untouched: a fake bd_live_ key still correctly returns '
  '{"error":"Invalid API key","code":"AUTH_ERROR"} rather than crashing. Existing oauth.test.js (10/10) '
  'and bd-key-regression.test.js pass unchanged.'
WHERE NOT EXISTS (
  SELECT 1 FROM public.directory_readiness
  WHERE item = 'oauth_flow' AND status IN ('pass', 'blocked_on_key', 'env_mismatch')
);
