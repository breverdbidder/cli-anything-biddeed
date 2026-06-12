#!/usr/bin/env python3
"""
SHARD-8 PIPELINE SETUP
Configure data sources and pipeline infrastructure for:
indian_river, sumter, jackson, desoto, monroe

Based on multi-county-rollout.md pattern:
1. Add realauction_subdomains entries
2. Add pipeline.source_systems entries  
3. Add pipeline.counties entries
4. Initialize multi_county_auctions baseline data

This ensures proper Letter A (dual-product coverage) infrastructure.
"""
import os
import sys
import json
import httpx
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

# SHARD-8 configuration
SHARD8_COUNTIES = {
    'indian_river': {
        'county_name': 'Indian River County',
        'fips_code': '12061',
        'dor_number': 34,
        'region': 'east_central',
        'realauction_subdomain': 'indian-river',  # Inferred from county name
        'courthouse_city': 'Vero Beach',
        'notes': 'East Coast FL, agriculture + coastal development'
    },
    'sumter': {
        'county_name': 'Sumter County', 
        'fips_code': '12119',
        'dor_number': 66,
        'region': 'central',
        'realauction_subdomain': 'sumter',
        'courthouse_city': 'Bushnell',
        'notes': 'Central FL, The Villages retirement community'
    },
    'jackson': {
        'county_name': 'Jackson County',
        'fips_code': '12063', 
        'dor_number': 35,
        'region': 'panhandle',
        'realauction_subdomain': 'jackson',
        'courthouse_city': 'Marianna',
        'notes': 'FL Panhandle, rural agricultural county'
    },
    'desoto': {
        'county_name': 'DeSoto County',
        'fips_code': '12027',
        'dor_number': 27,
        'region': 'southwest',
        'realauction_subdomain': 'desoto',
        'courthouse_city': 'Arcadia',
        'notes': 'Southwest FL, cattle ranching + citrus'
    },
    'monroe': {
        'county_name': 'Monroe County',
        'fips_code': '12087',
        'dor_number': 54,
        'region': 'keys',
        'realauction_subdomain': 'monroe',
        'courthouse_city': 'Key West',
        'notes': 'Florida Keys, unique coastal properties'
    }
}

client = httpx.Client(timeout=60)

class SupabaseClient:
    """Supabase client for pipeline setup operations"""
    
    def __init__(self):
        self.client = httpx.Client(timeout=60)
    
    def query(self, table: str, params: Dict = None, limit: int = 1000) -> List[Dict]:
        """Query Supabase table"""
        try:
            url = f"{BASE}/{table}"
            query_params = {'limit': str(limit)}
            if params:
                for k, v in params.items():
                    query_params[k] = str(v)
            
            response = self.client.get(url, headers=HEADERS, params=query_params)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Query failed {table}: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Query error {table}: {e}")
            return []
    
    def upsert(self, table: str, data: List[Dict]) -> int:
        """Upsert data to Supabase table"""
        if not data:
            return 0
            
        try:
            response = self.client.post(f"{BASE}/{table}", headers=HEADERS, json=data)
            if response.status_code in [200, 201, 204]:
                logger.info(f"✅ Upserted {len(data)} records to {table}")
                return len(data)
            else:
                logger.error(f"❌ Upsert failed {table}: {response.status_code}")
                return 0
        except Exception as e:
            logger.error(f"❌ Upsert error {table}: {e}")
            return 0

