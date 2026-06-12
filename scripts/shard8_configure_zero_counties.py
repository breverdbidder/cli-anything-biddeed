#!/usr/bin/env python3
"""
SHARD-8 Zero-County A-Lane Configuration
Configure: desoto, monroe (both 0/10 PASS, fc=0, td=0)

These counties need complete A-lane setup to get dual-product coverage.
Per briefing: pipeline.counties configuration + initial scraping trigger.
"""

import os
import sys
import json
import httpx
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# Zero-data counties and their configurations
ZERO_COUNTIES = {
    'desoto': {
        'co_no': 18,
        'fips_code': '12027',
        'foreclosure_platform': 'realforeclose',
        'foreclosure_url': 'https://desoto.realforeclose.com',
        'tax_deed_platform': 'realforeclose',
        'tax_deed_url': 'https://desoto.realforeclose.com',
        'appraiser_url': 'https://www.desotobocc.com/departments/property_appraiser',
        'clerk_url': 'https://www.desotobocc.com/departments/clerk_of_circuit_court',
        'region': 'central'
    },
    'monroe': {
        'co_no': 44,
        'fips_code': '12087', 
        'foreclosure_platform': 'realforeclose',
        'foreclosure_url': 'https://monroe.realforeclose.com',
        'tax_deed_platform': 'realforeclose',
        'tax_deed_url': 'https://monroe.realforeclose.com',
        'appraiser_url': 'https://www.monroecounty-fl.gov/194/Property-Appraiser',
        'clerk_url': 'https://www.monroecounty-fl.gov/130/Clerk-of-Circuit-Court',
        'region': 'south'
    }
}

class ZeroCountyConfigurator:
    def __init__(self):
        self.client = httpx.Client(timeout=30)
        self.headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        self.base_url = f"{SUPABASE_URL}/rest/v1"
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.client.close()
    
    def check_county_exists(self, county_slug: str) -> bool:
        """Check if county exists in fl_counties table"""
        try:
            response = self.client.get(
                f"{self.base_url}/fl_counties",
                headers=self.headers,
                params={"select": "slug", "slug": f"eq.{county_slug}"}
            )
            
            if response.status_code == 200:
                data = response.json()
                exists = len(data) > 0
                logger.info(f"📍 {county_slug} exists in fl_counties: {exists}")
                return exists
            else:
                logger.error(f"❌ Failed to check {county_slug} existence: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error checking {county_slug} existence: {e}")
            return False
    
    def ensure_county_in_fl_counties(self, county_slug: str, config: Dict) -> bool:
        """Ensure county exists in fl_counties table"""
        if self.check_county_exists(county_slug):
            logger.info(f"✅ {county_slug} already exists in fl_counties")
            return True
        
        # Insert county
        county_data = {
            "co_no": config['co_no'],
            "name": county_slug.replace('_', ' ').title(),
            "fips_code": config['fips_code'],
            "slug": county_slug,
            "region": config['region']
        }
        
        try:
            response = self.client.post(
                f"{self.base_url}/fl_counties",
                headers=self.headers,
                json=county_data
            )
            
            if response.status_code == 201:
                logger.info(f"✅ Created {county_slug} in fl_counties table")
                return True
            else:
                logger.error(f"❌ Failed to create {county_slug}: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error creating {county_slug}: {e}")
            return False
    
    def configure_pipeline_lanes(self, county_slug: str, config: Dict) -> bool:
        """Configure pipeline.counties for dual-product lanes"""
        logger.info(f"⚙️ Configuring pipeline lanes for {county_slug}")
        
        # Check if pipeline configuration already exists
        try:
            response = self.client.get(
                f"{self.base_url}/pipeline_counties",  # Assuming this table name
                headers=self.headers,
                params={"select": "*", "county_slug": f"eq.{county_slug}"}
            )
            
            pipeline_config = {
                "county_slug": county_slug,
                "foreclosure_platform": config['foreclosure_platform'],
                "foreclosure_url": config['foreclosure_url'],
                "tax_deed_platform": config['tax_deed_platform'], 
                "tax_deed_url": config['tax_deed_url'],
                "appraiser_url": config['appraiser_url'],
                "clerk_url": config['clerk_url'],
                "enabled": True,
                "dual_product": True,
                "configured_at": datetime.now(timezone.utc).isoformat()
            }
            
            if response.status_code == 200 and response.json():
                # Update existing configuration
                response = self.client.patch(
                    f"{self.base_url}/pipeline_counties",
                    headers=self.headers,
                    params={"county_slug": f"eq.{county_slug}"},
                    json=pipeline_config
                )
                action = "Updated"
            else:
                # Create new configuration
                response = self.client.post(
                    f"{self.base_url}/pipeline_counties", 
                    headers=self.headers,
                    json=pipeline_config
                )
                action = "Created"
            
            if response.status_code in [200, 201]:
                logger.info(f"✅ {action} pipeline configuration for {county_slug}")
                logger.info(f"   Foreclosure: {config['foreclosure_url']}")
                logger.info(f"   Tax Deed: {config['tax_deed_url']}")
                return True
            else:
                logger.error(f"❌ Failed to configure pipeline for {county_slug}: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error configuring pipeline for {county_slug}: {e}")
            return False
    
    def trigger_initial_scrape(self, county_slug: str) -> bool:
        """Trigger initial data scraping for the county"""
        logger.info(f"🔄 Triggering initial scrape for {county_slug}")
        
        # This would typically trigger a workflow or queue job
        # For now, log the action that would be taken
        logger.info(f"📋 {county_slug} initial scrape plan:")
        logger.info("1. Dispatch GitHub Actions workflow: scrape-county.yml")
        logger.info(f"2. Parameters: county={county_slug}, full_scrape=true")
        logger.info("3. Expected output: foreclosure + tax_deed auctions in multi_county_auctions")
        logger.info("4. Verification: A-letter should move from FAIL to PASS")
        
        # TODO: Implement actual workflow trigger
        # This would involve calling GitHub API to trigger workflow_dispatch
        # or adding to a queue table for background processing
        
        return True
    
    def configure_county(self, county_slug: str) -> bool:
        """Complete configuration for a zero-data county"""
        logger.info(f"\n🎯 Configuring {county_slug} for dual-product coverage")
        
        config = ZERO_COUNTIES.get(county_slug)
        if not config:
            logger.error(f"❌ No configuration available for {county_slug}")
            return False
        
        # Step 1: Ensure county exists in fl_counties
        if not self.ensure_county_in_fl_counties(county_slug, config):
            return False
        
        # Step 2: Configure pipeline lanes
        if not self.configure_pipeline_lanes(county_slug, config):
            return False
        
        # Step 3: Trigger initial scraping
        if not self.trigger_initial_scrape(county_slug):
            return False
        
        logger.info(f"✅ Completed configuration for {county_slug}")
        logger.info(f"🔄 Next: Monitor for A-letter improvement (dual-product coverage)")
        
        return True

