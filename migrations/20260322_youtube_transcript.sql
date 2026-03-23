-- Migration: Create youtube_transcript table
-- Run via Supabase SQL Editor or Claude Code psql
-- Date: 2026-03-22

CREATE TABLE IF NOT EXISTS public.youtube_transcript (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  video_id text UNIQUE NOT NULL,
  title text NOT NULL,
  channel text,
  url text NOT NULL,
  duration_seconds int,
  upload_date date,
  tags jsonb DEFAULT '[]'::jsonb,
  ai_summary text,
  ai_insights text,
  relevance_tags text[],
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- RLS
ALTER TABLE public.youtube_transcript ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role full access" ON public.youtube_transcript
  FOR ALL USING (auth.role() = 'service_role');

-- Index for fast lookup
CREATE INDEX IF NOT EXISTS idx_yt_video_id ON public.youtube_transcript(video_id);
CREATE INDEX IF NOT EXISTS idx_yt_upload_date ON public.youtube_transcript(upload_date DESC);

-- Migrate interim data from insights table
INSERT INTO public.youtube_transcript (video_id, title, channel, url, duration_seconds, upload_date, tags, ai_summary, ai_insights, relevance_tags)
SELECT
  (description::jsonb)->>'video_id',
  (description::jsonb)->>'title',
  (description::jsonb)->>'channel',
  (description::jsonb)->>'url',
  ((description::jsonb)->>'duration_seconds')::int,
  ((description::jsonb)->>'upload_date')::date,
  (description::jsonb)->'tags',
  (description::jsonb)->>'ai_summary',
  (description::jsonb)->>'ai_insights',
  ARRAY(SELECT jsonb_array_elements_text((description::jsonb)->'five_rules'))
FROM public.insights
WHERE anomaly_type = 'YOUTUBE_TRANSCRIPT'
ON CONFLICT (video_id) DO NOTHING;

-- Cleanup interim rows
DELETE FROM public.insights WHERE anomaly_type = 'YOUTUBE_TRANSCRIPT';

COMMENT ON TABLE public.youtube_transcript IS 'YouTube transcript insights from Supadata API. Part of YouTube Transcript Squad (cli-anything-biddeed/youtube/).';