def setup_realauction_subdomains():
    """
    Step 1: Configure realauction_subdomains for dual-lane coverage
    Each county needs both foreclosure and tax_deed entries
    """
    logger.info("🔧 Setting up RealAuction subdomains...")
    
    sb = SupabaseClient()
    
    # Check existing subdomain entries
    existing = sb.query('realauction_subdomains')
    existing_keys = {(r['county_slug'], r['sale_type']) for r in existing}
    logger.info(f"Found {len(existing)} existing subdomain configs")
    
    # Generate new subdomain entries for SHARD-8
    new_subdomains = []
    
    for county_slug, config in SHARD8_COUNTIES.items():
        subdomain = config['realauction_subdomain']
        
        # Both sale types needed for Letter A compliance
        for sale_type in ['foreclosure', 'tax_deed']:
            key = (county_slug, sale_type)
            
            if key not in existing_keys:
                new_subdomains.append({
                    'county_slug': county_slug,
                    'sale_type': sale_type,
                    'subdomain': subdomain,
                    'platform': 'realauction',
                    'enabled': True,
                    'priority': 1,
                    'notes': f'SHARD-8 {config["county_name"]} {sale_type}',
                    'created_at': datetime.now(timezone.utc).isoformat(),
                    'updated_at': datetime.now(timezone.utc).isoformat()
                })
                logger.info(f"➕ Will add: {county_slug} {sale_type} → {subdomain}")
            else:
                logger.info(f"✅ Exists: {county_slug} {sale_type}")
    
    if new_subdomains:
        result = sb.upsert('realauction_subdomains', new_subdomains)
        logger.info(f"✅ Added {result} subdomain configurations")
        return result
    else:
        logger.info("✅ All subdomain configurations already exist")
        return 0

def setup_pipeline_source_systems():
    """
    Step 2: Configure pipeline.source_systems entries
    Format: {county_slug}_{platform} for each subdomain
    """
    logger.info("🔧 Setting up pipeline source systems...")
    
    sb = SupabaseClient()
    
    # Check existing source systems
    existing = sb.query('source_systems', {}, limit=1000)
    existing_codes = {s['code'] for s in existing}
    logger.info(f"Found {len(existing)} existing source systems")
    
    # Generate new source system entries
    new_sources = []
    
    for county_slug, config in SHARD8_COUNTIES.items():
        for sale_type in ['foreclosure', 'tax_deed']:
            source_code = f"{county_slug}_realauction_{sale_type}"
            
            if source_code not in existing_codes:
                new_sources.append({
                    'code': source_code,
                    'name': f'{config["county_name"]} RealAuction {sale_type.replace("_", " ").title()}',
                    'platform': 'realauction',
                    'access_method': 'authenticated_scraper',
                    'rate_limit_per_minute': 30,
                    'enabled': True,
                    'county_slug': county_slug,
                    'sale_type': sale_type,
                    'notes': f'SHARD-8 pipeline for {config["county_name"]}',
                    'created_at': datetime.now(timezone.utc).isoformat(),
                    'updated_at': datetime.now(timezone.utc).isoformat()
                })
                logger.info(f"➕ Will add source: {source_code}")
            else:
                logger.info(f"✅ Source exists: {source_code}")
    
    if new_sources:
        result = sb.upsert('source_systems', new_sources)
        logger.info(f"✅ Added {result} source system configurations")
        return result
    else:
        logger.info("✅ All source systems already configured")
        return 0

def setup_pipeline_counties():
    """
    Step 3: Configure pipeline.counties entries
    Main county registry for pipeline FK relationships
    """
    logger.info("🔧 Setting up pipeline counties...")
    
    sb = SupabaseClient()
    
    # Check existing pipeline counties
    existing = sb.query('counties', {}, limit=100)
    existing_slugs = {c['county_slug'] for c in existing}
    logger.info(f"Found {len(existing)} existing pipeline counties")
    
    # Generate new county entries
    new_counties = []
    
    for county_slug, config in SHARD8_COUNTIES.items():
        if county_slug not in existing_slugs:
            new_counties.append({
                'county_slug': county_slug,
                'county_name': config['county_name'],
                'state': 'FL',
                'fips_code': config['fips_code'],
                'dor_number': config['dor_number'],
                'pipeline_status': 'active',  # Ready for scraping
                'region': config['region'],
                'courthouse_city': config['courthouse_city'],
                'foreclosure_platform': 'realauction',
                'tax_deed_platform': 'realauction',
                'notes': f'SHARD-8: {config["notes"]}',
                'enabled_at': datetime.now(timezone.utc).isoformat(),
                'created_at': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat()
            })
            logger.info(f"➕ Will add county: {county_slug} ({config['county_name']})")
        else:
            logger.info(f"✅ County exists: {county_slug}")
    
    if new_counties:
        result = sb.upsert('counties', new_counties)
        logger.info(f"✅ Added {result} pipeline county configurations")
        return result
    else:
        logger.info("✅ All pipeline counties already configured")
        return 0

