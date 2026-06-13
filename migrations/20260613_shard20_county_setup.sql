-- SHARD-20 County Setup Migration  
-- Counties: brevard (2/10), duval (2/10)
-- Execute: supabase db push (NO HITL per CLAUDE.md autonomous operations)

-- Ensure our target counties exist in fl_counties with proper configuration
INSERT INTO public.fl_counties (co_no, county_name, county_slug, active, ingested_at, total_parcels)
VALUES 
  (9, 'BREVARD', 'brevard', true, NOW(), 19706), -- Per brief: denominators FROZEN at snapshot
  (16, 'DUVAL', 'duval', true, NOW(), 20022)   -- Per brief: denominators FROZEN at snapshot  
ON CONFLICT (co_no) 
DO UPDATE SET 
  county_slug = EXCLUDED.county_slug,
  active = true,
  total_parcels = EXCLUDED.total_parcels,
  ingested_at = NOW();

-- Ensure multi_county_auctions has required columns for gold standard evaluation
ALTER TABLE public.multi_county_auctions 
ADD COLUMN IF NOT EXISTS parity_status TEXT DEFAULT 'pending',
ADD COLUMN IF NOT EXISTS tier1_sold_amount DECIMAL(12,2),
ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ DEFAULT NOW(),
ADD COLUMN IF NOT EXISTS parcel_id TEXT,
ADD COLUMN IF NOT EXISTS verified_outcome_source TEXT,
ADD COLUMN IF NOT EXISTS data_source TEXT DEFAULT 'unknown',
ADD COLUMN IF NOT EXISTS zone_code TEXT,
ADD COLUMN IF NOT EXISTS address TEXT,
ADD COLUMN IF NOT EXISTS geo_lat DECIMAL(10,8),
ADD COLUMN IF NOT EXISTS geo_lng DECIMAL(11,8),
ADD COLUMN IF NOT EXISTS property_value DECIMAL(12,2);

-- Update pipeline configurations for SHARD-20 counties per COUNTY EXCEPTIONS
-- Brevard: foreclosures NOT ONLINE, clerk_html platform
-- Duval: standard realauction platform
INSERT INTO public.pipeline_counties (county_slug, active, foreclosure_platform, foreclosure_url, tax_deed_platform, tax_deed_url, notes)
VALUES
  ('brevard', true, 'clerk_html', 'https://brevardclerk.us/court-services/foreclosure-sales/', 'realauction', 'https://brevard.realforeclose.com', 'EXCEPTION: foreclosures in-person Wednesdays at Government Center North Titusville'),
  ('duval', true, 'realauction', 'https://www.realauction.com/duval', 'realauction', 'https://www.realauction.com/duval', 'Standard realauction platform')
ON CONFLICT (county_slug)
DO UPDATE SET 
  active = true,
  foreclosure_platform = EXCLUDED.foreclosure_platform,
  foreclosure_url = EXCLUDED.foreclosure_url,
  notes = EXCLUDED.notes,
  updated_at = NOW();

