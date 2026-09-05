-- GTM-5 (#20034): daily-digest consent compliance.
--
-- Root cause: biddeed-daily-digest.yml (workflow 321410535) emailed every
-- lead_profiles row with an email, with no consent filter, since at least
-- Aug 24. lead_profiles already has email_consent/marketing_consent
-- (20260807_lead_profiles_sms_email_consent.sql) but nothing recorded an
-- unsubscribe, and nothing suppressed the people who already unsubscribed
-- (source='unsubscribe_link', 6 rows, email_consent=false) from being
-- re-added or re-sent to by a future pipeline. Additive only per intent
-- guardrail #5 -- no changes to lead_profiles, no deletes, ever.
--
-- Two tables, two jobs:
--   email_opt_outs    -- forward-looking: written by the one-click
--                         unsubscribe link/header on every future send;
--                         the consent gate excludes anyone in here even if
--                         lead_profiles.email_consent is later (re)flipped.
--   email_suppressions -- backward-looking audit trail: every address that
--                         received a digest without consent (the Aug 24-
--                         Sep 4 incident), independent of whether it is
--                         also synced to Resend's audience-contact
--                         suppression signal.
-- Both RLS-enabled, no anon/authenticated policy -- service_role only,
-- same posture as every other compliance table in this repo.

CREATE TABLE IF NOT EXISTS public.email_opt_outs (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email         text NOT NULL UNIQUE,
  opted_out_at  timestamptz NOT NULL DEFAULT now(),
  source        text NOT NULL DEFAULT 'unsubscribe_link',
  reason        text
);

ALTER TABLE public.email_opt_outs ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS public.email_suppressions (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email              text NOT NULL UNIQUE,
  suppressed_at      timestamptz NOT NULL DEFAULT now(),
  reason             text NOT NULL DEFAULT 'non_consented_digest_recipient_gtm5',
  resend_synced      boolean NOT NULL DEFAULT false,
  resend_synced_at   timestamptz
);

ALTER TABLE public.email_suppressions ENABLE ROW LEVEL SECURITY;

-- Backfill: the 6 lead_profiles rows already sourced from a prior
-- unsubscribe (source='unsubscribe_link', email_consent=false,
-- marketing_consent=false) are opted out as of today per intent hard
-- guardrail #2/#4 -- lead_profiles itself is never written by this
-- migration, only this new table.
INSERT INTO public.email_opt_outs (email, source, reason)
SELECT email, 'unsubscribe_link_backfill', 'GTM-5 backfill: source=unsubscribe_link in lead_profiles'
FROM public.lead_profiles
WHERE source = 'unsubscribe_link' AND email IS NOT NULL
ON CONFLICT (email) DO NOTHING;
