-- Migration: PostHog instrumentation status — mcp_server + b2c_page surfaces
-- Created: 2026-07-02 | Idempotent: safe to re-run
-- Sprint3 P0-4
--
-- Vault check (live, 2026-07-02): tried get_vault_secret_mcp() against
-- 'posthog_project_key', 'posthog_key', 'POSTHOG_PROJECT_KEY', 'posthog_api_key',
-- 'posthog_project_api_key' — all NULL. `gh secret list` on this repo has no
-- POSTHOG_* entry either. A real PostHog project DOES exist in the org
-- (zonewise-web ships lib/posthog.ts + NEXT_PUBLIC_POSTHOG_KEY GH secret,
-- project "US Cloud 35462x" per zonewise-web/docs/POSTHOG-DASHBOARD.md), but
-- GH Actions secrets are write-only — the token value cannot be read back
-- from here, and it lives in a different repo's secret store. Both surfaces
-- are therefore honestly 'blocked_on_key', not 'live': code is fully wired
-- (packages/biddeed-mcp/src/posthog.js resolves the vault secret on every
-- flush with a 10-min re-check, so a key added later activates without a
-- redeploy; biddeed-mcp/start/index.html in everest-battle-cards has the full
-- PostHog loader gated behind a POSTHOG_KEY constant, same activation model).
--
-- Reconciliation query (mcp_tool_call vs billing_events — see posthog.js
-- header comment for the full version): once PostHog data lands in a
-- queryable store (warehouse sync or manual export), compare per-tool-name
-- counts in a matching time window; billed > posthog_seen means the fire-
-- and-forget queue dropped events or the vault key was unset for that
-- window — both cases must be visible, not silently absorbed.

CREATE TABLE IF NOT EXISTS public.posthog_instrumentation_status (
  surface     TEXT PRIMARY KEY,
  status      TEXT NOT NULL CHECK (status IN ('live', 'blocked_on_key', 'fail')),
  evidence    TEXT NOT NULL,
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO public.posthog_instrumentation_status (surface, status, evidence, updated_at)
VALUES
  (
    'mcp_server',
    'blocked_on_key',
    'packages/biddeed-mcp/src/posthog.js wired (mcp_tool_call event, sha256 distinct_id, ' ||
    'batched fire-and-forget queue, drop-on-overflow, tests in test/posthog.test.js all pass) ' ||
    'and called from src/server.js alongside recordBilling(). No posthog_project_key found in ' ||
    'Supabase Vault (checked 5 candidate names via get_vault_secret_mcp, all NULL) or in this ' ||
    'repo''s GH secrets (gh secret list, no POSTHOG_* key). Re-checks vault every 10 min at ' ||
    'runtime — activates automatically once vault.create_secret(<phc_ token>, ''posthog_project_key'') is run.',
    now()
  ),
  (
    'b2c_page',
    'blocked_on_key',
    'everest-battle-cards biddeed-mcp/start/index.html patched: full PostHog JS loader snippet ' ||
    'added, gated behind var POSTHOG_KEY (empty string = no-op, verified via Playwright headless ' ||
    '— no console/page errors, window.posthog stays undefined, signup form still POSTs and shows ' ||
    'success/duplicate messaging unchanged). b2c_signup_submitted and b2c_signup_success(locale, ' ||
    'already_registered) events wired via a defensive phCapture() helper. No phc_ project token is ' ||
    'retrievable from here — GH Actions secrets are write-only and the org''s known PostHog project ' ||
    '(zonewise-web, "US Cloud 35462x") keeps its key in a different repo''s secret store. Paste the ' ||
    'real token into the POSTHOG_KEY constant to activate; no other code changes needed.',
    now()
  )
ON CONFLICT (surface) DO UPDATE SET
  status = EXCLUDED.status,
  evidence = EXCLUDED.evidence,
  updated_at = EXCLUDED.updated_at;
