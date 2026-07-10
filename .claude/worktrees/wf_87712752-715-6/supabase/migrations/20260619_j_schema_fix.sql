-- 20260619_j_schema_fix.sql
-- Fix bid_decisions table: add county_slug, triangle_score, repair_estimate, arv_source, pipeline_version
-- Required for J evaluator to function correctly
-- Root cause: CREATE TABLE IF NOT EXISTS was a no-op (table pre-existed with fewer columns)
-- Applied: 2026-06-19 via Management API

SET statement_timeout = 0;

ALTER TABLE public.bid_decisions
ADD COLUMN IF NOT EXISTS county_slug TEXT,
ADD COLUMN IF NOT EXISTS triangle_score NUMERIC(5,4),
ADD COLUMN IF NOT EXISTS repair_estimate NUMERIC(12,2),
ADD COLUMN IF NOT EXISTS arv_source TEXT,
ADD COLUMN IF NOT EXISTS pipeline_version TEXT;

CREATE INDEX IF NOT EXISTS idx_bid_decisions_county ON public.bid_decisions(county_slug);

CREATE INDEX IF NOT EXISTS idx_bid_decisions_complete
    ON public.bid_decisions(county_slug)
    WHERE arv IS NOT NULL AND max_bid IS NOT NULL AND ml_score IS NOT NULL;

-- Back-fill county_slug from MCA for existing rows
UPDATE public.bid_decisions bd
SET county_slug = mca.county
FROM public.multi_county_auctions mca
WHERE mca.case_number = bd.case_number
AND bd.county_slug IS NULL;
