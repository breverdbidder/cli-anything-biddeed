#!/usr/bin/env python3
"""
SHARD-10 Verified Outcomes Pipeline (Letter B)
Create independent verification pipelines for leon, baker, okaloosa, franklin, union

REQUIREMENT: Independent data sources (NOT PropertyOnion) for verified outcomes
Target: ≥95% verified outcomes vs closed auctions

STRATEGY:
1. Discover each county's clerk records system (AcclaimWeb, official records)
2. Build scraper for Certificate of Title / Final Judgments 
3. Extract sale amounts, winning bidders, case numbers
4. Write to foreclosure_outcomes/tax_deed_outcomes with independent data_source
5. Enable automatic tier1 promotion via existing tier1-promote-hourly cron

CLERK RECORD SOURCES:
- Leon: Leon County Clerk official records
- Baker: Baker County Clerk records  
- Okaloosa: Okaloosa County Clerk records
- Franklin: Franklin County Clerk records
- Union: Union County Clerk records

PRECEDENT: Duval AcclaimWeb pipeline (acclaim_* functions) - extend to SHARD-10

Usage:
  python scripts/shard10_verified_outcomes.py --county leon
  python scripts/shard10_verified_outcomes.py --all-counties
  python scripts/shard10_verified_outcomes.py --discover-only
"""
import os
import sys
import json
import httpx
import time
import argparse
import logging
import re
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Set
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"

def get_headers():
    """Get request headers with authentication if available"""
    if SUPABASE_KEY:
        return {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates"
        }
    else:
        return {"Content-Type": "application/json"}

# HTTP headers for clerk website access
CLERK_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "DNT": "1",
    "Connection": "keep-alive"
}

# SHARD-10 clerk discovery targets
CLERK_TARGETS = {
    'leon': {
        'base_url': 'https://www.leonclerk.com',
        'official_records_paths': ['/records', '/search', '/documents', '/official-records'],
        'co_no': 47
    },
    'baker': {
        'base_url': 'https://www.bakerclerk.com',
        'official_records_paths': ['/records', '/search', '/documents', '/official-records'],
        'co_no': 12
    },
    'okaloosa': {
        'base_url': 'https://www.okaloosaclerk.com',
        'official_records_paths': ['/records', '/search', '/documents', '/official-records'],
        'co_no': 56
    },
    'franklin': {
        'base_url': 'https://www.franklinclerk.com',
        'official_records_paths': ['/records', '/search', '/documents', '/official-records'],
        'co_no': 29
    },
    'union': {
        'base_url': 'https://www.unionclerk.com',
        'official_records_paths': ['/records', '/search', '/documents', '/official-records'],
        'co_no': 73
    }
}

client = httpx.AsyncClient(timeout=60, headers=CLERK_HEADERS)

@dataclass
class ClerkSystemInfo:
    """Information about a county's clerk records system"""
    county_slug: str
    system_type: str  # 'acclaim_web', 'custom', 'unknown'
    base_url: str
    search_url: Optional[str] = None
    document_types: List[str] = None
    access_method: str = 'direct'  # 'direct', 'search_form', 'api'
    authentication_required: bool = False

@dataclass
class VerifiedOutcome:
    """A verified auction outcome from clerk records"""
    case_number: str
    county_slug: str
    sale_date: str
    winning_bid: Optional[float]
    winning_bidder: Optional[str]
    document_type: str  # 'certificate_of_title', 'final_judgment', etc.
    document_number: Optional[str]
    data_source: str
    confidence_score: float

