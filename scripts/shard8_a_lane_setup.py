#!/usr/bin/env python3
"""
SHARD-8 A-Lane Configuration for DeSoto & Monroe Counties
Configure foreclosure and tax deed lanes for dual-product coverage

Root Cause: desoto and monroe have 0 auctions (all metrics null)
Need to configure pipeline.counties for both counties

Based on FL county research:
- DeSoto: Rural agricultural county, smaller court system  
- Monroe: Florida Keys, unique jurisdiction challenges

Usage:
  python scripts/shard8_a_lane_setup.py
"""

import os
import sys
import json
from datetime import datetime, timezone
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_KEY:
    print("⚠️ No SUPABASE_KEY found - will generate SQL only")
    SUPABASE_KEY = "dummy"

def log(message, level="INFO"):
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"[{timestamp}] {level}: {message}")
    if level == "ERROR":
        logger.error(message)
    else:
        logger.info(message)

# County lane configurations based on FL county research
COUNTY_LANE_CONFIGS = {
    'desoto': {
        'county_name': 'DeSoto County',
        'state': 'FL',
        'co_no': 22,  # DeSoto County number per FL system
        'foreclosure_platform': 'realauction',  # Start with standard platform
        'foreclosure_url': 'https://desoto.realforeclose.com',  
        'tax_deed_platform': 'realauction',
        'tax_deed_url': 'https://desoto.realforeclose.com',
        'appraiser_url': 'https://www.desotocountyfl.gov/departments/property-appraiser',
        'clerk_url': 'https://www.desotoclerk.com',
        'foreclosure_frequency': 'weekly',  # Rural counties often weekly
        'tax_deed_frequency': 'monthly',
        'timezone': 'America/New_York',
        'status': 'needs_configuration',
        'notes': 'Rural agricultural county - smaller volume expected',
        'priority': 'medium'
    },
    'monroe': {
        'county_name': 'Monroe County', 
        'state': 'FL',
        'co_no': 52,  # Monroe County number per FL system
        'foreclosure_platform': 'realauction',
        'foreclosure_url': 'https://monroe.realforeclose.com',
        'tax_deed_platform': 'realauction', 
        'tax_deed_url': 'https://monroe.realforeclose.com',
        'appraiser_url': 'https://www.monroecounty-fl.gov/departments/property_appraiser',
        'clerk_url': 'https://www.clerk-of-the-court.com',
        'foreclosure_frequency': 'weekly',
        'tax_deed_frequency': 'monthly', 
        'timezone': 'America/New_York',
        'status': 'needs_configuration',
        'notes': 'Florida Keys - high property values, unique market conditions',
        'priority': 'high'  # Keys market has high values
    }
}

def generate_pipeline_counties_sql():
    """Generate SQL to insert/update pipeline.counties configuration"""
    log("📝 Generating pipeline.counties SQL for desoto and monroe")
    
    sql_script = """
-- SHARD-8 A-LANE SETUP: Configure desoto and monroe counties
-- Target: Enable A-lane (dual-product coverage) for both counties
-- Current: desoto A=null, monroe A=null (0 auctions)

SET statement_timeout = 0;

-- Insert or update DeSoto County configuration
INSERT INTO pipeline.counties (
    county_slug,
    county_name,
    state,
    co_no,
    foreclosure_platform,
    foreclosure_url,
    tax_deed_platform,
    tax_deed_url,
    appraiser_url,
    clerk_url,
    foreclosure_frequency,
    tax_deed_frequency,
    timezone,
    status,
    notes,
    priority,
    created_at,
    updated_at
) VALUES (
    'desoto',
    'DeSoto County',
    'FL',
    22,
    'realauction',
    'https://desoto.realforeclose.com',
    'realauction', 
    'https://desoto.realforeclose.com',
    'https://www.desotocountyfl.gov/departments/property-appraiser',
    'https://www.desotoclerk.com',
    'weekly',
    'monthly',
    'America/New_York',
    'configured',
    'SHARD-8: Rural agricultural county, configured for dual-product coverage',
    'medium',
    NOW(),
    NOW()
)
ON CONFLICT (county_slug) DO UPDATE SET
    county_name = EXCLUDED.county_name,
    co_no = EXCLUDED.co_no,
    foreclosure_platform = EXCLUDED.foreclosure_platform,
    foreclosure_url = EXCLUDED.foreclosure_url,
    tax_deed_platform = EXCLUDED.tax_deed_platform,
    tax_deed_url = EXCLUDED.tax_deed_url,
    appraiser_url = EXCLUDED.appraiser_url,
    clerk_url = EXCLUDED.clerk_url,
    foreclosure_frequency = EXCLUDED.foreclosure_frequency,
    tax_deed_frequency = EXCLUDED.tax_deed_frequency,
    status = 'configured',
    notes = EXCLUDED.notes,
    priority = EXCLUDED.priority,
    updated_at = NOW();

-- Insert or update Monroe County configuration  
INSERT INTO pipeline.counties (
    county_slug,
    county_name,
    state,
    co_no,
    foreclosure_platform,
    foreclosure_url,
    tax_deed_platform,
    tax_deed_url,
    appraiser_url,
    clerk_url,
    foreclosure_frequency,
    tax_deed_frequency,
    timezone,
    status,
    notes,
    priority,
    created_at,
    updated_at
) VALUES (
    'monroe',
    'Monroe County',
    'FL',
    52,
    'realauction',
    'https://monroe.realforeclose.com',
    'realauction',
    'https://monroe.realforeclose.com', 
    'https://www.monroecounty-fl.gov/departments/property_appraiser',
    'https://www.clerk-of-the-court.com',
    'weekly',
    'monthly',
    'America/New_York',
    'configured',
    'SHARD-8: Florida Keys high-value market, configured for dual-product coverage',
    'high',
    NOW(),
    NOW()
)
ON CONFLICT (county_slug) DO UPDATE SET
    county_name = EXCLUDED.county_name,
    co_no = EXCLUDED.co_no,
    foreclosure_platform = EXCLUDED.foreclosure_platform,
    foreclosure_url = EXCLUDED.foreclosure_url,
    tax_deed_platform = EXCLUDED.tax_deed_platform,
    tax_deed_url = EXCLUDED.tax_deed_url,
    appraiser_url = EXCLUDED.appraiser_url,
    clerk_url = EXCLUDED.clerk_url,
    foreclosure_frequency = EXCLUDED.foreclosure_frequency,
    tax_deed_frequency = EXCLUDED.tax_deed_frequency,
    status = 'configured',
    notes = EXCLUDED.notes,
    priority = EXCLUDED.priority,
    updated_at = NOW();

-- Verify the configurations
SELECT 
    'SHARD-8 A-LANE VERIFICATION' as check_type,
    county_slug,
    county_name,
    foreclosure_platform,
    tax_deed_platform,
    status,
    priority,
    updated_at
FROM pipeline.counties
WHERE county_slug IN ('desoto', 'monroe')
ORDER BY county_slug;
"""
    
    return sql_script

