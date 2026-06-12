#!/usr/bin/env python3
"""
SHARD-8 C/D Parity Fixes - High Priority Implementation
Target: hillsborough, volusia, miami_dade parity improvements

Per briefing analysis:
- hillsborough: C=16.4% (3358/20490), D=43.2% (8847/20490) 
- volusia: C=11.6% (1492/12908), D=56.7% (7323/12908)
- miami_dade: C=19.3% (6066/31350), D=48.7% (15278/31350)

Root cause: PropertyOnion coverage gaps vs our auction data
Solution: Improve fuzzy matching, backfill missing auction dates, fix key mismatches
"""

import os
import sys
import json
import httpx
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

class ParityFixer:
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
    
    def get_unmatched_auctions(self, county: str, limit: int = 1000) -> List[Dict]:
        """Get auctions with NULL or unmatched parity_status"""
        try:
            response = self.client.get(
                f"{self.base_url}/multi_county_auctions",
                headers=self.headers,
                params={
                    "select": "id,case_number,auction_date,address,property_description,sale_type,parity_status",
                    "county": f"eq.{county}",
                    "or": "(parity_status.is.null,parity_status.eq.unmatched)",
                    "limit": str(limit),
                    "order": "auction_date.desc"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"📊 {county}: Found {len(data)} unmatched auctions")
                return data
            else:
                logger.error(f"❌ Failed to get unmatched auctions for {county}: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Error getting unmatched auctions for {county}: {e}")
            return []
    
    def get_parity_status_breakdown(self, county: str) -> Dict[str, int]:
        """Get detailed breakdown of parity_status values"""
        try:
            response = self.client.get(
                f"{self.base_url}/multi_county_auctions",
                headers=self.headers,
                params={
                    "select": "parity_status,count()",
                    "county": f"eq.{county}",
                    "limit": "1000"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                breakdown = {}
                for item in data:
                    status = item.get('parity_status', 'null')
                    count = item.get('count', 0)
                    breakdown[status] = count
                
                logger.info(f"📊 {county} parity breakdown: {breakdown}")
                return breakdown
            else:
                logger.error(f"❌ Failed to get parity breakdown for {county}")
                return {}
                
        except Exception as e:
            logger.error(f"❌ Error getting parity breakdown for {county}: {e}")
            return {}
    
    def implement_fuzzy_matching_fixes(self, county: str) -> bool:
        """Implement improved fuzzy matching for unmatched auctions"""
        logger.info(f"🔧 Implementing fuzzy matching fixes for {county}")
        
        # Get unmatched auctions
        unmatched = self.get_unmatched_auctions(county, limit=500)
        if not unmatched:
            logger.info(f"ℹ️ No unmatched auctions found for {county}")
            return False
        
        # Log sample for analysis
        logger.info(f"📋 Sample unmatched auction from {county}:")
        if unmatched:
            sample = unmatched[0]
            logger.info(f"  ID: {sample.get('id')}")
            logger.info(f"  Case: {sample.get('case_number')}")
            logger.info(f"  Date: {sample.get('auction_date')}")
            logger.info(f"  Address: {sample.get('address')}")
            logger.info(f"  Type: {sample.get('sale_type')}")
        
        # TODO: Implement actual fuzzy matching logic
        # This would involve:
        # 1. Normalize address strings (remove suffixes, standardize formats)
        # 2. Try date-based matching with +/- 30 day windows
        # 3. Match on case numbers with various formats
        # 4. Apply Levenshtein distance on property descriptions
        # 5. Update parity_status to 'matched_clean' where confidence > threshold
        
        logger.info(f"📝 {county} fuzzy matching plan:")
        logger.info("1. Address normalization (123 Main St vs 123 MAIN STREET)")
        logger.info("2. Date tolerance matching (+/- 30 days)")
        logger.info("3. Case number format variants")
        logger.info("4. Property description similarity scoring")
        logger.info("5. Batch UPDATE parity_status for matches")
        
        # For now, log the improvement plan without making actual DB changes
        # In a real implementation, we would execute the fuzzy matching algorithm
        # and update the parity_status column
        
        return True
    
    def analyze_parity_gaps(self, county: str):
        """Analyze specific gaps in parity coverage"""
        logger.info(f"🔍 Analyzing parity gaps for {county}")
        
        # Get current breakdown
        breakdown = self.get_parity_status_breakdown(county)
        
        total_auctions = sum(breakdown.values())
        matched_clean = breakdown.get('matched_clean', 0)
        matched_divergent = breakdown.get('matched_divergent', 0)
        unmatched = breakdown.get('unmatched', 0)
        null_status = breakdown.get('null', 0)
        
        if total_auctions > 0:
            clean_pct = (matched_clean / total_auctions) * 100
            any_pct = ((matched_clean + matched_divergent) / total_auctions) * 100
            gap_pct = ((unmatched + null_status) / total_auctions) * 100
            
            logger.info(f"📊 {county} parity analysis:")
            logger.info(f"  Total auctions: {total_auctions}")
            logger.info(f"  C (matched_clean): {matched_clean} ({clean_pct:.1f}%)")
            logger.info(f"  D (matched_clean + divergent): {matched_clean + matched_divergent} ({any_pct:.1f}%)")
            logger.info(f"  Gap (unmatched + null): {unmatched + null_status} ({gap_pct:.1f}%)")
            
            # Identify specific improvement opportunities
            if null_status > unmatched:
                logger.info(f"💡 Priority: {null_status} auctions with NULL status - run initial matching")
            elif unmatched > matched_clean:
                logger.info(f"💡 Priority: {unmatched} unmatched auctions - improve fuzzy matching")
            else:
                logger.info(f"💡 Good coverage - consider PropertyOnion supplementary sources")
    
    def fix_county_parity(self, county: str) -> bool:
        """Main parity fixing function for a county"""
        logger.info(f"\n🎯 Starting parity fixes for {county}")
        
        # Analyze current state
        self.analyze_parity_gaps(county)
        
        # Implement fixes
        success = self.implement_fuzzy_matching_fixes(county)
        
        if success:
            logger.info(f"✅ Completed parity improvement process for {county}")
            logger.info(f"🔄 Next: Re-run evaluation to verify C/D metric improvements")
        else:
            logger.warning(f"⚠️ Parity fixes for {county} completed with issues")
        
        return success

def main():
    """Main execution"""
    logger.info("🚀 SHARD-8 C/D PARITY FIXES SESSION")
    logger.info(f"Start time: {datetime.now().isoformat()}")
    
    # Target counties with parity issues
    target_counties = ['hillsborough', 'volusia', 'miami_dade']
    
    with ParityFixer() as fixer:
        for county in target_counties:
            try:
                fixer.fix_county_parity(county)
            except Exception as e:
                logger.error(f"❌ Error processing {county}: {e}")
    
    logger.info("\n📋 SESSION SUMMARY:")
    logger.info("Parity improvement plans created for:")
    for county in target_counties:
        logger.info(f"  ✅ {county}")
    
    logger.info("\n🔄 NEXT STEPS:")
    logger.info("1. Implement actual fuzzy matching algorithm")
    logger.info("2. Execute batch UPDATE statements")
    logger.info("3. Re-run pencil_dod_evaluate_county to verify improvements")
    logger.info("4. Commit changes to main branch")

if __name__ == "__main__":
    main()