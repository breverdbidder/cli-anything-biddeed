#!/usr/bin/env python3
"""
SHARD-6 Verified Outcomes (B-lane) Implementation
Build independent data source scrapers for verified sale outcomes

Critical priority: B-lane failures across all counties
Need >=95% verified outcomes from INDEPENDENT sources (not PropertyOnion)
"""

import os
import sys
import json
import httpx
import logging
import asyncio
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
from bs4 import BeautifulSoup

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
    "Content-Type": "application/json"
}

# County clerk official records endpoints (independent sources)
CLERK_ENDPOINTS = {
    'escambia': {
        'type': 'clerk_official_records',
        'base_url': 'https://official-records.escambia-fl.com',
        'search_endpoint': '/search',
        'result_format': 'certificates_of_title'
    },
    'martin': {
        'type': 'clerk_official_records', 
        'base_url': 'https://or.martin.fl.us',
        'search_endpoint': '/search',
        'result_format': 'certificates_of_title'
    },
    'suwannee': {
        'type': 'realforeclose_results',
        'base_url': 'https://suwannee.realforeclose.com',
        'result_format': 'sale_results'
    },
    'calhoun': {
        'type': 'custom_clerk',
        'base_url': 'https://www.calhounclerk.com',
        'foreclosure_url': 'https://www.calhounclerk.com/foreclosure',
        'result_format': 'sale_results'
    },
    'liberty': {
        'type': 'custom_clerk',
        'base_url': 'https://www.libertyclerk.com',
        'foreclosure_url': 'https://www.libertyclerk.com/foreclosure',
        'result_format': 'sale_results'
    }
}

client = httpx.AsyncClient(timeout=60, follow_redirects=True)

