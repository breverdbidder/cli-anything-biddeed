-- Gold Standard Tier1 Promotion Function
-- Promotes winning_bid amounts from foreclosure_outcomes to multi_county_auctions 
-- for F metric calculation (tier1 sold amount verification)

CREATE OR REPLACE FUNCTION public.promote_tier1_from_outcomes()
RETURNS TABLE(updated_count bigint, county_breakdown jsonb) 
LANGUAGE plpgsql
AS $$
DECLARE
    v_updated bigint := 0;
    v_county_stats jsonb := '{}';
    v_county text;
    v_county_count bigint;
BEGIN
    -- Update multi_county_auctions with winning_bid from foreclosure_outcomes
    -- Only update records that don't already have tier1_sold_amount
    WITH updated_rows AS (
        UPDATE multi_county_auctions mca
        SET 
            tier1_sold_amount = fo.winning_bid,
            tier1_data_source = fo.data_source,
            tier1_verified_at = now()
        FROM foreclosure_outcomes fo
        WHERE mca.case_number = fo.case_number 
        AND mca.county = fo.county
        AND fo.winning_bid IS NOT NULL
        AND fo.winning_bid > 0
        -- Only independent sources (exclude PropertyOnion-derived)
        AND NOT fo.data_source LIKE '%propertyonion%'
        AND NOT fo.data_source LIKE 'PO-%'
        AND NOT fo.data_source LIKE '%flynn%' -- questionable provenance per issue
        -- Only update if not already populated or if new source is better
        AND (mca.tier1_sold_amount IS NULL 
             OR mca.tier1_data_source IS NULL 
             OR fo.data_source LIKE 'acclaim_ct:%')
        RETURNING mca.county, mca.case_number
    ),
    county_counts AS (
        SELECT county, count(*) as cnt
        FROM updated_rows
        GROUP BY county
    )
    SELECT count(*), jsonb_object_agg(county, cnt)
    INTO v_updated, v_county_stats
    FROM county_counts;

    RETURN QUERY SELECT v_updated, COALESCE(v_county_stats, '{}');
END;
$$;

-- Create the feed_acclaim_queue function for auto-enqueueing closed cases
CREATE OR REPLACE FUNCTION public.feed_acclaim_queue_brevard()
RETURNS TABLE(enqueued_count bigint, month_range text)
LANGUAGE plpgsql  
AS $$
DECLARE
    v_enqueued bigint := 0;
    v_start_date date;
    v_end_date date;
BEGIN
    -- Get date range for last 6 months
    v_end_date := current_date;
    v_start_date := v_end_date - interval '6 months';
    
    -- Find closed Brevard foreclosure cases that aren't in the acclaim queue yet
    WITH new_queue_items AS (
        INSERT INTO brevard_fc_acclaim_queue (case_number, county, source_platform, queued_at, status)
        SELECT DISTINCT 
            mca.case_number,
            mca.county,
            mca.source_platform,
            now(),
            'pending'
        FROM multi_county_auctions mca
        WHERE mca.county = 'brevard'
        AND mca.sale_type = 'foreclosure'
        AND mca.status IN ('sold', 'closed')
        AND mca.case_number IS NOT NULL
        AND NOT mca.case_number LIKE 'PO-%'  -- Exclude PropertyOnion IDs
        AND mca.case_number ~ '^[0-9]{2}-[0-9]{4}-(CA|CC|FC)'  -- Match court format
        AND mca.auction_date >= v_start_date
        -- Not already processed
        AND NOT EXISTS (
            SELECT 1 FROM foreclosure_outcomes fo 
            WHERE fo.case_number = mca.case_number 
            AND fo.county = 'brevard'
            AND fo.data_source LIKE 'acclaim_ct:%'
        )
        -- Not already queued
        AND NOT EXISTS (
            SELECT 1 FROM brevard_fc_acclaim_queue q 
            WHERE q.case_number = mca.case_number
        )
        RETURNING 1
    )
    SELECT count(*) INTO v_enqueued FROM new_queue_items;
    
    RETURN QUERY SELECT 
        v_enqueued,
        format('%s to %s', v_start_date, v_end_date);
END;
$$;

-- Create the queue table if it doesn't exist
CREATE TABLE IF NOT EXISTS brevard_fc_acclaim_queue (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    case_number text NOT NULL,
    county text NOT NULL DEFAULT 'brevard',
    source_platform text,
    queued_at timestamptz DEFAULT now(),
    processed_at timestamptz,
    status text DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    error_message text,
    retry_count int DEFAULT 0,
    UNIQUE(case_number, county)
);

CREATE INDEX IF NOT EXISTS idx_brevard_acclaim_queue_status 
ON brevard_fc_acclaim_queue(status, queued_at);

CREATE INDEX IF NOT EXISTS idx_brevard_acclaim_queue_case 
ON brevard_fc_acclaim_queue(case_number);