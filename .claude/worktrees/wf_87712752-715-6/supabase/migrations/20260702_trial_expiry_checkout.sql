-- Migration: Trial expiry enforcement — 7-day read-only grace, then hard cutoff
-- Created: 2026-07-02 | Idempotent: safe to re-run
-- Dispatch: 93837408-be24-4f55-b57e-b40599aef97f (SPRINT3 P0-3)
--
-- Schema inventory note (verified live via Supabase Management API, NOT from
-- this repo's migration files, which have drifted from prod on this table):
--   mcp_api_keys already has key_id/customer_id (UUID), tier, is_active,
--   active, expires_at, stripe_customer_id, revoked_at — no ALTERs needed.
--   stripe_checkout_sessions and mcp_subscription_tiers ALREADY EXIST in prod
--   (session_id PK, customer_id/tier_id FKs, status CHECK IN
--   ('pending','complete','expired','cancelled')) — not created here, out of
--   scope for this dispatch, and IF NOT EXISTS'ing a guessed schema for them
--   would risk masking the real one. biddeed-checkout (supabase/functions)
--   and webhook.js post-processing (packages/biddeed-mcp/src/webhook.js) read
--   /write those tables directly via PostgREST.
--
-- No tier value literally named 'trial' or 'investor-trial' exists (CONFIRMED
-- — checked live). Trial vs. paid is distinguished the same way
-- b2c_activate_signups() already encodes it: expires_at IS NOT NULL means
-- "still trialing (or a trial past due)"; the checkout webhook clears
-- expires_at to NULL on upgrade, which is this migration's definition of
-- "no longer a trial".
--
-- Grace model: expires_at -> expires_at+7d is a read-only grace window
-- enforced at request time in auth.js (validateKey/assertTier — free-tier
-- streams only). This function is the daily bookkeeping pass: once a key is
-- past the full grace window, it flips is_active/active to FALSE so the key
-- shows up correctly in any dashboard/report querying is_active, independent
-- of whether the key is ever called again. auth.js's own expires_at+grace
-- check is the actual security boundary and does not depend on this cron
-- having run yet (same "app-layer is the boundary" convention as
-- 20260623_mcp_core_tables.sql).

CREATE OR REPLACE FUNCTION public.mcp_trial_expiry_enforce()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $fn$
DECLARE
  v_cutoff INT := 0;
BEGIN
  UPDATE public.mcp_api_keys
  SET is_active  = FALSE,
      active     = FALSE,
      revoked_at = COALESCE(revoked_at, now())
  WHERE expires_at IS NOT NULL
    AND expires_at + INTERVAL '7 days' < now()
    AND is_active = TRUE;
  GET DIAGNOSTICS v_cutoff = ROW_COUNT;

  RETURN jsonb_build_object('hard_cutoff', v_cutoff, 'ran_at', now());
END;
$fn$;

-- ── pg_cron: daily hard-cutoff sweep ─────────────────────────────────────────
SELECT cron.schedule('mcp-trial-expiry-enforce-daily', '0 6 * * *', $$SELECT public.mcp_trial_expiry_enforce();$$)
WHERE NOT EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'mcp-trial-expiry-enforce-daily');