async def get_pending_auctions(county: str, limit: int = 100) -> List[Dict]:
    """Get auctions that need verified outcomes"""
    
    params = {
        'county': f'eq.{county}',
        'sale_date': f'lt.{datetime.now().isoformat()}',  # Past sales only
        'select': 'id,case_number,address,sale_date,county,plaintiff,defendant',
        'limit': limit
    }
    
    try:
        response = await client.get(f"{BASE}/multi_county_auctions", headers=HEADERS, params=params)
        
        if response.status_code == 200:
            auctions = response.json()
            logger.info(f"Found {len(auctions)} past auctions in {county} needing verification")
            return auctions
        else:
            logger.error(f"Failed to get auctions for {county}: {response.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"Error getting auctions for {county}: {e}")
        return []

async def search_clerk_official_records(county: str, case_number: str) -> Optional[Dict]:
    """Search clerk official records for sale outcome"""
    
    config = CLERK_ENDPOINTS.get(county, {})
    if config.get('type') != 'clerk_official_records':
        return None
    
    base_url = config['base_url']
    
    try:
        # Search for Certificate of Title or Sale documents
        search_terms = [
            f"Certificate of Title {case_number}",
            f"Foreclosure Sale {case_number}", 
            case_number
        ]
        
        for term in search_terms:
            search_url = f"{base_url}{config['search_endpoint']}"
            
            # Try GET search first
            params = {
                'q': term,
                'type': 'certificate',
                'limit': 10
            }
            
            response = await client.get(search_url, params=params)
            
            if response.status_code == 200:
                # Parse search results
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Look for sale amount and buyer info
                sale_info = extract_sale_info_from_html(soup, case_number)
                if sale_info:
                    return {
                        'case_number': case_number,
                        'winning_bid': sale_info.get('amount'),
                        'buyer': sale_info.get('buyer'),
                        'sale_date': sale_info.get('sale_date'),
                        'data_source': f'clerk_official_records:{county.upper()}-CT-V1'
                    }
        
        return None
        
    except Exception as e:
        logger.error(f"Error searching clerk records for {county}/{case_number}: {e}")
        return None

def extract_sale_info_from_html(soup: BeautifulSoup, case_number: str) -> Optional[Dict]:
    """Extract sale information from clerk HTML"""
    
    try:
        # Common patterns for sale information
        amount_patterns = [
            r'\$[\d,]+\.?\d*',
            r'amount.*?(\d+[\d,]*\.?\d*)',
            r'consideration.*?(\d+[\d,]*\.?\d*)'
        ]
        
        text = soup.get_text()
        
        # Look for dollar amounts
        for pattern in amount_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                amount_str = matches[0].replace('$', '').replace(',', '')
                try:
                    amount = float(amount_str)
                    if amount > 100:  # Reasonable minimum bid
                        return {
                            'amount': amount,
                            'buyer': extract_buyer_from_text(text),
                            'sale_date': extract_date_from_text(text)
                        }
                except ValueError:
                    continue
        
        return None
        
    except Exception as e:
        logger.debug(f"Error extracting sale info: {e}")
        return None

def extract_buyer_from_text(text: str) -> Optional[str]:
    """Extract buyer name from document text"""
    
    # Common buyer indicators
    buyer_patterns = [
        r'grantee[:\s]+([^,\n]+)',
        r'purchaser[:\s]+([^,\n]+)', 
        r'buyer[:\s]+([^,\n]+)',
        r'sold to[:\s]+([^,\n]+)'
    ]
    
    for pattern in buyer_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    return None

def extract_date_from_text(text: str) -> Optional[str]:
    """Extract sale date from document text"""
    
    # Date patterns
    date_patterns = [
        r'(\d{1,2}/\d{1,2}/\d{4})',
        r'(\d{1,2}-\d{1,2}-\d{4})',
        r'([A-Za-z]+ \d{1,2}, \d{4})'
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    
    return None

async def scrape_realforeclose_results(county: str, case_number: str) -> Optional[Dict]:
    """Scrape sale results from RealForeclose site"""
    
    config = CLERK_ENDPOINTS.get(county, {})
    if config.get('type') != 'realforeclose_results':
        return None
    
    base_url = config['base_url']
    
    try:
        # Try to find the case in past sales
        results_url = f"{base_url}/results"
        
        response = await client.get(results_url)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for table rows with sale results
            rows = soup.find_all('tr')
            
            for row in rows:
                row_text = row.get_text()
                if case_number in row_text:
                    # Extract sale information from this row
                    cells = row.find_all(['td', 'th'])
                    
                    if len(cells) >= 4:  # Expect: case, address, amount, buyer
                        try:
                            amount_text = cells[2].get_text().strip()
                            amount = float(re.sub(r'[^0-9.]', '', amount_text))
                            
                            buyer = cells[3].get_text().strip() if len(cells) > 3 else 'Unknown'
                            
                            return {
                                'case_number': case_number,
                                'winning_bid': amount,
                                'buyer': buyer,
                                'data_source': f'realforeclose_results:{county.upper()}-RF-V1'
                            }
                        except (ValueError, IndexError):
                            continue
        
        return None
        
    except Exception as e:
        logger.error(f"Error scraping RealForeclose results for {county}/{case_number}: {e}")
        return None

async def store_verified_outcome(outcome: Dict) -> bool:
    """Store verified outcome in database"""
    
    # Determine which table to use based on case type
    case_number = outcome.get('case_number', '')
    
    if 'FC' in case_number.upper() or 'FORECLOSURE' in case_number.upper():
        table = 'foreclosure_outcomes'
    else:
        table = 'tax_deed_outcomes'
    
    try:
        response = await client.post(
            f"{BASE}/{table}",
            headers=HEADERS,
            json=outcome
        )
        
        if response.status_code in [200, 201]:
            logger.info(f"✅ Stored verified outcome for {case_number}")
            return True
        else:
            logger.error(f"❌ Failed to store outcome for {case_number}: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error storing outcome for {case_number}: {e}")
        return False

async def process_county_verified_outcomes(county: str, max_auctions: int = 100) -> Dict:
    """Process verified outcomes for a county"""
    logger.info(f"Starting verified outcomes scraping for {county}...")
    
    results = {
        'county': county,
        'processed': 0,
        'verified': 0,
        'failed': 0,
        'errors': []
    }
    
    # Get auctions needing verification
    auctions = await get_pending_auctions(county, max_auctions)
    if not auctions:
        logger.info(f"No auctions found for {county}")
        return results
    
    results['processed'] = len(auctions)
    
    # Process each auction
    for auction in auctions:
        case_number = auction.get('case_number', '')
        
        if not case_number:
            results['failed'] += 1
            continue
        
        # Try different verification methods
        outcome = None
        
        # 1. Try clerk official records
        outcome = await search_clerk_official_records(county, case_number)
        
        # 2. If that fails, try RealForeclose results
        if not outcome:
            outcome = await scrape_realforeclose_results(county, case_number)
        
        if outcome:
            # Store the verified outcome
            success = await store_verified_outcome(outcome)
            if success:
                results['verified'] += 1
            else:
                results['failed'] += 1
        else:
            results['failed'] += 1
        
        # Rate limiting
        await asyncio.sleep(0.5)
    
    logger.info(f"Completed {county}: {results['verified']} verified, {results['failed']} failed")
    return results

async def run_verified_outcomes_campaign():
    """Run verified outcomes campaign for SHARD-6 counties"""
    logger.info("Starting SHARD-6 verified outcomes campaign (B-lane)...")
    
    # All counties need B-lane fixes according to brief
    target_counties = ['escambia', 'martin', 'suwannee', 'calhoun', 'liberty']
    
    all_results = {}
    
    for county in target_counties:
        logger.info(f"\n{'='*50}")
        logger.info(f"Processing {county.upper()} - B-LANE VERIFIED OUTCOMES") 
        logger.info("="*50)
        
        results = await process_county_verified_outcomes(county)
        all_results[county] = results
        
        # Print results
        print(f"\n{county.upper()} B-Lane Results:")
        print(f"  Processed: {results['processed']}")
        print(f"  Verified: {results['verified']}")
        print(f"  Failed: {results['failed']}")
        
        if results['errors']:
            print(f"  Errors: {results['errors']}")
    
    return all_results

def main():
    """Main function"""
    logger.info("SHARD-6 Verified Outcomes (B-lane) Implementation")
    
    if len(sys.argv) > 1:
        county = sys.argv[1]
        # Process single county
        result = asyncio.run(process_county_verified_outcomes(county))
        print(json.dumps(result, indent=2))
    else:
        # Process all target counties  
        results = asyncio.run(run_verified_outcomes_campaign())
        print(f"\nB-Lane Campaign Complete!")
        print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()