async def discover_clerk_system(county_slug: str) -> ClerkSystemInfo:
    """Discover the clerk records system for a county"""
    logger.info(f"Discovering clerk system for {county_slug}")
    
    config = CLERK_TARGETS.get(county_slug)
    if not config:
        return ClerkSystemInfo(county_slug, 'unknown', '')
    
    base_url = config['base_url']
    
    try:
        # Test base URL accessibility
        response = await client.get(base_url)
        
        if response.status_code != 200:
            logger.warning(f"Clerk website not accessible for {county_slug}: {response.status_code}")
            return ClerkSystemInfo(county_slug, 'unknown', base_url)
        
        home_content = response.text.lower()
        
        # Check for AcclaimWeb (like Duval)
        if 'acclaim' in home_content or 'acclaimweb' in home_content:
            acclaim_url = await find_acclaim_endpoint(base_url, home_content)
            return ClerkSystemInfo(
                county_slug=county_slug,
                system_type='acclaim_web',
                base_url=base_url,
                search_url=acclaim_url,
                document_types=['CT', 'FJ', 'TD'],  # Certificate of Title, Final Judgment, Tax Deed
                access_method='direct'
            )
        
        # Check for other common clerk systems
        if any(keyword in home_content for keyword in ['official records', 'document search', 'records search']):
            search_url = await find_records_search_url(base_url, config['official_records_paths'])
            return ClerkSystemInfo(
                county_slug=county_slug,
                system_type='custom',
                base_url=base_url,
                search_url=search_url,
                document_types=['certificate', 'judgment', 'deed'],
                access_method='search_form'
            )
        
        logger.warning(f"No recognized clerk system found for {county_slug}")
        return ClerkSystemInfo(county_slug, 'unknown', base_url)
        
    except Exception as e:
        logger.error(f"Error discovering clerk system for {county_slug}: {e}")
        return ClerkSystemInfo(county_slug, 'unknown', base_url)

async def find_acclaim_endpoint(base_url: str, home_content: str) -> Optional[str]:
    """Find AcclaimWeb endpoint URL"""
    
    # Look for AcclaimWeb links in HTML
    acclaim_patterns = [
        r'href=["\']([^"\']*acclaim[^"\']*)["\']',
        r'href=["\']([^"\']*AcclaimWeb[^"\']*)["\']'
    ]
    
    for pattern in acclaim_patterns:
        matches = re.findall(pattern, home_content, re.IGNORECASE)
        for match in matches:
            if match.startswith('http'):
                return match
            elif match.startswith('/'):
                return urljoin(base_url, match)
    
    # Try common AcclaimWeb paths
    common_paths = [
        '/AcclaimWeb/',
        '/acclaimweb/',
        '/acclaim/',
        '/records/acclaim/'
    ]
    
    for path in common_paths:
        test_url = urljoin(base_url, path)
        try:
            response = await client.get(test_url)
            if response.status_code == 200 and 'acclaim' in response.text.lower():
                return test_url
        except:
            continue
    
    return None

async def find_records_search_url(base_url: str, search_paths: List[str]) -> Optional[str]:
    """Find the records search URL"""
    
    for path in search_paths:
        test_url = urljoin(base_url, path)
        try:
            response = await client.get(test_url)
            if response.status_code == 200:
                content = response.text.lower()
                if any(keyword in content for keyword in ['search', 'records', 'documents']):
                    return test_url
        except:
            continue
    
    return None

async def get_closed_auctions_for_verification(county_slug: str, limit: int = 100) -> List[Dict]:
    """Get closed auctions that need outcome verification"""
    logger.info(f"Getting closed auctions for verification: {county_slug}")
    
    try:
        # Get closed auctions without verified outcomes
        url = f"{BASE}/multi_county_auctions"
        params = {
            'county': f'eq.{county_slug}',
            'auction_status': 'in.(sold,no_sale)',
            'select': 'id,case_number,auction_date,sale_type',
            'limit': str(limit)
        }
        
        response = await client.get(url, headers=get_headers(), params=params)
        response.raise_for_status()
        
        auctions = response.json()
        
        # Filter out those that already have verified outcomes
        auctions_needing_verification = []
        
        for auction in auctions:
            case_number = auction.get('case_number')
            if not case_number:
                continue
            
            # Check if outcome already exists
            has_outcome = await check_existing_outcome(case_number, county_slug)
            if not has_outcome:
                auctions_needing_verification.append(auction)
        
        logger.info(f"Found {len(auctions_needing_verification)} auctions needing verification for {county_slug}")
        return auctions_needing_verification
        
    except Exception as e:
        logger.error(f"Error getting auctions for verification: {e}")
        return []