def generate_scraper_schedule_sql():
    """Generate SQL to add counties to scraper schedule"""
    sql_script = """
-- SHARD-8 SCRAPER SCHEDULE: Add desoto and monroe to automated scraping
-- This enables the 05:30Z dispatch cycle to include these counties

-- Add to scraper dispatch schedule (if not already present)
INSERT INTO pipeline.scraper_schedule (
    county_slug,
    scraper_type,
    frequency,
    next_run,
    enabled,
    created_at,
    updated_at
) VALUES 
    -- DeSoto foreclosure schedule
    ('desoto', 'foreclosure', 'weekly', NOW() + INTERVAL '1 day', true, NOW(), NOW()),
    -- DeSoto tax deed schedule  
    ('desoto', 'tax_deed', 'monthly', NOW() + INTERVAL '2 days', true, NOW(), NOW()),
    -- Monroe foreclosure schedule
    ('monroe', 'foreclosure', 'weekly', NOW() + INTERVAL '1 day', true, NOW(), NOW()),
    -- Monroe tax deed schedule
    ('monroe', 'tax_deed', 'monthly', NOW() + INTERVAL '2 days', true, NOW(), NOW())
ON CONFLICT (county_slug, scraper_type) DO UPDATE SET
    frequency = EXCLUDED.frequency,
    enabled = true,
    updated_at = NOW();

-- Verify scheduling
SELECT 
    'SCRAPER SCHEDULE' as check_type,
    county_slug,
    scraper_type,
    frequency,
    enabled,
    next_run
FROM pipeline.scraper_schedule
WHERE county_slug IN ('desoto', 'monroe')
ORDER BY county_slug, scraper_type;
"""
    
    return sql_script

def create_sql_files():
    """Create the SQL execution files"""
    
    # Main configuration SQL
    config_sql = generate_pipeline_counties_sql()
    config_file = f"shard8_a_lane_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
    
    with open(config_file, 'w') as f:
        f.write(f"-- SHARD-8 A-LANE CONFIGURATION - Generated at {datetime.now().isoformat()}\n")
        f.write(f"-- Purpose: Configure pipeline.counties for desoto and monroe\n")
        f.write(f"-- Target: Enable dual-product coverage (A-lane)\n\n")
        f.write(config_sql)
    
    log(f"✅ Configuration SQL written to: {config_file}")
    
    # Scraper schedule SQL
    schedule_sql = generate_scraper_schedule_sql()
    schedule_file = f"shard8_scraper_schedule_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
    
    with open(schedule_file, 'w') as f:
        f.write(f"-- SHARD-8 SCRAPER SCHEDULE - Generated at {datetime.now().isoformat()}\n")
        f.write(f"-- Purpose: Add desoto/monroe to automated scraping\n\n")
        f.write(schedule_sql)
    
    log(f"✅ Schedule SQL written to: {schedule_file}")
    
    return config_file, schedule_file

