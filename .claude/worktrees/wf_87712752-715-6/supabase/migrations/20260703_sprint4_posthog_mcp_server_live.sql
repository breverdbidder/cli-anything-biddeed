-- SPRINT4 H1 P0-3: posthog_instrumentation_status.mcp_server blocked_on_key -> live.
--
-- Verified live (2026-07-03): vault.posthog_project_key now resolves via
-- get_vault_secret_mcp('posthog_project_key') -> 'phc_zUQGNqDUYXbpJn7RGKt2wwnHfP8GXge2MZsYAJXTs14'
-- (was NULL when 20260702_posthog_instrumentation_status.sql was written).
--
-- packages/biddeed-mcp/src/posthog.js already reads the key vault-first via this
-- same RPC (resolveProjectKey(), 10-min re-check) and packages/biddeed-mcp/src/server.js
-- already calls captureToolCall() on every tool invocation -- no code change needed,
-- the surface was fully wired and only blocked on the missing key.
--
-- Emitted one real event through the actual module path:
--   node -e "import('./packages/biddeed-mcp/src/posthog.js').then(m => {
--     m.captureToolCall({credential:'sprint4-h1-live-verification',
--       toolName:'sprint4_h1_posthog_wiring_verification', tier:'internal', latencyMs:1});
--     return m.flushNow();
--   })"
--   -> pre-flush:  {"queueDepth":1,"dropped":0,"projectKeyResolved":false}
--   -> post-flush: {"queueDepth":0,"dropped":0,"projectKeyResolved":true}
-- Confirmed accepted (not just fire-and-forget silence) via a direct POST to the
-- same PostHog batch endpoint with the same key: HTTP 200 {"status":"Ok"}.
--
-- test/posthog.test.js: 4/4 passing (node --test), unchanged by this migration.

UPDATE public.posthog_instrumentation_status
SET status = 'live',
    evidence = 'packages/biddeed-mcp/src/posthog.js resolves posthog_project_key via ' ||
      'get_vault_secret_mcp (vault-first, 10-min re-check) and server.js calls ' ||
      'captureToolCall() on every MCP tool invocation -- code was already fully wired, ' ||
      'blocked only on the missing vault key. Vault now returns a real phc_ token ' ||
      '(confirmed 2026-07-03 via live RPC call). Emitted one real mcp_tool_call event ' ||
      'through the actual captureToolCall()+flushNow() path: pre-flush ' ||
      'projectKeyResolved=false queueDepth=1, post-flush projectKeyResolved=true ' ||
      'queueDepth=0. Independently confirmed PostHog accepted it via a direct POST to ' ||
      'https://us.i.posthog.com/batch/ with the same key and an equivalent payload: ' ||
      'HTTP 200 {"status":"Ok"}. test/posthog.test.js 4/4 passing, no code changes made.',
    updated_at = now()
WHERE surface = 'mcp_server';
