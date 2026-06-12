-- ============================================================
-- SHARD 17 COUNTY SETUP: charlotte, citrus, broward
-- Migration: 20260612_shard17_county_setup.sql
-- Configures Gold Standard pipeline for assigned counties
-- ============================================================

-- Ensure county slugs are set for shard 17 counties
INSERT INTO fl_counties (co_no, name, fips_code, slug, region) VALUES 
  (9,  'Charlotte', '12015', 'charlotte', 'southwest'),
  (17, 'Citrus',    '12017', 'citrus',    'central'), 
  (11, 'Broward',   '12011', 'broward',   'southeast')
ON CONFLICT (co_no) DO UPDATE SET 
  slug = EXCLUDED.slug 
WHERE fl_counties.slug IS NULL;

-- Configure pipeline.counties for shard 17 (if table exists)
DO $$ 
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'counties' AND table_schema = 'pipeline') THEN
        -- Charlotte County configuration
        INSERT INTO pipeline.counties (
            county_slug, state, co_no, active, priority,
            foreclosure_platform, foreclosure_url,
            tax_deed_platform, tax_deed_url,
            property_appraiser_url, clerk_url,
            notes, configured_at
        ) VALUES (
            'charlotte', 'FL', 9, true, 'normal',
            'realauction', 'https://www.realforeclose.com/index.cfm?zaction=AUCTION&zmethod=PREVIEW&AUCTIONDATE=2024-01-01&CountyID=9',
            'realauction', 'https://www.realauction.com/index.cfm?zaction=AUCTION&zmethod=PREVIEW&AUCTIONDATE=2024-01-01&CountyID=9',
            'https://www.ccappraiser.com', 'https://www.charlotteclerk.com',
            'Shard 17 - Standard RealAuction platforms', now()
        ) ON CONFLICT (county_slug) DO UPDATE SET
            active = true,
            foreclosure_platform = EXCLUDED.foreclosure_platform,
            foreclosure_url = EXCLUDED.foreclosure_url,
            tax_deed_platform = EXCLUDED.tax_deed_platform,
            tax_deed_url = EXCLUDED.tax_deed_url,
            property_appraiser_url = EXCLUDED.property_appraiser_url,
            clerk_url = EXCLUDED.clerk_url,
            notes = EXCLUDED.notes,
            configured_at = now();

        -- Citrus County configuration
        INSERT INTO pipeline.counties (
            county_slug, state, co_no, active, priority,
            foreclosure_platform, foreclosure_url,
            tax_deed_platform, tax_deed_url,
            property_appraiser_url, clerk_url,
            notes, configured_at
        ) VALUES (
            'citrus', 'FL', 17, true, 'normal',
            'realauction', 'https://www.realforeclose.com/index.cfm?zaction=AUCTION&zmethod=PREVIEW&AUCTIONDATE=2024-01-01&CountyID=17',
            'realauction', 'https://www.realauction.com/index.cfm?zaction=AUCTION&zmethod=PREVIEW&AUCTIONDATE=2024-01-01&CountyID=17',
            'https://www.citruspa.org', 'https://www.citrusclerk.org',
            'Shard 17 - Standard RealAuction platforms', now()
        ) ON CONFLICT (county_slug) DO UPDATE SET
            active = true,
            foreclosure_platform = EXCLUDED.foreclosure_platform,
            foreclosure_url = EXCLUDED.foreclosure_url,
            tax_deed_platform = EXCLUDED.tax_deed_platform,
            tax_deed_url = EXCLUDED.tax_deed_url,
            property_appraiser_url = EXCLUDED.property_appraiser_url,
            clerk_url = EXCLUDED.clerk_url,
            notes = EXCLUDED.notes,
            configured_at = now();

        -- Broward County configuration (major county)
        INSERT INTO pipeline.counties (
            county_slug, state, co_no, active, priority,
            foreclosure_platform, foreclosure_url,
            tax_deed_platform, tax_deed_url,
            property_appraiser_url, clerk_url,
            notes, configured_at
        ) VALUES (
            'broward', 'FL', 11, true, 'high',
            'realauction', 'https://www.realforeclose.com/index.cfm?zaction=AUCTION&zmethod=PREVIEW&AUCTIONDATE=2024-01-01&CountyID=11',
            'realauction', 'https://www.realauction.com/index.cfm?zaction=AUCTION&zmethod=PREVIEW&AUCTIONDATE=2024-01-01&CountyID=11',
            'https://www.bcpa.net', 'https://browardclerk.org',
            'Shard 17 - Major county, high priority for Gold Standard', now()
        ) ON CONFLICT (county_slug) DO UPDATE SET
            active = true,
            priority = 'high',
            foreclosure_platform = EXCLUDED.foreclosure_platform,
            foreclosure_url = EXCLUDED.foreclosure_url,
            tax_deed_platform = EXCLUDED.tax_deed_platform,
            tax_deed_url = EXCLUDED.tax_deed_url,
            property_appraiser_url = EXCLUDED.property_appraiser_url,
            clerk_url = EXCLUDED.clerk_url,
            notes = EXCLUDED.notes,
            configured_at = now();

        RAISE NOTICE 'Pipeline counties configured for shard 17';
    ELSE
        RAISE NOTICE 'pipeline.counties table not found, skipping pipeline configuration';
    END IF;
END $$;

