-- Issue #19847 Pass 3 — S3 progressive disclosure for Projects.
--
-- The project report side panel needs to know whether a real, PAID SIGNAL$
-- Property Report has ever landed against a project, so it can render the
-- 18 section names locked (blurred placeholder values) vs. unlocked. That
-- state has to live somewhere durable and project-scoped; biddeed_reports
-- (supabase/migrations/20260904b_deal_rooms_reports_19847_c3.sql, already
-- live in production — verified this session via a permission-denied anon
-- probe, which only returns for tables that exist) already has project_id
-- and owner_email, so two nullable columns are enough:
--   paid_at  — set ONLY by the Stripe webhook's best-effort linking after a
--              genuine s5_onetime purchase (see supabase/functions/
--              stripe-webhook/index.ts); never set by any Worker route or
--              the client. NULL means "not paid" — the panel's default,
--              locked state.
--   mca_id   — the multi_county_auctions row the paid report is for, so the
--              panel can deep-link to the existing /report/:mca_id page
--              once unlocked, instead of re-deriving it from case_number.
--
-- File-only, per this repo's standing rule: DDL ships in the PR and is
-- applied at merge, never from the runner.
ALTER TABLE public.biddeed_reports
  ADD COLUMN IF NOT EXISTS paid_at timestamptz,
  ADD COLUMN IF NOT EXISTS mca_id uuid;

CREATE INDEX IF NOT EXISTS biddeed_reports_project_paid_idx
  ON public.biddeed_reports (project_id)
  WHERE paid_at IS NOT NULL;