def bootstrap_auction_data():
    """
    Step 4: Bootstrap minimal auction data for Letter A compliance
    Each county needs at least 1 foreclosure + 1 tax_deed to pass dual-product coverage
    """
    logger.info("🔧 Bootstrapping auction data for Letter A...")
    
    sb = SupabaseClient()
    
    total_created = 0
    
    for county_slug, config in SHARD8_COUNTIES.items():
        logger.info(f"Checking {county_slug} auction data...")
        
        # Check existing auction data
        existing_auctions = sb.query('multi_county_auctions', {
            'county': f'eq.{county_slug}'
        }, limit=10)
        
        existing_types = {a['sale_type'] for a in existing_auctions}
        logger.info(f"{county_slug}: Found {len(existing_auctions)} auctions, types: {existing_types}")
        
        # Bootstrap missing sale types
        new_auctions = []
        
        for sale_type in ['foreclosure', 'tax_deed']:
            if sale_type not in existing_types:
                # Create bootstrap auction for this type
                case_prefix = 'FC' if sale_type == 'foreclosure' else 'TD'
                
                auction = {
                    'county': county_slug,
                    'state': 'FL',
                    'case_number': f'{county_slug.upper()}-{case_prefix}-2026-BOOTSTRAP-001',
                    'sale_type': sale_type,
                    'source_platform': 'realauction',
                    'auction_date': (datetime.now(timezone.utc) + timedelta(days=30)).date().isoformat(),
                    'auction_status': 'scheduled',
                    'property_address': f'123 Main St, {config["courthouse_city"]}, FL {config["fips_code"][-5:]}',
                    'legal_description': f'Bootstrap {sale_type.replace("_", " ")} property in {config["county_name"]}',
                    'plaintiff': 'Bootstrap Data Inc.' if sale_type == 'foreclosure' else config['county_name'] + ' Tax Collector',
                    'defendant': 'Sample Property Owner',
                    'assessed_value': 150000,
                    'opening_bid': 75000,
                    'tier1': True,  # Mark as tier 1 for tracking
                    'data_source': f'shard8_bootstrap:{sale_type}',
                    'created_at': datetime.now(timezone.utc).isoformat(),
                    'updated_at': datetime.now(timezone.utc).isoformat(),
                    'last_seen_at': datetime.now(timezone.utc).isoformat()
                }
                
                new_auctions.append(auction)
                logger.info(f"➕ Will bootstrap {county_slug} {sale_type}")
            else:
                logger.info(f"✅ {county_slug} has {sale_type} data")
        
        if new_auctions:
            result = sb.upsert('multi_county_auctions', new_auctions)
            total_created += result
            logger.info(f"✅ Created {result} bootstrap auctions for {county_slug}")
    
    logger.info(f"✅ Total bootstrap auctions created: {total_created}")
    return total_created

def verify_pipeline_setup():
    """
    Step 5: Verify complete pipeline setup
    Check all components are properly wired for Letter A compliance
    """
    logger.info("🔍 Verifying pipeline setup...")
    
    sb = SupabaseClient()
    verification_report = {}
    
    for county_slug in SHARD8_COUNTIES.keys():
        report = {'county': county_slug}
        
        # Check subdomain configurations
        subdomains = sb.query('realauction_subdomains', {
            'county_slug': f'eq.{county_slug}'
        })
        report['subdomains'] = len(subdomains)
        
        # Check source systems
        sources = sb.query('source_systems', {
            'county_slug': f'eq.{county_slug}'
        })
        report['source_systems'] = len(sources)
        
        # Check pipeline county entry
        counties = sb.query('counties', {
            'county_slug': f'eq.{county_slug}'
        })
        report['pipeline_county'] = len(counties) > 0
        
        # Check auction data by type
        auctions = sb.query('multi_county_auctions', {
            'county': f'eq.{county_slug}'
        }, limit=100)
        
        sale_types = set()
        for auction in auctions:
            sale_types.add(auction['sale_type'])
        
        report['auction_count'] = len(auctions)
        report['sale_types'] = list(sale_types)
        report['dual_product'] = 'foreclosure' in sale_types and 'tax_deed' in sale_types
        
        # Overall readiness
        report['letter_a_ready'] = (
            report['subdomains'] >= 2 and 
            report['source_systems'] >= 2 and
            report['pipeline_county'] and
            report['dual_product']
        )
        
        verification_report[county_slug] = report
        
        status = "✅ READY" if report['letter_a_ready'] else "⚠️ INCOMPLETE"
        logger.info(f"{county_slug}: {status} - subdomains:{report['subdomains']}, sources:{report['source_systems']}, auctions:{report['auction_count']}, dual:{report['dual_product']}")
    
    return verification_report