def generate_verification_sql():
    """Generate comprehensive verification queries"""
    verification_sql = """
-- SHARD-8 A-LANE VERIFICATION: Check configuration and initial scraping
-- Run this AFTER executing the configuration and schedule SQL

-- 1. Verify pipeline.counties configuration
SELECT 
    'PIPELINE CONFIG' as check_type,
    county_slug,
    county_name,
    foreclosure_platform,
    foreclosure_url,
    tax_deed_platform,
    tax_deed_url,
    status,
    priority,
    updated_at
FROM pipeline.counties
WHERE county_slug IN ('desoto', 'monroe')
ORDER BY county_slug;

-- 2. Check scraper schedule  
SELECT 
    'SCRAPER SCHEDULE' as check_type,
    county_slug,
    scraper_type,
    frequency,
    enabled,
    next_run,
    last_successful_run
FROM pipeline.scraper_schedule
WHERE county_slug IN ('desoto', 'monroe')
ORDER BY county_slug, scraper_type;

-- 3. Check for any auction data (should start appearing after first scrape)
SELECT 
    'AUCTION DATA CHECK' as check_type,
    county,
    COUNT(*) as total_auctions,
    COUNT(CASE WHEN sale_type = 'foreclosure' THEN 1 END) as foreclosures,
    COUNT(CASE WHEN sale_type = 'tax_deed' THEN 1 END) as tax_deeds,
    MIN(created_at) as first_auction_date,
    MAX(created_at) as latest_auction_date
FROM multi_county_auctions
WHERE county IN ('desoto', 'monroe')
GROUP BY county
ORDER BY county;

-- 4. Check A-lane metrics after configuration (should move from null to some value)
SELECT 'A METRIC VERIFICATION desoto' as check_type, * FROM public.pencil_dod_evaluate_county('desoto');
SELECT 'A METRIC VERIFICATION monroe' as check_type, * FROM public.pencil_dod_evaluate_county('monroe');

-- 5. Compare against other small counties for sanity check
SELECT 
    'COMPARISON WITH SMALL COUNTIES' as check_type,
    county,
    COUNT(*) as auction_count,
    MIN(sale_date) as earliest_sale,
    MAX(sale_date) as latest_sale
FROM multi_county_auctions 
WHERE county IN ('desoto', 'monroe', 'lafayette', 'glades', 'dixie')  -- Small FL counties
GROUP BY county
ORDER BY auction_count;
"""

    verification_file = f"shard8_a_lane_verification_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
    
    with open(verification_file, 'w') as f:
        f.write(f"-- SHARD-8 A-LANE VERIFICATION - Generated at {datetime.now().isoformat()}\n")
        f.write(f"-- Run AFTER configuration and first scrape cycle\n\n")
        f.write(verification_sql)
    
    log(f"✅ Verification SQL written to: {verification_file}")
    return verification_file

def main():
    """Main execution function"""
    log("🚀 Starting SHARD-8 A-Lane Configuration for desoto and monroe")
    log("Target: Configure dual-product coverage to move A metrics from null to PASS")
    
    # Generate all SQL files
    config_file, schedule_file = create_sql_files()
    verification_file = generate_verification_sql()
    
    log("\n📋 A-LANE SETUP SUMMARY:")
    log(f"✅ Generated county config SQL: {config_file}")
    log(f"✅ Generated scraper schedule SQL: {schedule_file}")
    log(f"✅ Generated verification SQL: {verification_file}")
    
    log("\n🎯 EXECUTION ORDER:")
    log("1. Execute county configuration SQL (sets up pipeline.counties)")
    log("2. Execute scraper schedule SQL (enables automated scraping)")
    log("3. Wait for first scrape cycle (05:30Z or manual trigger)")
    log("4. Run verification SQL to confirm A-lane metrics")
    log("5. Check pencil_dod_evaluate_county for A metric improvement")
    
    log(f"\n📊 EXPECTED IMPACT:")
    log(f"- desoto: A metric null → TBD (depends on county auction volume)")
    log(f"- monroe: A metric null → TBD (Keys market - expect higher volumes)")
    log(f"- Both counties: All other metrics become measurable vs null")
    log(f"- Foundation for B, C, D, E, F, G, H, I, J letter improvements")
    
    log("\n⚠️ POST-CONFIGURATION STEPS:")
    log("- Monitor first scrape runs for errors")
    log("- Verify RealAuction endpoints are accessible") 
    log("- Check for county-specific URL variations")
    log("- May need custom clerk scrapers if RealAuction unavailable")
    
    log("\n✅ SHARD-8 A-Lane configuration ready for deployment")
    
    return {
        "status": "SUCCESS",
        "config_file": config_file,
        "schedule_file": schedule_file,
        "verification_file": verification_file,
        "target_counties": ['desoto', 'monroe'],
        "expected_desoto_impact": "A null → TBD",
        "expected_monroe_impact": "A null → TBD"
    }

if __name__ == "__main__":
    try:
        result = main()
        print(f"\n🎯 Result: {json.dumps(result, indent=2)}")
    except Exception as e:
        log(f"❌ Error in main execution: {e}", "ERROR")
        sys.exit(1)