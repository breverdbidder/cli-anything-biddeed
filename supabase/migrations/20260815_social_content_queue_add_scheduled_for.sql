-- social_content_queue day-based publish pacing (issue #19088)
--
-- The publish workers (social-publish-worker, social-publish-worker-telegram)
-- select up to 10 pending rows per run ordered by created_at ascending, with
-- no per-day cap -- confirmed by reading the deployed function source via the
-- Management API (no pacing logic exists today, as issue #19088 suspected).
--
-- scheduled_for gates eligibility: a row is publishable once
-- scheduled_for <= current_date. Existing rows and any future insert from the
-- untouched county_snapshot generator get the DEFAULT (yesterday), which
-- keeps them immediately eligible -- zero behavior change for that path.
-- property_spotlight rows set this explicitly to stagger publication.
ALTER TABLE public.social_content_queue
  ADD COLUMN IF NOT EXISTS scheduled_for date NOT NULL DEFAULT (current_date - 1);

COMMENT ON COLUMN public.social_content_queue.scheduled_for IS
  'Row is eligible to publish once scheduled_for <= current_date. Default (yesterday) preserves prior no-pacing behavior for existing/county_snapshot rows.';