-- Create shard 17 specific verified outcomes tracking
-- (Uses existing tax_deed_outcomes and foreclosure_outcomes tables)

-- Initialize Gold Standard tracking for shard 17 counties
-- Ensure they appear in gold_standard_county_status on next loop run
DO $$
DECLARE
    county_rec record;
BEGIN
    FOR county_rec IN SELECT 'charlotte'::text as slug UNION SELECT 'citrus' UNION SELECT 'broward'
    LOOP
        -- Insert placeholder status if not exists (will be overwritten by next loop run)
        INSERT INTO gold_standard_county_status (
            loop_run_id, county_slug, 
            a_dual_product, a_dual_product_detail, a_dual_product_pass,
            b_verified_outcomes, b_verified_outcomes_detail, b_verified_outcomes_pass,
            c_parity_clean, c_parity_clean_detail, c_parity_clean_pass,
            d_parity_any, d_parity_any_detail, d_parity_any_pass,
            e_parcel_linkage, e_parcel_linkage_detail, e_parcel_linkage_pass,
            f_tier1_sold, f_tier1_sold_detail, f_tier1_sold_pass,
            g_zoning, g_zoning_detail, g_zoning_pass,
            h_freshness, h_freshness_detail, h_freshness_pass,
            i_property_card, i_property_card_detail, i_property_card_pass,
            j_deal_thesis, j_deal_thesis_detail, j_deal_thesis_pass,
            total_score, letters_pass, gold_standard, critical_three_pass,
            created_at
        ) 
        SELECT 
            COALESCE((SELECT max(loop_run_id) FROM gold_standard_county_status), 0),
            county_rec.slug,
            null, 'Shard 17 initialization', false,
            null, 'Shard 17 initialization', false,
            null, 'Shard 17 initialization', false,
            null, 'Shard 17 initialization', false,
            null, 'Shard 17 initialization', false,
            null, 'Shard 17 initialization', false,
            null, 'Shard 17 initialization', false,
            null, 'Shard 17 initialization', false,
            null, 'Shard 17 initialization', false,
            null, 'Shard 17 initialization', false,
            0, '{}', false, false,
            now()
        WHERE NOT EXISTS (
            SELECT 1 FROM gold_standard_county_status 
            WHERE county_slug = county_rec.slug
        );
    END LOOP;
    
    RAISE NOTICE 'Gold Standard status initialized for shard 17 counties';
END $$;

-- Create parcel linkage helper function for shard 17
CREATE OR REPLACE FUNCTION link_parcels_shard17(county_slug_arg text, batch_limit integer DEFAULT 1000)
RETURNS TABLE (
    linked_count integer,
    total_unlinked integer,
    success_rate numeric
) LANGUAGE plpgsql AS $$
DECLARE
    linked_cnt integer := 0;
    total_cnt integer := 0;
BEGIN
    -- Count total unlinked auctions for county
    SELECT COUNT(*) INTO total_cnt 
    FROM multi_county_auctions 
    WHERE county = county_slug_arg AND parcel_id IS NULL;
    
    -- For now, return counts for tracking (actual linking requires GIS integration)
    -- This will be extended with property appraiser API calls
    
    RETURN QUERY SELECT 
        linked_cnt::integer,
        total_cnt::integer,
        CASE WHEN total_cnt > 0 THEN (linked_cnt::numeric / total_cnt * 100) ELSE 0 END;
END $$;

-- Create parity improvement helper for shard 17
CREATE OR REPLACE FUNCTION improve_parity_shard17(county_slug_arg text)
RETURNS TABLE (
    total_auctions integer,
    clean_matches integer,
    any_matches integer,
    clean_pct numeric,
    any_pct numeric
) LANGUAGE plpgsql AS $$
DECLARE
    total_cnt integer := 0;
    clean_cnt integer := 0;
    any_cnt integer := 0;
BEGIN
    -- Get current parity statistics
    SELECT 
        COUNT(*),
        COUNT(CASE WHEN parity_status = 'matched_clean' THEN 1 END),
        COUNT(CASE WHEN parity_status IN ('matched_clean', 'matched_divergent') THEN 1 END)
    INTO total_cnt, clean_cnt, any_cnt
    FROM multi_county_auctions 
    WHERE county = county_slug_arg AND source_platform IS NOT NULL;
    
    RETURN QUERY SELECT 
        total_cnt,
        clean_cnt,
        any_cnt,
        CASE WHEN total_cnt > 0 THEN (clean_cnt::numeric / total_cnt * 100) ELSE 0 END,
        CASE WHEN total_cnt > 0 THEN (any_cnt::numeric / total_cnt * 100) ELSE 0 END;
END $$;

-- Log migration completion
INSERT INTO audit_log (event_type, description, metadata, created_at) VALUES (
    'migration',
    'Shard 17 county setup completed',
    jsonb_build_object(
        'counties', array['charlotte', 'citrus', 'broward'],
        'migration', '20260612_shard17_county_setup.sql',
        'shard', 17
    ),
    now()
);

-- Grant permissions on helper functions
GRANT EXECUTE ON FUNCTION link_parcels_shard17(text, integer) TO PUBLIC;
GRANT EXECUTE ON FUNCTION improve_parity_shard17(text) TO PUBLIC;

RAISE NOTICE 'Shard 17 county setup completed successfully';