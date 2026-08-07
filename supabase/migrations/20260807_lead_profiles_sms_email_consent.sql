-- Issue: cold send consent + free report lead capture + SMS opt-in.
-- Adds phone + explicit per-channel consent tracking to lead_profiles so the
-- new /free-report capture flow can record opt-in separately for email vs
-- SMS (marketing_consent already exists but is a single undifferentiated
-- flag — SMS sending is a future task and needs its own consent record now,
-- before any SMS capability exists, per TCPA opt-in requirements).
ALTER TABLE public.lead_profiles
  ADD COLUMN IF NOT EXISTS phone text,
  ADD COLUMN IF NOT EXISTS sms_consent boolean DEFAULT false,
  ADD COLUMN IF NOT EXISTS sms_consent_at timestamptz,
  ADD COLUMN IF NOT EXISTS email_consent boolean DEFAULT false,
  ADD COLUMN IF NOT EXISTS email_consent_at timestamptz;