-- Create acclaim harvest queue for Duval (extends existing acclaim pipeline)
CREATE TABLE IF NOT EXISTS public.duval_acclaim_harvest_queue (
    id BIGSERIAL PRIMARY KEY,
    case_number TEXT NOT NULL UNIQUE,
    doctype TEXT NOT NULL, -- CT (Certificate of Title) for verified outcomes
    status TEXT DEFAULT 'queued', -- queued|processing|completed|failed
    retries INTEGER DEFAULT 0,
    last_attempt_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_duval_acclaim_queue_status ON public.duval_acclaim_harvest_queue(status);
CREATE INDEX IF NOT EXISTS idx_duval_acclaim_queue_case_number ON public.duval_acclaim_harvest_queue(case_number);

-- Create staged records tables for acclaim pipeline
CREATE TABLE IF NOT EXISTS public.duval_clerk_grantor_recordings_staging (
    id BIGSERIAL PRIMARY KEY,
    case_number TEXT,
    raw_jsonb JSONB NOT NULL,
    doc_legal_description TEXT,
    comments TEXT,
    consideration DECIMAL(12,2), -- Maps to winning_bid
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.duval_tax_deed_recordings_staging (
    id BIGSERIAL PRIMARY KEY,
    case_number TEXT,
    raw_jsonb JSONB NOT NULL,
    doc_legal_description TEXT,
    comments TEXT,
    consideration DECIMAL(12,2), -- Maps to winning_bid
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create function to promote tier1 winning bids from outcomes (Letter F automation)
CREATE OR REPLACE FUNCTION public.promote_tier1_from_outcomes()
RETURNS TABLE(county_slug TEXT, promoted_count INTEGER) AS $$
BEGIN
    -- Promote from foreclosure_outcomes
    WITH promoted_fc AS (
        UPDATE public.multi_county_auctions 
        SET tier1_sold_amount = fo.winning_bid
        FROM public.foreclosure_outcomes fo
        WHERE public.multi_county_auctions.case_number = fo.case_number
          AND public.multi_county_auctions.county = fo.county_slug
          AND public.multi_county_auctions.tier1_sold_amount IS NULL
          AND fo.winning_bid IS NOT NULL
        RETURNING public.multi_county_auctions.county, fo.winning_bid
    ),
    -- Promote from tax_deed_outcomes  
    promoted_td AS (
        UPDATE public.multi_county_auctions
        SET tier1_sold_amount = tdo.winning_bid  
        FROM public.tax_deed_outcomes tdo
        WHERE public.multi_county_auctions.case_number = tdo.case_number
          AND public.multi_county_auctions.county = tdo.county_slug
          AND public.multi_county_auctions.tier1_sold_amount IS NULL
          AND tdo.winning_bid IS NOT NULL
        RETURNING public.multi_county_auctions.county, tdo.winning_bid
    ),
    -- Aggregate counts
    county_counts AS (
        SELECT county as county_slug, COUNT(*) as promoted_count FROM promoted_fc GROUP BY county
        UNION ALL
        SELECT county as county_slug, COUNT(*) as promoted_count FROM promoted_td GROUP BY county  
    )
    SELECT cc.county_slug, SUM(cc.promoted_count)::INTEGER as promoted_count
    FROM county_counts cc
    GROUP BY cc.county_slug;
END;
$$ LANGUAGE plpgsql;

-- Create function to feed duval acclaim queue (Letter B automation)
CREATE OR REPLACE FUNCTION public.feed_acclaim_queue_duval()
RETURNS INTEGER AS $$
DECLARE
    enqueued_count INTEGER := 0;
BEGIN
    -- Enqueue closed duval cases not yet in queue and not PropertyOnion-keyed
    WITH new_cases AS (
        SELECT mca.case_number, 'CT' as doctype
        FROM public.multi_county_auctions mca
        WHERE mca.county = 'duval'
          AND mca.sale_status IN ('sold', 'closed')
          AND mca.case_number NOT LIKE 'PO-%'  -- Exclude PropertyOnion IDs
          AND mca.case_number NOT IN (SELECT case_number FROM public.duval_acclaim_harvest_queue)
        LIMIT 1000 -- Batch limit to prevent overload
    )
    INSERT INTO public.duval_acclaim_harvest_queue (case_number, doctype)
    SELECT case_number, doctype FROM new_cases;
    
    GET DIAGNOSTICS enqueued_count = ROW_COUNT;
    
    RETURN enqueued_count;
END;
$$ LANGUAGE plpgsql;

-- Create function to map staged records to outcomes (CHAIN BREAK fix per brief)
CREATE OR REPLACE FUNCTION public.map_staged_to_outcomes_duval()
RETURNS INTEGER AS $$
DECLARE
    mapped_count INTEGER := 0;
BEGIN
    -- Map grantor recordings to foreclosure_outcomes
    WITH mapped_fc AS (
        INSERT INTO public.foreclosure_outcomes (case_number, county_slug, winning_bid, data_source)
        SELECT 
            -- Recover case_number from raw_jsonb or legal_description
            COALESCE(
                dgrs.case_number,
                regexp_replace(dgrs.doc_legal_description, '.*(FC\d{2}-\d+).*', '\1'),
                regexp_replace(dgrs.comments, '.*(FC\d{2}-\d+).*', '\1')
            ) as case_number,
            'duval' as county_slug,
            dgrs.consideration as winning_bid,
            'acclaim_ct:DUVAL-FC-V1' as data_source
        FROM public.duval_clerk_grantor_recordings_staging dgrs
        WHERE dgrs.consideration IS NOT NULL
          AND dgrs.consideration > 0
          AND COALESCE(dgrs.case_number, dgrs.doc_legal_description, dgrs.comments) ~ 'FC\d{2}-\d+'
        ON CONFLICT (case_number, county_slug, data_source) DO NOTHING
        RETURNING case_number
    ),
    -- Map tax deed recordings to tax_deed_outcomes
    mapped_td AS (
        INSERT INTO public.tax_deed_outcomes (case_number, county_slug, winning_bid, data_source)
        SELECT 
            -- Recover case_number from raw_jsonb or legal_description
            COALESCE(
                dtrs.case_number,
                regexp_replace(dtrs.doc_legal_description, '.*(TD\d{2}-\d+).*', '\1'),
                regexp_replace(dtrs.comments, '.*(TD\d{2}-\d+).*', '\1')
            ) as case_number,
            'duval' as county_slug,
            dtrs.consideration as winning_bid,
            'acclaim_ct:DUVAL-TD-V1' as data_source
        FROM public.duval_tax_deed_recordings_staging dtrs  
        WHERE dtrs.consideration IS NOT NULL
          AND dtrs.consideration > 0
          AND COALESCE(dtrs.case_number, dtrs.doc_legal_description, dtrs.comments) ~ 'TD\d{2}-\d+'
        ON CONFLICT (case_number, county_slug, data_source) DO NOTHING
        RETURNING case_number
    )
    SELECT (SELECT COUNT(*) FROM mapped_fc) + (SELECT COUNT(*) FROM mapped_td) INTO mapped_count;
    
    RETURN mapped_count;
END;
$$ LANGUAGE plpgsql;

-- Log this migration execution
INSERT INTO public.migration_log (filename, executed_at, shard, notes)
VALUES ('20260613_shard20_county_setup.sql', NOW(), 'SHARD-20', 'Database foundation for brevard + duval AUTOPILOT RUN 20')
ON CONFLICT DO NOTHING;

COMMENT ON TABLE public.duval_acclaim_harvest_queue IS 'Queue for harvesting Duval AcclaimWeb certificates - feeds Letter B pipeline';
COMMENT ON FUNCTION public.promote_tier1_from_outcomes IS 'Auto-promotes winning_bid to tier1_sold_amount - Letter F automation';
COMMENT ON FUNCTION public.feed_acclaim_queue_duval IS 'Auto-enqueues closed Duval cases for acclaim harvest - Letter B automation';
COMMENT ON FUNCTION public.map_staged_to_outcomes_duval IS 'Maps staged acclaim records to verified outcomes - CHAIN BREAK fix';