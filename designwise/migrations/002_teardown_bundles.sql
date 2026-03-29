-- Migration: TeardownWise — teardown_bundles table
-- Date: 2026-03-29
-- Issue: breverdbidder/cli-anything-biddeed#10
-- Spec: DESIGNWISE-V3-UPGRADES.md UPGRADE 1

CREATE TABLE IF NOT EXISTS public.teardown_bundles (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    url           TEXT        NOT NULL,
    html_hash     TEXT,
    techniques    JSONB,      -- layout_technique, animation_library, color_system, typography
    components    JSONB,      -- effects[], component_patterns[]
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_teardown_url ON teardown_bundles(url);
CREATE INDEX IF NOT EXISTS idx_teardown_created ON teardown_bundles(created_at DESC);

COMMENT ON TABLE teardown_bundles IS 'TeardownWise — structured technique analysis per URL';
COMMENT ON COLUMN teardown_bundles.techniques IS 'layout_technique, animation_library, color_system, typography';
COMMENT ON COLUMN teardown_bundles.components IS 'effects[], component_patterns[]';