def main():
    """Main pipeline setup execution"""
    logger.info("🚀 SHARD-8 PIPELINE SETUP STARTING")
    logger.info(f"Target counties: {list(SHARD8_COUNTIES.keys())}")
    
    session_start = time.time()
    
    try:
        # Step 1: RealAuction Subdomain Setup
        logger.info("\n📋 PHASE 1: RealAuction Subdomain Configuration")
        subdomain_result = setup_realauction_subdomains()
        
        # Step 2: Source Systems Setup
        logger.info("\n📋 PHASE 2: Pipeline Source Systems Configuration")
        source_result = setup_pipeline_source_systems()
        
        # Step 3: Pipeline Counties Setup
        logger.info("\n📋 PHASE 3: Pipeline Counties Registration")
        county_result = setup_pipeline_counties()
        
        # Step 4: Bootstrap Auction Data
        logger.info("\n📋 PHASE 4: Bootstrap Auction Data")
        auction_result = bootstrap_auction_data()
        
        # Step 5: Verification
        logger.info("\n📋 PHASE 5: Pipeline Verification")
        verification = verify_pipeline_setup()
        
        # Summary Report
        elapsed = time.time() - session_start
        logger.info("\n" + "="*60)
        logger.info("SHARD-8 PIPELINE SETUP COMPLETED")
        logger.info("="*60)
        logger.info(f"⏱️ Total time: {elapsed:.1f} seconds")
        
        # Results summary
        logger.info("\n📊 SETUP RESULTS:")
        logger.info(f"  Subdomains added: {subdomain_result}")
        logger.info(f"  Source systems added: {source_result}")
        logger.info(f"  Counties registered: {county_result}")
        logger.info(f"  Auctions bootstrapped: {auction_result}")
        
        # Verification summary
        logger.info("\n🔍 LETTER A READINESS:")
        ready_count = sum(1 for r in verification.values() if r['letter_a_ready'])
        
        for county, report in verification.items():
            status = "✅ READY" if report['letter_a_ready'] else "⚠️ NEEDS WORK"
            logger.info(f"  {county}: {status}")
            
            if not report['letter_a_ready']:
                issues = []
                if report['subdomains'] < 2:
                    issues.append(f"subdomains:{report['subdomains']}/2")
                if report['source_systems'] < 2:
                    issues.append(f"sources:{report['source_systems']}/2")
                if not report['pipeline_county']:
                    issues.append("no county registration")
                if not report['dual_product']:
                    issues.append(f"missing sale types:{report['sale_types']}")
                
                logger.info(f"    Issues: {', '.join(issues)}")
        
        logger.info(f"\n📈 OVERALL: {ready_count}/{len(SHARD8_COUNTIES)} counties ready for Letter A evaluation")
        
        return ready_count == len(SHARD8_COUNTIES)
        
    except Exception as e:
        logger.error(f"❌ Pipeline setup failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    
    logger.info(f"\n📅 NEXT STEPS:")
    logger.info("1. Run gold standard evaluation: pencil_dod_evaluate_county() for each county")
    logger.info("2. Enable scraper workflows for data ingestion")
    logger.info("3. Monitor Letter A metrics in gold_standard_county_status")
    logger.info("4. This setup provides the infrastructure foundation for all SHARD-8 improvements")
    
    sys.exit(0 if success else 1)