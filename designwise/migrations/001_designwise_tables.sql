-- DesignWise Squad — S1.4 Schema Migration
-- Version: 1.2.0 | Date: 2026-03-21
-- Run this in Supabase SQL Editor or psql
-- Ref: mocerqjnksmhcjzxrewo

-- ── 1. design_tasks ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.design_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_type TEXT NOT NULL,
    agent_id TEXT,
    input_spec JSONB,
    status TEXT NOT NULL DEFAULT 'pending',
    figma_url TEXT,
    output JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── 2. brand_violations ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.brand_violations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id TEXT NOT NULL,
    page_url TEXT NOT NULL,
    violation_type TEXT NOT NULL,
    expected TEXT,
    actual TEXT,
    severity TEXT NOT NULL DEFAULT 'warning',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── 3. visual_baselines ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.visual_baselines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    route TEXT NOT NULL,
    url TEXT NOT NULL,
    viewports JSONB,
    screenshot_desktop TEXT,
    screenshot_tablet TEXT,
    screenshot_mobile TEXT,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── 4. page_analytics ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.page_analytics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    route TEXT NOT NULL,
    date DATE NOT NULL,
    page_views INTEGER DEFAULT 0,
    unique_visitors INTEGER DEFAULT 0,
    bounce_rate FLOAT,
    avg_session_duration FLOAT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(route, date)
);

-- ── 5. conversion_funnel ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.conversion_funnel (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date DATE NOT NULL,
    step TEXT NOT NULL,
    count INTEGER DEFAULT 0,
    rate FLOAT DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(date, step)
);

-- ── 6. support_tickets ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.support_tickets (
    id TEXT PRIMARY KEY,
    message TEXT NOT NULL,
    category TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    confidence FLOAT,
    auto_response TEXT,
    github_issue_url TEXT,
    user_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── 7. ab_tests ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.ab_tests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'configuring',
    variants JSONB,
    traffic_split JSONB,
    confidence_threshold FLOAT DEFAULT 0.95,
    min_sample_size INTEGER DEFAULT 100,
    winner TEXT,
    promoted BOOLEAN DEFAULT FALSE,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── 8. deploy_log ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.deploy_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    commit_sha TEXT NOT NULL,
    branch TEXT NOT NULL,
    tier TEXT NOT NULL,
    status TEXT NOT NULL,
    checks JSONB,
    vercel_deploy_id TEXT,
    preview_url TEXT,
    deployed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── 9. competitor_snapshots ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.competitor_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    competitor TEXT NOT NULL,
    url TEXT NOT NULL,
    dom_hash TEXT,
    tech_stack JSONB,
    screenshot TEXT,
    scan_date DATE NOT NULL DEFAULT CURRENT_DATE,
    status INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(competitor, scan_date)
);

-- ── 10. seo_audits ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.seo_audits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    route TEXT NOT NULL,
    scan_date DATE NOT NULL DEFAULT CURRENT_DATE,
    score INTEGER,
    violations JSONB,
    checks JSONB,
    core_web_vitals JSONB,
    lighthouse_scores JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(route, scan_date)
);

-- ── 11. stitch_usage ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.stitch_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    mode TEXT NOT NULL,
    screen_name TEXT NOT NULL,
    count INTEGER DEFAULT 1,
    tokens_used INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(date, mode, screen_name)
);

-- ── RLS Policies ──────────────────────────────────────────────────────────────

-- Enable RLS on all tables
ALTER TABLE public.design_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.brand_violations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.visual_baselines ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.page_analytics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.conversion_funnel ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.support_tickets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ab_tests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.deploy_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.competitor_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.seo_audits ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.stitch_usage ENABLE ROW LEVEL SECURITY;

-- Service role: full access on all tables
CREATE POLICY IF NOT EXISTS "service_role_all" ON public.design_tasks FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY IF NOT EXISTS "service_role_all" ON public.brand_violations FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY IF NOT EXISTS "service_role_all" ON public.visual_baselines FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY IF NOT EXISTS "service_role_all" ON public.page_analytics FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY IF NOT EXISTS "service_role_all" ON public.conversion_funnel FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY IF NOT EXISTS "service_role_all" ON public.support_tickets FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY IF NOT EXISTS "service_role_all" ON public.ab_tests FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY IF NOT EXISTS "service_role_all" ON public.deploy_log FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY IF NOT EXISTS "service_role_all" ON public.competitor_snapshots FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY IF NOT EXISTS "service_role_all" ON public.seo_audits FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY IF NOT EXISTS "service_role_all" ON public.stitch_usage FOR ALL TO service_role USING (true) WITH CHECK (true);

-- page_analytics: read-only for authenticated
CREATE POLICY IF NOT EXISTS "authenticated_read" ON public.page_analytics FOR SELECT TO authenticated USING (true);
CREATE POLICY IF NOT EXISTS "authenticated_read" ON public.conversion_funnel FOR SELECT TO authenticated USING (true);

-- support_tickets: users can read/write their own
CREATE POLICY IF NOT EXISTS "user_own_tickets" ON public.support_tickets FOR ALL TO authenticated USING (user_id = auth.uid()::text) WITH CHECK (user_id = auth.uid()::text);
