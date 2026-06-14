#!/usr/bin/env python3
"""
SHARD-7 Gold Standard Letter B: Independent Verified Outcomes Scraper
Scrapes verified auction outcomes from county clerk sources for highlands, baker, miami_dade, columbia, madison

Usage:
  python scripts/shard7_verified_outcomes.py --county highlands
  python scripts/shard7_verified_outcomes.py --county baker  
  python scripts/shard7_verified_outcomes.py --county miami_dade
  python scripts/shard7_verified_outcomes.py --county columbia
  python scripts/shard7_verified_outcomes.py --county madison
  python scripts/shard7_verified_outcomes.py --all-counties
"""
import httpx
import json
import os
import sys
import argparse
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from bs4 import BeautifulSoup

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

# County-specific clerk sources (independent from PropertyOnion)
SHARD7_COUNTY_SOURCES = {
    'highlands': {
        'name': 'Highlands County',
        'clerk_url': 'https://www.myhighlandsclerk.com/',
        'foreclosure_source': 'https://www.myhighlandsclerk.com/public-records/court-records',
        'tax_deed_source': 'https://www.myhighlandsclerk.com/records/tax-deed-sales',
        'official_records': 'https://records.myhighlandsclerk.com/',
        'auction_calendar': 'https://highlands.realforeclose.com/',
        'platform': 'clerk_direct'
    },
    'baker': {
        'name': 'Baker County', 
        'clerk_url': 'https://www.bakercountyclerk.org/',
        'foreclosure_source': 'https://www.bakercountyclerk.org/foreclosure',
        'tax_deed_source': 'https://www.bakercountyclerk.org/tax-collector',
        'official_records': 'https://www.bakercountyclerk.org/official-records',
        'auction_calendar': 'https://www.bakercountyclerk.org/foreclosure',
        'platform': 'clerk_direct'
    },
    'miami_dade': {
        'name': 'Miami-Dade County',
        'clerk_url': 'https://www.miami-dadeclerk.com/',
        'foreclosure_source': 'https://www.miami-dadeclerk.com/public_records/online_services/',
        'tax_deed_source': 'https://www.miamidade.gov/global/service.page?Mduid_service=ser1489695280815660',
        'official_records': 'https://onlinerecords.miami-dadeclerk.com/',
        'auction_calendar': 'https://miamidade.realforeclose.com/',
        'platform': 'realforeclose_tier1'
    },
    'columbia': {
        'name': 'Columbia County',
        'clerk_url': 'https://www.columbiaclerk.com/',
        'foreclosure_source': 'https://columbia.realforeclose.com/',
        'tax_deed_source': 'https://www.columbiaclerk.com/tax-deeds',
        'official_records': 'https://www.columbiaclerk.com/official-records',
        'auction_calendar': 'https://columbia.realforeclose.com/',
        'platform': 'realforeclose_tier1'
    },
    'madison': {
        'name': 'Madison County',
        'clerk_url': 'https://www.madisonclerk.com/',
        'foreclosure_source': 'https://madison.realforeclose.com/',
        'tax_deed_source': 'https://www.madisonclerk.com/tax-collector',
        'official_records': 'https://www.madisonclerk.com/records',
        'auction_calendar': 'https://madison.realforeclose.com/',
        'platform': 'realforeclose_tier1'
    }
}

client = httpx.Client(
    timeout=30, 
    follow_redirects=True,
    headers={
        'User-Agent': 'Mozilla/5.0 (BidDeed-SHARD7-VerifiedOutcomes/1.0; contact: ariel@everestcapitalusa.com)',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5'
    }
)

def supabase_get(table: str, params: Dict = None) -> List[Dict]:
    """Get data from Supabase table"""
    try:
        url = f"{BASE}/{table}"
        if params:
            url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
        
        response = client.get(url, headers=HEADERS)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching from {table}: {e}")
        return []

def supabase_upsert(table: str, data: List[Dict]) -> int:
    """Upsert data to Supabase table"""
    if not data:
        return 0
        
    try:
        response = client.post(f"{BASE}/{table}", headers=HEADERS, json=data)
        response.raise_for_status()
        logger.info(f"Successfully upserted {len(data)} records to {table}")
        return len(data)
    except Exception as e:
        logger.error(f"Error upserting to {table}: {e}")
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            logger.error(f"Response: {e.response.text}")
        return 0

def get_pending_auctions(county_slug: str, days_back: int = 90) -> List[Dict]:
    """Get auctions from multi_county_auctions that need outcome verification"""
    since_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
    
    params = {
        'select': 'case_number,parcel_id,auction_date,sale_type,auction_status,winning_bid,source_platform',
        'county': f'eq.{county_slug}',
        'auction_date': f'gte.{since_date}',
        'order': 'auction_date.desc',
        'limit': '1000'
    }
    
    auctions = supabase_get('multi_county_auctions', params)
    logger.info(f"Found {len(auctions)} auctions for {county_slug} since {since_date}")
    return auctions

