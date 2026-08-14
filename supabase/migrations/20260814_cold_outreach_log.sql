-- Migration: cold_outreach_log
-- Tracks every cold email sent via the acquisition sprint CAN-SPAM campaign.
-- Rows are append-only; one row per Resend API call attempt.

CREATE TABLE IF NOT EXISTS public.cold_outreach_log (
  id              BIGSERIAL PRIMARY KEY,
  lead_id         BIGINT,
  email           TEXT NOT NULL,
  resend_message_id TEXT,
  status          TEXT NOT NULL DEFAULT 'pending',
  subject         TEXT,
  template        TEXT,
  sent_at         TIMESTAMPTZ,
  error           TEXT,
  county          TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cold_outreach_log_email  ON public.cold_outreach_log(email);
CREATE INDEX IF NOT EXISTS idx_cold_outreach_log_status ON public.cold_outreach_log(status);
CREATE INDEX IF NOT EXISTS idx_cold_outreach_log_sent   ON public.cold_outreach_log(sent_at);

ALTER TABLE public.cold_outreach_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY cold_outreach_log_service_only ON public.cold_outreach_log
  USING (false)
  WITH CHECK (false);

COMMENT ON TABLE public.cold_outreach_log IS
  'CAN-SPAM compliant cold outreach log. One row per send attempt. resend_message_id confirms delivery accepted by Resend API.';