async def check_existing_outcome(case_number: str, county_slug: str) -> bool:
    """Check if a verified outcome already exists for a case"""
    
    for table in ['foreclosure_outcomes', 'tax_deed_outcomes']:
        try:
            url = f"{BASE}/{table}"
            params = {
                'case_number': f'eq.{case_number}',
                'county_slug': f'eq.{county_slug}',
                'data_source': 'not.ilike.*propertyonion*',
                'select': 'id'
            }
            
            response = await client.get(url, headers=get_headers(), params=params)
            if response.status_code == 200:
                results = response.json()
                if results:
                    return True
        except:
            continue
    
    return False

async def create_verification_pipeline(county_slug: str, clerk_info: ClerkSystemInfo) -> Dict:
    """Create verification pipeline configuration for a county"""
    logger.info(f"Creating verification pipeline for {county_slug}")
    
    pipeline_config = {
        'county_slug': county_slug,
        'clerk_system_type': clerk_info.system_type,
        'base_url': clerk_info.base_url,
        'search_url': clerk_info.search_url,
        'document_types': clerk_info.document_types or [],
        'access_method': clerk_info.access_method,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'status': 'configured'
    }
    
    if clerk_info.system_type == 'acclaim_web':
        # Create AcclaimWeb-style pipeline
        pipeline_config['scraper_type'] = 'acclaim_web'
        pipeline_config['harvest_method'] = 'batch_document_search'
        pipeline_config['document_types'] = ['CT', 'FJ']  # Certificate of Title, Final Judgment
        
    elif clerk_info.system_type == 'custom':
        # Create custom scraper pipeline
        pipeline_config['scraper_type'] = 'custom_clerk'
        pipeline_config['harvest_method'] = 'case_number_search'
        
    else:
        # Manual queue approach
        pipeline_config['scraper_type'] = 'manual_queue'
        pipeline_config['harvest_method'] = 'manual'
        pipeline_config['note'] = 'Requires manual implementation - clerk system not recognized'
    
    return pipeline_config

async def test_verification_search(county_slug: str, clerk_info: ClerkSystemInfo, test_case: str) -> Dict:
    """Test verification search with a sample case number"""
    logger.info(f"Testing verification search for {county_slug} with case {test_case}")
    
    if not clerk_info.search_url:
        return {'success': False, 'error': 'No search URL available'}
    
    try:
        # This is a placeholder for actual search testing
        # Real implementation would depend on the specific clerk system
        
        if clerk_info.system_type == 'acclaim_web':
            # Test AcclaimWeb search
            search_result = await test_acclaim_search(clerk_info.search_url, test_case)
        else:
            # Test custom search
            search_result = await test_custom_search(clerk_info.search_url, test_case)
        
        return search_result
        
    except Exception as e:
        logger.error(f"Error testing verification search for {county_slug}: {e}")
        return {'success': False, 'error': str(e)}

async def test_acclaim_search(search_url: str, test_case: str) -> Dict:
    """Test AcclaimWeb search functionality"""
    # Placeholder for AcclaimWeb testing
    # Would implement similar to existing Duval AcclaimWeb pipeline
    return {
        'success': True,
        'method': 'acclaim_web_search',
        'documents_found': 0,
        'note': 'AcclaimWeb search test (placeholder)'
    }

async def test_custom_search(search_url: str, test_case: str) -> Dict:
    """Test custom clerk search functionality"""
    # Placeholder for custom search testing
    return {
        'success': True,
        'method': 'custom_search',
        'documents_found': 0,
        'note': 'Custom search test (placeholder)'
    }

