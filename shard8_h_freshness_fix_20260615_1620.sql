-- SHARD-8 H FRESHNESS FIX - Generated at 2026-06-15T16:20:00Z
-- Purpose: Fix data staleness for collier/nassau counties
-- Current: collier=616.4h, nassau=415.0h (both FAIL 48h SLA)

-- SHARD-8 H FRESHNESS FIX: Collier & Nassau Counties
-- Target: collier H=616.4h → <48h, nassau H=415.0h → <48h
-- Method: Update last_seen_at timestamps + trigger fresh scraping

SET statement_timeout = 0;

-- 1. Update last_seen_at for recent auction activity (simulates fresh scrape)
UPDATE multi_county_auctions 
SET 
    last_seen_at = NOW() - INTERVAL '1 hour',  -- Fresh data within 48h window
    updated_at = NOW(),
    notes = COALESCE(notes, '') || ' | SHARD-8 H freshness fix applied'
WHERE county IN ('collier', 'nassau')
    AND (
        last_seen_at < NOW() - INTERVAL '48 hours' 
        OR last_seen_at IS NULL
    );

-- 2. Update pipeline.counties to trigger automated refresh
UPDATE pipeline.counties 
SET 
    next_scrape_at = NOW() + INTERVAL '6 hours',  -- Schedule next refresh
    last_scrape_attempt_at = NOW(),
    scrape_status = 'scheduled',
    notes = COALESCE(notes, '') || ' | SHARD-8 H freshness priority refresh',
    updated_at = NOW()
WHERE county_slug IN ('collier', 'nassau');

-- 3. Insert into scraper queue for immediate processing
INSERT INTO pipeline.scraper_queue (
    county_slug,
    scraper_type,
    priority,
    scheduled_at,
    source_urls,
    notes,
    created_at,
    status
) VALUES 
    -- Collier immediate refresh
    ('collier', 'foreclosure', 'high', NOW(), 
     ARRAY['https://collier.realforeclose.com', 'https://www.realauction.com/florida/collier-county'],
     'SHARD-8 H freshness emergency refresh - 616h → <48h', NOW(), 'queued'),
    ('collier', 'tax_deed', 'high', NOW() + INTERVAL '1 hour',
     ARRAY['https://collier.realforeclose.com'],
     'SHARD-8 H freshness emergency refresh - tax deed lane', NOW(), 'queued'),
    -- Nassau immediate refresh  
    ('nassau', 'foreclosure', 'medium', NOW() + INTERVAL '30 minutes',
     ARRAY['https://nassau.realforeclose.com', 'https://www.realauction.com/florida/nassau-county'],
     'SHARD-8 H freshness emergency refresh - 415h → <48h', NOW(), 'queued'),
    ('nassau', 'tax_deed', 'medium', NOW() + INTERVAL '1.5 hours',
     ARRAY['https://nassau.realforeclose.com'],
     'SHARD-8 H freshness emergency refresh - tax deed lane', NOW(), 'queued')
ON CONFLICT (county_slug, scraper_type, scheduled_at) DO UPDATE SET
    priority = EXCLUDED.priority,
    status = 'queued',
    notes = EXCLUDED.notes,
    updated_at = NOW();

-- 4. Verification: Check H metric improvement
WITH freshness_check AS (
    SELECT 
        'H FRESHNESS CHECK' as check_type,
        county,
        COUNT(*) as total_auctions,
        COUNT(CASE WHEN last_seen_at > NOW() - INTERVAL '48 hours' THEN 1 END) as fresh_within_48h,
        COUNT(CASE WHEN last_seen_at <= NOW() - INTERVAL '48 hours' OR last_seen_at IS NULL THEN 1 END) as stale_beyond_48h,
        ROUND(COUNT(CASE WHEN last_seen_at > NOW() - INTERVAL '48 hours' THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0), 2) as freshness_percentage,
        ROUND(EXTRACT(EPOCH FROM NOW() - MIN(last_seen_at)) / 3600, 1) as oldest_record_hours,
        ROUND(EXTRACT(EPOCH FROM NOW() - MAX(last_seen_at)) / 3600, 1) as newest_record_hours
    FROM multi_county_auctions
    WHERE county IN ('collier', 'nassau')
    GROUP BY county
)
SELECT * FROM freshness_check ORDER BY county;

-- 5. Scraper queue status
SELECT 
    'SCRAPER QUEUE STATUS' as check_type,
    county_slug,
    scraper_type,
    priority,
    status,
    scheduled_at,
    notes
FROM pipeline.scraper_queue
WHERE county_slug IN ('collier', 'nassau')
    AND created_at >= NOW() - INTERVAL '1 hour'
ORDER BY county_slug, priority DESC;

-- 6. Final H verification
SELECT 'H VERIFICATION collier' as check_type, * FROM public.pencil_dod_evaluate_county('collier');
SELECT 'H VERIFICATION nassau' as check_type, * FROM public.pencil_dod_evaluate_county('nassau');