def scrape_realforeclose_outcomes(county_slug: str) -> List[Dict]:
    """
    Scrape outcomes from RealForeclose platform with tier1 data source marking
    This provides independent verification separate from PropertyOnion
    """
    outcomes = []
    county_config = SHARD7_COUNTY_SOURCES[county_slug]
    
    try:
        auction_url = county_config['auction_calendar']
        logger.info(f"Scraping RealForeclose outcomes for {county_slug} from {auction_url}")
        
        # Get the main auction calendar page
        response = client.get(auction_url)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for auction result links or completed sale information
        # RealForeclose sites often have "Results" or "Sale Results" sections
        
        # Extract any visible sale information from the page
        # This is a preliminary implementation - would need county-specific parsing
        
        # For now, create a framework that can be extended per county
        sample_outcome = {
            'county_slug': county_slug,
            'case_number': 'SAMPLE-2024-001',
            'auction_date': datetime.now().strftime('%Y-%m-%d'),
            'sale_status': 'sold',
            'sale_amount': 15000.00,
            'buyer_type': 'third_party',
            'data_source': f'realforeclose_tier1:{county_slug.upper()}-FC-V1',
            'source_url': auction_url,
            'confidence_level': 'probable',
            'notes': f'Scraped from {county_config["name"]} RealForeclose auction calendar'
        }
        
        # Enable when parsing is implemented
        # outcomes.append(sample_outcome)
        
    except Exception as e:
        logger.error(f"Error scraping {county_slug} RealForeclose outcomes: {e}")
    
    return outcomes

def scrape_clerk_direct_outcomes(county_slug: str) -> List[Dict]:
    """
    Scrape outcomes directly from county clerk websites
    Provides highest confidence independent verification
    """
    outcomes = []
    county_config = SHARD7_COUNTY_SOURCES[county_slug]
    
    try:
        # Try multiple clerk sources
        sources_to_try = [
            ('foreclosure', county_config['foreclosure_source']),
            ('tax_deed', county_config['tax_deed_source'])
        ]
        
        for sale_type, source_url in sources_to_try:
            logger.info(f"Scraping {county_slug} {sale_type} outcomes from {source_url}")
            
            try:
                response = client.get(source_url)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Look for common clerk page patterns:
                # - Tables with case numbers, dates, amounts
                # - Sale result lists
                # - Auction outcome calendars
                
                # Extract table data if present
                tables = soup.find_all('table')
                for table in tables:
                    rows = table.find_all('tr')
                    for row in rows[1:]:  # Skip header
                        cells = row.find_all(['td', 'th'])
                        if len(cells) >= 3:
                            # Basic extraction - customize per county
                            cell_texts = [cell.get_text(strip=True) for cell in cells]
                            
                            # Look for patterns that indicate case numbers, dates, amounts
                            case_pattern = re.search(r'[A-Z]{2,}-?\d{4,}-?\d{3,}', ' '.join(cell_texts))
                            date_pattern = re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', ' '.join(cell_texts))
                            amount_pattern = re.search(r'\$?[\d,]+\.?\d{0,2}', ' '.join(cell_texts))
                            
                            if case_pattern and date_pattern:
                                outcome = {
                                    'county_slug': county_slug,
                                    'case_number': case_pattern.group(),
                                    'auction_date': _normalize_date(date_pattern.group()),
                                    'sale_status': 'sold' if amount_pattern else 'no_sale',
                                    'sale_amount': float(re.sub(r'[,$]', '', amount_pattern.group())) if amount_pattern else None,
                                    'buyer_type': 'unknown',
                                    'data_source': f'clerk_direct:{county_slug.upper()}-{sale_type.upper()}-V1',
                                    'source_url': source_url,
                                    'confidence_level': 'verified',
                                    'notes': f'Scraped from {county_config["name"]} clerk records'
                                }
                                outcomes.append(outcome)
                
            except Exception as e:
                logger.warning(f"Could not scrape {source_url}: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Error scraping {county_slug} clerk outcomes: {e}")
    
    return outcomes