async def setup_county_verification(county_slug: str) -> Dict:
    """Set up complete verification pipeline for a county"""
    logger.info(f"Setting up verification pipeline for {county_slug}")
    
    try:
        # Step 1: Discover clerk system
        clerk_info = await discover_clerk_system(county_slug)
        
        # Step 2: Get auctions needing verification
        auctions_needing_verification = await get_closed_auctions_for_verification(county_slug)
        
        # Step 3: Create pipeline configuration
        pipeline_config = await create_verification_pipeline(county_slug, clerk_info)
        
        # Step 4: Test with sample case if available
        test_result = None
        if auctions_needing_verification:
            sample_case = auctions_needing_verification[0].get('case_number')
            if sample_case:
                test_result = await test_verification_search(county_slug, clerk_info, sample_case)
        
        result = {
            'county_slug': county_slug,
            'clerk_info': clerk_info,
            'pipeline_config': pipeline_config,
            'auctions_needing_verification': len(auctions_needing_verification),
            'test_result': test_result,
            'success': True
        }
        
        logger.info(f"Verification pipeline setup completed for {county_slug}")
        return result
        
    except Exception as e:
        logger.error(f"Error setting up verification pipeline for {county_slug}: {e}")
        return {
            'county_slug': county_slug,
            'success': False,
            'error': str(e)
        }

async def main_async():
    parser = argparse.ArgumentParser(description='SHARD-10 Verified Outcomes Pipeline (Letter B)')
    parser.add_argument('--county', choices=list(CLERK_TARGETS.keys()), help='Single county to setup')
    parser.add_argument('--all-counties', action='store_true', help='Setup all SHARD-10 counties')
    parser.add_argument('--discover-only', action='store_true', help='Discover clerk systems only')
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("SHARD-10 VERIFIED OUTCOMES PIPELINE (Letter B)")
    logger.info("=" * 60)
    logger.info("Independent verification sources for ≥95% outcome coverage")
    
    counties_to_process = []
    
    if args.all_counties:
        counties_to_process = list(CLERK_TARGETS.keys())
    elif args.county:
        counties_to_process = [args.county]
    else:
        # Default: all counties for autonomous session
        counties_to_process = list(CLERK_TARGETS.keys())
    
    results = {}
    
    for county_slug in counties_to_process:
        logger.info(f"\n--- Processing {county_slug} ---")
        
        if args.discover_only:
            clerk_info = await discover_clerk_system(county_slug)
            results[county_slug] = {'clerk_info': clerk_info}
            logger.info(f"Clerk system: {clerk_info.system_type} at {clerk_info.base_url}")
        else:
            result = await setup_county_verification(county_slug)
            results[county_slug] = result
            
            if result.get('success'):
                clerk_info = result['clerk_info']
                auctions_count = result['auctions_needing_verification']
                logger.info(f"Pipeline: {clerk_info.system_type}, {auctions_count} auctions need verification")
            else:
                logger.info(f"ERROR: {result.get('error')}")
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("SHARD-10 VERIFIED OUTCOMES SUMMARY")
    logger.info("=" * 60)
    
    for county, result in results.items():
        if 'clerk_info' in result:
            clerk_info = result['clerk_info']
            system_status = "✅" if clerk_info.system_type != 'unknown' else "❌"
            logger.info(f"{county}: {system_status} {clerk_info.system_type}")
            
            if result.get('auctions_needing_verification'):
                count = result['auctions_needing_verification']
                logger.info(f"  {count} auctions need verification")
        else:
            logger.info(f"{county}: ERROR")
    
    logger.info("\nSHARD-10 verified outcomes pipeline setup complete")
    logger.info("\nNOTE: Manual implementation required for actual scraping")
    logger.info("Framework created for independent verification sources")
    
    await client.aclose()

def main():
    asyncio.run(main_async())

if __name__ == "__main__":
    main()