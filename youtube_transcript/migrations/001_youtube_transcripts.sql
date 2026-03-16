-- YouTube Transcripts Table for BidDeed.AI
-- Migration: 001_youtube_transcripts.sql

CREATE TABLE IF NOT EXISTS youtube_transcripts (
    id BIGSERIAL PRIMARY KEY,
    video_id TEXT NOT NULL UNIQUE,
    title TEXT,
    video_url TEXT,
    analysis JSONB DEFAULT '{}',
    word_count INTEGER DEFAULT 0,
    relevance_score INTEGER DEFAULT 0,
    pipeline_version TEXT DEFAULT 'v1.0',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for quick lookups
CREATE INDEX IF NOT EXISTS idx_yt_video_id ON youtube_transcripts(video_id);
CREATE INDEX IF NOT EXISTS idx_yt_relevance ON youtube_transcripts(relevance_score DESC);
CREATE INDEX IF NOT EXISTS idx_yt_created ON youtube_transcripts(created_at DESC);

-- Updated_at trigger
CREATE OR REPLACE FUNCTION update_yt_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_yt_updated_at ON youtube_transcripts;
CREATE TRIGGER trg_yt_updated_at
    BEFORE UPDATE ON youtube_transcripts
    FOR EACH ROW EXECUTE FUNCTION update_yt_updated_at();

-- RLS (allow service key full access)
ALTER TABLE youtube_transcripts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service key full access" ON youtube_transcripts
    FOR ALL USING (true) WITH CHECK (true);