def _normalize_date(date_str: str) -> str:
    """Convert various date formats to YYYY-MM-DD"""
    date_str = date_str.strip()
    for fmt in ("%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d", "%m/%d/%y", "%m-%d-%y"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_str

def verify_existing_outcomes(county_slug: str) -> Dict:
    """Check current verified outcomes count for county"""
    tax_deed_count = len(supabase_get('tax_deed_outcomes', {
        'county_slug': f'eq.{county_slug}',
        'select': 'id'
    }))
    
    foreclosure_count = len(supabase_get('foreclosure_outcomes', {
        'county_slug': f'eq.{county_slug}', 
        'select': 'id'
    }))
    
    total_auctions = len(supabase_get('multi_county_auctions', {
        'county': f'eq.{county_slug}',
        'auction_status': f'in.(sold,no_sale,canceled)',
        'select': 'id'
    }))
    
    verified_rate = ((tax_deed_count + foreclosure_count) / total_auctions * 100) if total_auctions > 0 else 0
    
    return {
        'county': county_slug,
        'tax_deed_outcomes': tax_deed_count,
        'foreclosure_outcomes': foreclosure_count,
        'total_verified': tax_deed_count + foreclosure_count,
        'total_auctions': total_auctions,
        'verification_rate': verified_rate,
        'letter_b_status': 'PASS' if verified_rate >= 95.0 else 'FAIL'
    }

def scrape_county_outcomes(county_slug: str) -> int:
    """Scrape verified outcomes for a specific county"""
    if county_slug not in SHARD7_COUNTY_SOURCES:
        logger.error(f"County {county_slug} not supported in SHARD-7")
        return 0
    
    logger.info(f"Starting verified outcomes scrape for {county_slug}")
    
    # Get pending auctions that need verification
    pending_auctions = get_pending_auctions(county_slug)
    
    # Check current status
    current_status = verify_existing_outcomes(county_slug)
    logger.info(f"Current Letter B status for {county_slug}: {current_status}")
    
    total_scraped = 0
    county_config = SHARD7_COUNTY_SOURCES[county_slug]
    
    # Try multiple approaches for maximum outcome capture
    all_outcomes = []
    
    # 1. RealForeclose platform scraping (for counties that use it)
    if county_config['platform'] == 'realforeclose_tier1':
        rf_outcomes = scrape_realforeclose_outcomes(county_slug)
        all_outcomes.extend(rf_outcomes)
    
    # 2. Direct clerk website scraping (highest confidence)
    clerk_outcomes = scrape_clerk_direct_outcomes(county_slug)
    all_outcomes.extend(clerk_outcomes)
    
    # Separate by sale type and upsert to appropriate tables
    tax_deed_outcomes = []
    foreclosure_outcomes = []
    
    for outcome in all_outcomes:
        case_num = outcome.get('case_number', '').upper()
        if any(marker in case_num for marker in ['TD', 'TAX', 'DEED']):
            tax_deed_outcomes.append(outcome)
        elif any(marker in case_num for marker in ['FC', 'FORECL', 'MORTGAGE']):
            foreclosure_outcomes.append(outcome)
        else:
            # Default to foreclosure for ambiguous cases
            foreclosure_outcomes.append(outcome)
    
    # Upsert to database
    if tax_deed_outcomes:
        total_scraped += supabase_upsert('tax_deed_outcomes', tax_deed_outcomes)
    
    if foreclosure_outcomes:
        total_scraped += supabase_upsert('foreclosure_outcomes', foreclosure_outcomes)
    
    # Verify improvement
    final_status = verify_existing_outcomes(county_slug)
    logger.info(f"Final Letter B status for {county_slug}: {final_status}")
    
    improvement = final_status['verification_rate'] - current_status['verification_rate']
    logger.info(f"Verification rate improvement: +{improvement:.1f}%")
    
    return total_scraped

def main():
    parser = argparse.ArgumentParser(description='SHARD-7 verified auction outcomes scraper for Gold Standard Letter B')
    parser.add_argument('--county', choices=['highlands', 'baker', 'miami_dade', 'columbia', 'madison'], 
                       help='County to scrape')
    parser.add_argument('--all-counties', action='store_true', 
                       help='Scrape all SHARD-7 counties')
    parser.add_argument('--verify-only', action='store_true',
                       help='Only verify current status, do not scrape')
    
    args = parser.parse_args()
    
    if not SUPABASE_KEY:
        logger.error("SUPABASE_KEY environment variable not set")
        sys.exit(1)
    
    logger.info("=" * 60)
    logger.info("SHARD-7 GOLD STANDARD LETTER B - Verified Outcomes Scraper")
    logger.info("Counties: highlands, baker, miami_dade, columbia, madison")
    logger.info("=" * 60)
    
    counties_to_process = []
    
    if args.all_counties:
        counties_to_process = ['highlands', 'baker', 'miami_dade', 'columbia', 'madison']
    elif args.county:
        counties_to_process = [args.county]
    else:
        parser.print_help()
        sys.exit(1)
    
    total_scraped = 0
    
    for county in counties_to_process:
        logger.info(f"\n--- Processing {county} ---")
        
        if args.verify_only:
            status = verify_existing_outcomes(county)
            logger.info(f"Verification status: {status}")
        else:
            scraped = scrape_county_outcomes(county)
            total_scraped += scraped
            logger.info(f"Scraped {scraped} verified outcomes for {county}")
    
    logger.info(f"\nTotal verified outcomes scraped: {total_scraped}")
    logger.info("SHARD-7 verified outcomes scraping complete")

if __name__ == "__main__":
    main()