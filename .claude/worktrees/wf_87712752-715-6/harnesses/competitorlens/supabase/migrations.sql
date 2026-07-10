-- CompetitorLens — Supabase Tables + RLS
-- Agent #14, DesignWise Squad
-- Run via Supabase SQL editor or supabase db push

-- ============================================================
-- TABLE: competitor_analyses
-- Stores full analysis records per competitor URL crawl
-- ============================================================
CREATE TABLE IF NOT EXISTS public.competitor_analyses (
    id                      UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    competitor_name         TEXT NOT NULL,                    -- "PropertyOnion" | "Foreclosure.com"
    source_url              TEXT NOT NULL,                    -- Original URL crawled
    component_type          TEXT NOT NULL DEFAULT 'unknown', -- "calendar" | "search" | "listing" | "map"
    layout_skeleton         JSONB,                           -- ComponentBlueprint JSON from DeepSeek
    ux_patterns             JSONB,                           -- UXPatternReport from Sonnet (Sprint 2)
    generated_component_path TEXT,                           -- Path to .jsx output (Sprint 2)
    brand_guard_status      TEXT NOT NULL DEFAULT 'PENDING', -- "PASS" | "BLOCK" | "PENDING"
    brand_guard_violations  JSONB,                           -- Array of violations if BLOCK
    diff_report_path        TEXT,                            -- Path to diff report (Sprint 3)
    crawl_metadata          JSONB,                           -- Screenshot URL, crawl timestamp, etc.
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT competitor_analyses_status_check
        CHECK (brand_guard_status IN ('PASS', 'BLOCK', 'PENDING')),
    CONSTRAINT competitor_analyses_type_check
        CHECK (component_type IN ('calendar', 'search', 'listing', 'map', 'hybrid', 'unknown'))
);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_competitor_analyses_updated_at
    BEFORE UPDATE ON public.competitor_analyses
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Indexes
CREATE INDEX IF NOT EXISTS idx_competitor_analyses_competitor
    ON public.competitor_analyses(competitor_name);

CREATE INDEX IF NOT EXISTS idx_competitor_analyses_status
    ON public.competitor_analyses(brand_guard_status);

CREATE INDEX IF NOT EXISTS idx_competitor_analyses_type
    ON public.competitor_analyses(component_type);

CREATE INDEX IF NOT EXISTS idx_competitor_analyses_created_at
    ON public.competitor_analyses(created_at DESC);

-- ============================================================
-- TABLE: ux_pattern_library
-- Reusable UX patterns extracted from competitor analyses
-- ============================================================
CREATE TABLE IF NOT EXISTS public.ux_pattern_library (
    id                      UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    pattern_name            TEXT NOT NULL UNIQUE,            -- "auction-calendar-grid"
    source_competitor       TEXT NOT NULL,                   -- Where we first saw it
    description             TEXT NOT NULL,                   -- Plain English description
    implementation_notes    TEXT,                            -- How to adapt for BidDeed.AI
    component_type          TEXT,                            -- Which component type this applies to
    visual_example          JSONB,                           -- Screenshot URLs or element descriptions
    reuse_count             INTEGER NOT NULL DEFAULT 0,      -- How many times we've adapted it
    tags                    TEXT[],                          -- ["calendar", "filter", "mobile-first"]
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER update_ux_pattern_library_updated_at
    BEFORE UPDATE ON public.ux_pattern_library
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE INDEX IF NOT EXISTS idx_ux_pattern_library_competitor
    ON public.ux_pattern_library(source_competitor);

CREATE INDEX IF NOT EXISTS idx_ux_pattern_library_reuse
    ON public.ux_pattern_library(reuse_count DESC);

-- ============================================================
-- ROW LEVEL SECURITY
-- Standard: authenticated users only
-- ============================================================

-- Enable RLS on both tables
ALTER TABLE public.competitor_analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ux_pattern_library ENABLE ROW LEVEL SECURITY;

-- competitor_analyses: authenticated users can read all, service role can write
CREATE POLICY "authenticated_read_competitor_analyses"
    ON public.competitor_analyses
    FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "service_role_write_competitor_analyses"
    ON public.competitor_analyses
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ux_pattern_library: authenticated users can read all, service role can write
CREATE POLICY "authenticated_read_ux_pattern_library"
    ON public.ux_pattern_library
    FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "service_role_write_ux_pattern_library"
    ON public.ux_pattern_library
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ============================================================
-- SEED: Initial UX patterns from known competitor analysis
-- ============================================================
INSERT INTO public.ux_pattern_library (pattern_name, source_competitor, description, implementation_notes, component_type, tags)
VALUES
    ('auction-calendar-grid',
     'PropertyOnion',
     'Monthly calendar grid showing auction dates with property counts per day cell. Click day to expand property list.',
     'Adapt with ML scores overlaid on each day cell. Color code: green=good deals, yellow=review, red=skip.',
     'calendar',
     ARRAY['calendar', 'grid', 'auction', 'date-picker']),

    ('county-filter-dropdown',
     'PropertyOnion',
     'Dropdown to select Florida county, updates calendar in real-time without page reload.',
     'Use Supabase realtime or simple fetch to filter multi_county_auctions by county field.',
     'filter',
     ARRAY['filter', 'dropdown', 'county', 'florida']),

    ('sale-type-color-coding',
     'PropertyOnion',
     'Color coding to distinguish sale types: foreclosure vs tax deed. Different badge colors per type.',
     'Extend with BID/REVIEW/SKIP color system on top of sale type colors.',
     'calendar',
     ARRAY['color-coding', 'badge', 'sale-type']),

    ('list-calendar-toggle',
     'PropertyOnion',
     'Toggle button to switch between calendar view and list view of same auction data.',
     'Add map view as third option using Mapbox integration.',
     'navigation',
     ARRAY['toggle', 'view-switch', 'calendar', 'list'])
ON CONFLICT (pattern_name) DO NOTHING;