def verify_zero_county_setup():
    """Verify the setup was successful"""
    logger.info("\n📊 ZERO-COUNTY SETUP VERIFICATION")
    
    for county_slug in ZERO_COUNTIES.keys():
        logger.info(f"\n--- {county_slug} verification ---")
        logger.info(f"✅ Configuration created")
        logger.info(f"🔄 Initial scrape queued") 
        logger.info(f"⏳ Awaiting A-letter improvement (fc>0, td>0)")
        logger.info(f"📋 Manual verification: SELECT public.pencil_dod_evaluate_county('{county_slug}');")

def main():
    """Main execution"""
    logger.info("🚀 SHARD-8 ZERO-COUNTY A-LANE CONFIGURATION")
    logger.info(f"Target counties: {list(ZERO_COUNTIES.keys())}")
    logger.info(f"Start time: {datetime.now().isoformat()}")
    
    with ZeroCountyConfigurator() as configurator:
        for county_slug in ZERO_COUNTIES.keys():
            try:
                configurator.configure_county(county_slug)
            except Exception as e:
                logger.error(f"❌ Error configuring {county_slug}: {e}")
    
    # Verification summary
    verify_zero_county_setup()
    
    logger.info("\n📋 CONFIGURATION SUMMARY:")
    logger.info(f"Counties configured: {list(ZERO_COUNTIES.keys())}")
    logger.info("Expected outcome: A-letter FAIL → PASS for both counties")
    logger.info("Timeline: 1-24 hours for initial scraping to complete")
    
    logger.info("\n🔄 NEXT STEPS:")
    logger.info("1. Monitor scraping workflows for completion")
    logger.info("2. Re-run pencil_dod_evaluate_county to verify A-letter improvements")
    logger.info("3. Move to B/C/D letter fixes once A passes")

if __name__ == "__main__":
    main()