-- Daily multi-county auction result banner + social post generator
-- Issue: daily banner + post spotlighting a real completed FL auction,
-- rotating across counties. See scripts/generate_daily_auction_banner.py.

-- Tracks which county was featured on which day so the generator can
-- exclude counties used in the last 7 days and rotate across all 58+.
CREATE TABLE IF NOT EXISTS public.social_banner_history (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  county text NOT NULL,
  property_id text NOT NULL,
  posted_date date NOT NULL DEFAULT CURRENT_DATE,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS social_banner_history_county_date_idx
  ON public.social_banner_history (county, posted_date);

ALTER TABLE public.social_banner_history ENABLE ROW LEVEL SECURITY;

-- service_role only (matches social_content_queue posture -- no anon access)
CREATE POLICY social_banner_history_service_role
  ON public.social_banner_history
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- Banner PNGs are uploaded to the 'social-banners' storage bucket; this
-- column stores the public URL so the queue row is self-contained.
ALTER TABLE public.social_content_queue
  ADD COLUMN IF NOT EXISTS media_url text;

-- 'draft' status: generated but never picked up by social-publish-cron.yml
-- (which only queries status='pending'). LinkedIn OAuth isn't connected yet,
-- so auction-banner rows must stay out of the auto-publish path until a
-- human promotes them.
ALTER TABLE public.social_content_queue
  DROP CONSTRAINT IF EXISTS social_content_queue_status_check;
ALTER TABLE public.social_content_queue
  ADD CONSTRAINT social_content_queue_status_check
  CHECK (status = ANY (ARRAY['pending'::text, 'published'::text, 'failed'::text, 'skipped_duplicate'::text, 'draft'::text]));
