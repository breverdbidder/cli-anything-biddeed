-- 1. Agent Brain
CREATE TABLE IF NOT EXISTS viral_agent_brain (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  identity jsonb NOT NULL DEFAULT '{}',
  icp jsonb NOT NULL DEFAULT '{}',
  pillars jsonb NOT NULL DEFAULT '[]',
  platforms jsonb NOT NULL DEFAULT '{}',
  competitors jsonb NOT NULL DEFAULT '[]',
  cadence jsonb NOT NULL DEFAULT '{}',
  monetization jsonb NOT NULL DEFAULT '{}',
  learning_weights jsonb NOT NULL DEFAULT '{"icp_relevance":1.0,"timeliness":1.0,"content_gap":1.0,"proof_potential":1.0}',
  hook_preferences jsonb NOT NULL DEFAULT '{"contradiction":0,"specificity":0,"timeframe_tension":0,"pov_as_advice":0,"vulnerable_confession":0,"pattern_interrupt":0}',
  visual_patterns jsonb NOT NULL DEFAULT '{}',
  performance_patterns jsonb NOT NULL DEFAULT '{}',
  audience_blockers jsonb NOT NULL DEFAULT '[]',
  content_jobs jsonb NOT NULL DEFAULT '{}',
  metadata jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- 2. Topics
CREATE TABLE IF NOT EXISTS viral_topics (
  id text PRIMARY KEY,
  title text NOT NULL,
  description text DEFAULT '',
  source jsonb NOT NULL DEFAULT '{}',
  discovered_at timestamptz DEFAULT now(),
  scoring jsonb NOT NULL DEFAULT '{}',
  pillars jsonb NOT NULL DEFAULT '[]',
  competitor_coverage jsonb NOT NULL DEFAULT '[]',
  status text NOT NULL DEFAULT 'new',
  notes text DEFAULT '',
  created_at timestamptz DEFAULT now()
);

-- 3. Angles
CREATE TABLE IF NOT EXISTS viral_angles (
  id text PRIMARY KEY,
  topic_id text,
  format text NOT NULL,
  title text NOT NULL,
  contrast jsonb NOT NULL DEFAULT '{}',
  target_audience text DEFAULT '',
  pain_addressed text DEFAULT '',
  proof_method text DEFAULT '',
  funnel_direction jsonb NOT NULL DEFAULT '{}',
  competitor_angles jsonb NOT NULL DEFAULT '[]',
  content_job text DEFAULT '',
  blocker_destroyed text DEFAULT '',
  status text NOT NULL DEFAULT 'draft',
  notes text DEFAULT '',
  created_at timestamptz DEFAULT now()
);

-- 4. Hooks
CREATE TABLE IF NOT EXISTS viral_hooks (
  id text PRIMARY KEY,
  angle_id text,
  platform text NOT NULL,
  pattern text NOT NULL,
  hook_text text NOT NULL,
  visual_cue text DEFAULT '',
  score jsonb NOT NULL DEFAULT '{}',
  cta_pairing text DEFAULT '',
  status text NOT NULL DEFAULT 'draft',
  source text DEFAULT 'original',
  swipe_reference text DEFAULT '',
  performance jsonb NOT NULL DEFAULT '{}',
  notes text DEFAULT '',
  created_at timestamptz DEFAULT now()
);

-- 5. Scripts
CREATE TABLE IF NOT EXISTS viral_scripts (
  id text PRIMARY KEY,
  angle_id text,
  hook_ids jsonb NOT NULL DEFAULT '[]',
  platform text NOT NULL,
  title text NOT NULL,
  script_structure jsonb,
  filming_cards jsonb,
  shortform_structure jsonb,
  estimated_duration text DEFAULT '',
  status text NOT NULL DEFAULT 'draft',
  performance jsonb NOT NULL DEFAULT '{}',
  notes text DEFAULT '',
  created_at timestamptz DEFAULT now()
);

-- 6. Analytics
CREATE TABLE IF NOT EXISTS viral_analytics (
  id text PRIMARY KEY,
  content_id text NOT NULL,
  platform text NOT NULL,
  published_at timestamptz,
  analyzed_at timestamptz DEFAULT now(),
  days_since_publish integer DEFAULT 0,
  metrics jsonb NOT NULL DEFAULT '{}',
  thumbnail jsonb,
  hook_pattern_used text,
  topic_category text,
  content_pillar text,
  is_winner boolean DEFAULT false,
  winner_reason text,
  winner_metrics jsonb,
  collection_method text DEFAULT 'user_input',
  source_url text,
  notes text DEFAULT '',
  created_at timestamptz DEFAULT now()
);

-- 7. Swipe Hooks
CREATE TABLE IF NOT EXISTS viral_swipe_hooks (
  id text PRIMARY KEY,
  hook_text text NOT NULL,
  pattern text NOT NULL,
  why_it_works text DEFAULT '',
  visual_hook jsonb NOT NULL DEFAULT '{}',
  competitor text DEFAULT '',
  platform text DEFAULT '',
  url text DEFAULT '',
  engagement jsonb NOT NULL DEFAULT '{}',
  competitor_angle text DEFAULT '',
  topic_keywords jsonb NOT NULL DEFAULT '[]',
  source_video_title text DEFAULT '',
  used_count integer DEFAULT 0,
  notes text DEFAULT '',
  saved_at timestamptz DEFAULT now()
);

-- 8. Insights
CREATE TABLE IF NOT EXISTS viral_insights (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  last_updated timestamptz DEFAULT now(),
  analysis_count integer DEFAULT 0,
  top_topics jsonb NOT NULL DEFAULT '[]',
  hook_performance jsonb NOT NULL DEFAULT '{}',
  thumbnail_patterns jsonb NOT NULL DEFAULT '[]',
  content_format_performance jsonb NOT NULL DEFAULT '{}',
  optimal_posting_times jsonb NOT NULL DEFAULT '{}',
  competitor_insights jsonb NOT NULL DEFAULT '[]'
);

-- 9. Competitor Reels
CREATE TABLE IF NOT EXISTS viral_competitor_reels (
  shortcode text PRIMARY KEY,
  url text NOT NULL,
  video_url text DEFAULT '',
  views integer DEFAULT 0,
  likes integer DEFAULT 0,
  comments integer DEFAULT 0,
  caption text DEFAULT '',
  timestamp timestamptz,
  profile text NOT NULL,
  created_at timestamptz DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_viral_topics_status ON viral_topics(status);
CREATE INDEX IF NOT EXISTS idx_viral_angles_format ON viral_angles(format);
CREATE INDEX IF NOT EXISTS idx_viral_angles_status ON viral_angles(status);
CREATE INDEX IF NOT EXISTS idx_viral_hooks_pattern ON viral_hooks(pattern);
CREATE INDEX IF NOT EXISTS idx_viral_hooks_status ON viral_hooks(status);
CREATE INDEX IF NOT EXISTS idx_viral_analytics_platform ON viral_analytics(platform);
CREATE INDEX IF NOT EXISTS idx_viral_analytics_winner ON viral_analytics(is_winner);
CREATE INDEX IF NOT EXISTS idx_viral_scripts_platform ON viral_scripts(platform);
CREATE INDEX IF NOT EXISTS idx_viral_competitor_reels_profile ON viral_competitor_reels(profile);

-- RLS
ALTER TABLE viral_agent_brain ENABLE ROW LEVEL SECURITY;
ALTER TABLE viral_topics ENABLE ROW LEVEL SECURITY;
ALTER TABLE viral_angles ENABLE ROW LEVEL SECURITY;
ALTER TABLE viral_hooks ENABLE ROW LEVEL SECURITY;
ALTER TABLE viral_scripts ENABLE ROW LEVEL SECURITY;
ALTER TABLE viral_analytics ENABLE ROW LEVEL SECURITY;
ALTER TABLE viral_swipe_hooks ENABLE ROW LEVEL SECURITY;
ALTER TABLE viral_insights ENABLE ROW LEVEL SECURITY;
ALTER TABLE viral_competitor_reels ENABLE ROW LEVEL SECURITY;
