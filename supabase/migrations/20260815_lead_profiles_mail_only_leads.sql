-- Lead volume expansion (LLC/corp winning bidders -> lead_profiles).
-- Sunbiz's free public corporate registry does not expose email addresses
-- (confirmed via the official cordata fixed-width layout), so a real share of
-- this batch is mail-only. Widen email to nullable (multiple NULLs are legal
-- under a UNIQUE constraint) and add columns to carry the mailing channel.
ALTER TABLE public.lead_profiles ALTER COLUMN email DROP NOT NULL;

ALTER TABLE public.lead_profiles
  ADD COLUMN IF NOT EXISTS mailing_address text,
  ADD COLUMN IF NOT EXISTS registered_agent text;

COMMENT ON COLUMN public.lead_profiles.mailing_address IS
  'Physical mailing address for postcard/mail outreach when no email is available. Sourced from FL Sunbiz corporate registry mailing/principal address or fl_parcels.own_addr1 fallback.';
COMMENT ON COLUMN public.lead_profiles.registered_agent IS
  'Registered agent name on file with FL Division of Corporations, for corporate_bidder leads sourced from Sunbiz.';
