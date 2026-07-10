-- DesignWise Stitch 2.0 Spec Patch — Amendment 1 & 6
-- Date: 2026-03-21
-- Applies to: DESIGNWISE-SPEC.md V1.1.0

-- Amendment 1: stitch_usage quota tracking table
CREATE TABLE IF NOT EXISTS stitch_usage (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  date DATE NOT NULL,
  mode TEXT NOT NULL CHECK (mode IN ('flash', 'pro')),
  screen_name TEXT,
  generation_count INT DEFAULT 1,
  remaining INT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(date, mode, screen_name)
);

-- RLS: service_role only
ALTER TABLE stitch_usage ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_full" ON stitch_usage
  USING (auth.role() = 'service_role');

-- Amendment 6: Figma archive column on design_tasks
ALTER TABLE design_tasks ADD COLUMN IF NOT EXISTS figma_url TEXT;

-- Comments
COMMENT ON TABLE stitch_usage IS 'Tracks Stitch 2.0 generation quota (350/month free tier). Flash=iteration, Pro=production.';
COMMENT ON COLUMN design_tasks.figma_url IS 'Optional Figma export URL after production screen approval (P2 Sprint 4).';
