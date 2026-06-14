#!/usr/bin/env python3
"""
Populate CMA (Comparative Market Analysis) Pipeline for J Generator
Creates the foundation data needed for real bid_decisions generation

Usage:
    python3 scripts/populate_cma_pipeline.py duval [--batch-size 500]
    python3 scripts/populate_cma_pipeline.py brevard [--batch-size 500]
    python3 scripts/populate_cma_pipeline.py both [--batch-size 250]
"""
import os
import sys
import argparse
import json
import requests
import logging
from typing import Dict, List

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CMAPopulator:
    def __init__(self):
        self.supabase_url = "https://mocerqjnksmhcjzxrewo.supabase.co"
        self.supabase_key = os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('SUPABASE_KEY')
        
        if not self.supabase_key:
            logger.error("No Supabase API key found in environment")
            sys.exit(1)
            
        self.headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json"
        }

    def apply_migration(self) -> bool:
        """Apply the CMA pipeline migration"""
        try:
            # Read the migration file
            migration_path = "/home/runner/work/cli-anything-biddeed/cli-anything-biddeed/migrations/20260614_create_cma_pipeline.sql"
            
            with open(migration_path, 'r') as f:
                migration_sql = f.read()
            
            # Execute the migration
            response = requests.post(
                f"{self.supabase_url}/rest/v1/rpc/exec_sql",
                headers=self.headers,
                json={"query": migration_sql},
                timeout=60
            )
            
            if response.status_code == 200:
                logger.info("✅ CMA pipeline migration applied successfully")
                return True
            else:
                logger.error(f"❌ Migration failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error applying migration: {e}")
            return False

    def check_auction_count(self, county: str) -> int:
        """Check how many auctions need CMA data"""
        try:
            query = f"""
            SELECT COUNT(*) as missing_count
            FROM multi_county_auctions mca
            LEFT JOIN gen_valuations_comps_batch gcb ON gcb.case_number = mca.case_number AND gcb.county_slug = mca.county
            WHERE mca.county = '{county}' 
            AND gcb.case_number IS NULL
            AND mca.assessed_value > 0
            """
            
            response = requests.post(
                f"{self.supabase_url}/rest/v1/rpc/exec_sql",
                headers=self.headers,
                json={"query": query},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                count = result[0]['missing_count'] if result else 0
                logger.info(f"📊 {county}: {count} auctions need CMA data")
                return count
            else:
                logger.error(f"Failed to check count for {county}: {response.status_code}")
                return 0
                
        except Exception as e:
            logger.error(f"Error checking count for {county}: {e}")
            return 0

    def populate_cma_batch(self, county: str, batch_size: int = 500) -> Dict[str, int]:
        """Populate CMA data for a county using the batch function"""
        try:
            logger.info(f"🚀 Starting CMA population for {county} (batch size: {batch_size})")
            
            # Use the SQL function to populate CMA data
            response = requests.post(
                f"{self.supabase_url}/rest/v1/rpc/populate_cma_batch",
                headers=self.headers,
                json={
                    "p_county_slug": county,
                    "p_limit": batch_size
                },
                timeout=180  # 3 minutes for large batches
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ {county} CMA population completed")
                logger.info(f"   Processed: {result.get('processed', 0)}")
                logger.info(f"   Success: {result.get('success', 0)}")
                logger.info(f"   Errors: {result.get('errors', 0)}")
                
                return {
                    "processed": result.get('processed', 0),
                    "success": result.get('success', 0),
                    "errors": result.get('errors', 0)
                }
            else:
                logger.error(f"❌ CMA population failed for {county}: {response.status_code} - {response.text}")
                return {"processed": 0, "success": 0, "errors": 1}
                
        except Exception as e:
            logger.error(f"❌ Error populating CMA for {county}: {e}")
            return {"processed": 0, "success": 0, "errors": 1}

    def verify_cma_data(self, county: str) -> Dict[str, any]:
        """Verify CMA data quality for a county"""
        try:
            query = f"""
            SELECT 
                COUNT(*) as total_records,
                COUNT(CASE WHEN sufficient_comps_found THEN 1 END) as sufficient_comps,
                AVG(confidence_score) as avg_confidence,
                AVG(distressed_comp_count) as avg_distressed_comps,
                AVG(resale_comp_count) as avg_resale_comps,
                MIN(cma_distressed) as min_distressed,
                MAX(cma_distressed) as max_distressed,
                MIN(cma_resale) as min_resale,
                MAX(cma_resale) as max_resale
            FROM gen_valuations_comps_batch
            WHERE county_slug = '{county}'
            """
            
            response = requests.post(
                f"{self.supabase_url}/rest/v1/rpc/exec_sql",
                headers=self.headers,
                json={"query": query},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result:
                    stats = result[0]
                    logger.info(f"📈 {county} CMA Data Quality:")
                    logger.info(f"   Total records: {stats.get('total_records', 0)}")
                    logger.info(f"   Sufficient comps: {stats.get('sufficient_comps', 0)}")
                    logger.info(f"   Avg confidence: {float(stats.get('avg_confidence', 0)):.2f}")
                    logger.info(f"   Avg distressed comps: {float(stats.get('avg_distressed_comps', 0)):.1f}")
                    logger.info(f"   Avg resale comps: {float(stats.get('avg_resale_comps', 0)):.1f}")
                    
                    return stats
                    
            return {}
            
        except Exception as e:
            logger.error(f"Error verifying CMA data for {county}: {e}")
            return {}

def main():
    parser = argparse.ArgumentParser(description='Populate CMA Pipeline for J Generator')
    parser.add_argument('county', choices=['duval', 'brevard', 'both'], 
                       help='County to process')
    parser.add_argument('--batch-size', type=int, default=500,
                       help='Number of auctions to process (default: 500)')
    parser.add_argument('--skip-migration', action='store_true',
                       help='Skip applying the migration (assume already applied)')
    parser.add_argument('--verify-only', action='store_true',
                       help='Only verify existing CMA data, do not populate')
    
    args = parser.parse_args()
    
    populator = CMAPopulator()
    
    # Apply migration first (unless skipped)
    if not args.skip_migration:
        if not populator.apply_migration():
            logger.error("Migration failed, aborting")
            sys.exit(1)
    
    counties_to_process = ['duval', 'brevard'] if args.county == 'both' else [args.county]
    
    total_results = {"processed": 0, "success": 0, "errors": 0}
    
    for county in counties_to_process:
        if args.verify_only:
            populator.verify_cma_data(county)
            continue
            
        # Check current state
        missing_count = populator.check_auction_count(county)
        
        if missing_count == 0:
            logger.info(f"✅ {county} already has complete CMA data")
            populator.verify_cma_data(county)
            continue
            
        # Populate CMA data
        county_results = populator.populate_cma_batch(county, args.batch_size)
        
        # Aggregate results
        for key in total_results:
            total_results[key] += county_results[key]
            
        # Verify the results
        populator.verify_cma_data(county)
    
    print("\n" + "="*60)
    print("CMA PIPELINE POPULATION SUMMARY")
    print("="*60)
    print(f"Counties: {', '.join(counties_to_process)}")
    print(f"Total processed: {total_results['processed']}")
    print(f"Successful: {total_results['success']}")
    print(f"Errors: {total_results['errors']}")
    
    if total_results['success'] > 0:
        print(f"\n✅ CMA data populated for {total_results['success']} auctions")
        print("🎯 J Generator is now ready for real CMA data integration")
        print("📋 Next step: Run J Generator with updated CMA integration")

if __name__ == "__main__":
    main()