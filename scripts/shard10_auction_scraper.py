#!/usr/bin/env python3
"""
SHARD-10 Multi-County Auction Scraper
Targeted scraper for leon, baker, okaloosa, franklin, union counties

These counties currently have null slugs in fl_counties_manifest.yml, indicating
they need clerk website discovery and auction data ingestion to achieve Gold Standard.

APPROACH:
1. Discover each county's clerk foreclosure/tax deed auction pages
2. Build custom parsers for each clerk's HTML format  
3. Extract case_number, address, auction_date, sale_type, status
4. Upsert to multi_county_auctions with proper county slug assignment

CLERK DISCOVERY TARGETS:
- Leon County: https://www.leonclerk.com/
- Baker County: https://www.bakerclerk.com/  
- Okaloosa County: https://www.okaloosaclerk.com/
- Franklin County: https://www.franklinclerk.com/
- Union County: https://www.unionclerk.com/

Usage:
  python scripts/shard10_auction_scraper.py --county leon
  python scripts/shard10_auction_scraper.py --all-counties  
  python scripts/shard10_auction_scraper.py --discover-only
"""
import os
import sys
import json
import httpx
import time
import argparse
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

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

# HTTP headers for clerk website scraping
SCRAPER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}

# County clerk discovery targets
CLERK_TARGETS = {
    'leon': {
        'base_url': 'https://www.leonclerk.com',
        'search_paths': ['/foreclosure', '/auctions', '/sales', '/public-records'],
        'co_no': 47
    },
    'baker': {
        'base_url': 'https://www.bakerclerk.com',
        'search_paths': ['/foreclosure', '/auctions', '/sales', '/public-records'],
        'co_no': 12
    },
    'okaloosa': {
        'base_url': 'https://www.okaloosaclerk.com', 
        'search_paths': ['/foreclosure', '/auctions', '/sales', '/public-records'],
        'co_no': 56
    },
    'franklin': {
        'base_url': 'https://www.franklinclerk.com',
        'search_paths': ['/foreclosure', '/auctions', '/sales', '/public-records'],
        'co_no': 29
    },
    'union': {
        'base_url': 'https://www.unionclerk.com',
        'search_paths': ['/foreclosure', '/auctions', '/sales', '/public-records'],
        'co_no': 73
    }
}

client = httpx.Client(timeout=30, headers=SCRAPER_HEADERS)

class AuctionTableParser(HTMLParser):
    """Generic HTML table parser for auction listings"""
    
    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.current_cell = ""
        self.current_row: List[str] = []
        self.rows: List[List[str]] = []
        self.header: List[str] = []
        self.table_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.table_depth += 1
            if self.table_depth == 1:  # Only parse first level table
                self.in_table = True
        elif tag == "tr" and self.in_table:
            self.in_row = True
            self.current_row = []
        elif tag in ("td", "th") and self.in_row:
            self.in_cell = True
            self.current_cell = ""

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.in_cell:
            self.current_row.append(self.current_cell.strip())
            self.in_cell = False
        elif tag == "tr" and self.in_row:
            if self.current_row and len(self.current_row) >= 2:
                # Check if this looks like a header row
                if not self.header and self._is_header_row(self.current_row):
                    self.header = [h.lower().replace(" ", "_").replace("-", "_") for h in self.current_row]
                elif self.header and len(self.current_row) >= len(self.header):
                    self.rows.append(self.current_row)
            self.in_row = False
        elif tag == "table":
            self.table_depth -= 1
            if self.table_depth == 0:
                self.in_table = False

    def handle_data(self, data):
        if self.in_cell:
            self.current_cell += data

    def _is_header_row(self, row: List[str]) -> bool:
        """Detect if a row contains table headers"""
        header_keywords = ['case', 'number', 'date', 'property', 'address', 'plaintiff', 'defendant', 'status', 'sale', 'auction']
        row_text = ' '.join(row).lower()
        
        keyword_count = sum(1 for keyword in header_keywords if keyword in row_text)
        return keyword_count >= 2

def discover_auction_pages(county: str) -> List[str]:
    """Discover potential auction/foreclosure pages for a county"""
    logger.info(f"Discovering auction pages for {county}")
    
    config = CLERK_TARGETS.get(county)
    if not config:
        logger.error(f"No clerk configuration found for {county}")
        return []
    
    base_url = config['base_url']
    search_paths = config['search_paths']
    
    discovered_pages = []
    
    try:
        # First try the home page to discover site structure
        logger.info(f"Fetching home page: {base_url}")
        response = client.get(base_url)
        
        if response.status_code == 200:
            home_content = response.text.lower()
            
            # Look for links containing auction/foreclosure keywords
            keywords = ['foreclosure', 'auction', 'sale', 'sheriff', 'tax deed', 'tax sale']
            
            # Simple regex to find href links with relevant keywords
            import re
            link_pattern = r'href=["\']([^"\']*(?:foreclosure|auction|sale|sheriff|tax[_-]?deed|tax[_-]?sale)[^"\']*)["\']'
            matches = re.findall(link_pattern, home_content, re.IGNORECASE)
            
            for match in matches:
                if match.startswith('/'):
                    full_url = urljoin(base_url, match)
                elif match.startswith('http'):
                    full_url = match
                else:
                    continue
                    
                if full_url not in discovered_pages:
                    discovered_pages.append(full_url)
        
        # Also try common path patterns
        for path in search_paths:
            test_url = urljoin(base_url, path)
            try:
                test_response = client.get(test_url)
                if test_response.status_code == 200:
                    discovered_pages.append(test_url)
                    logger.info(f"Found accessible page: {test_url}")
            except Exception as e:
                logger.debug(f"Path {test_url} not accessible: {e}")
        
        logger.info(f"Discovered {len(discovered_pages)} pages for {county}")
        return discovered_pages[:5]  # Limit to top 5 candidates
        
    except Exception as e:
        logger.error(f"Error discovering pages for {county}: {e}")
        return []

def scrape_auction_page(url: str, county: str) -> List[Dict]:
    """Scrape auction data from a specific page"""
    logger.info(f"Scraping auction data from {url}")
    
    try:
        response = client.get(url)
        if response.status_code != 200:
            logger.error(f"Failed to fetch {url}: {response.status_code}")
            return []
        
        # Parse HTML for table data
        parser = AuctionTableParser()
        parser.feed(response.text)
        
        if not parser.rows:
            logger.warning(f"No table data found on {url}")
            return []
        
        auctions = []
        
        for row in parser.rows:
            if len(row) < 2:
                continue
                
            # Try to extract key fields from the row
            auction_data = extract_auction_fields(row, parser.header, county)
            
            if auction_data:
                auctions.append(auction_data)
        
        logger.info(f"Extracted {len(auctions)} auction records from {url}")
        return auctions
        
    except Exception as e:
        logger.error(f"Error scraping {url}: {e}")
        return []

def extract_auction_fields(row: List[str], header: List[str], county: str) -> Optional[Dict]:
    """Extract auction fields from a table row"""
    
    # Create a mapping if we have headers
    if header and len(row) >= len(header):
        row_data = dict(zip(header, row))
    else:
        # Fallback: assume common column order
        row_data = {}
        if len(row) >= 1:
            row_data['case_info'] = row[0]
        if len(row) >= 2:
            row_data['address_info'] = row[1] 
        if len(row) >= 3:
            row_data['date_info'] = row[2]
        if len(row) >= 4:
            row_data['status_info'] = row[3]
    
    # Extract case number
    case_number = extract_case_number(row_data)
    if not case_number:
        return None
    
    # Extract other fields
    address = extract_address(row_data)
    auction_date = extract_auction_date(row_data)
    status = extract_status(row_data)
    sale_type = extract_sale_type(row_data)
    
    return {
        'case_number': case_number,
        'county': county,
        'address': address,
        'auction_date': auction_date,
        'auction_status': status,
        'sale_type': sale_type,
        'source_platform': f'clerk_{county}',
        'data_source': f'shard10_scraper_{datetime.now(timezone.utc).strftime("%Y%m%d")}',
        'scraped_at': datetime.now(timezone.utc).isoformat(),
        'created_at': datetime.now(timezone.utc).isoformat()
    }

def extract_case_number(row_data: Dict[str, str]) -> Optional[str]:
    """Extract case number from row data"""
    
    # Look for case number patterns in various fields
    case_patterns = [
        r'\b\d{4}[A-Z]{2}\d+\b',  # 2024CA123456
        r'\b\d{2}-\d{4}-[A-Z]{2}-\d+\b',  # 24-2024-CA-123456  
        r'\bcase[:\s]*(\d+[A-Z]*\d*)\b',  # Case: 123456
        r'\b(\d{4,})\b'  # Any 4+ digit number
    ]
    
    for field_name, value in row_data.items():
        if 'case' in field_name or 'number' in field_name:
            for pattern in case_patterns:
                match = re.search(pattern, value, re.IGNORECASE)
                if match:
                    return match.group(0).upper().strip()
    
    # Fallback: look in all fields
    all_text = ' '.join(row_data.values())
    for pattern in case_patterns:
        match = re.search(pattern, all_text, re.IGNORECASE)
        if match:
            return match.group(0).upper().strip()
    
    return None

def extract_address(row_data: Dict[str, str]) -> Optional[str]:
    """Extract property address from row data"""
    
    # Look for address-like content
    for field_name, value in row_data.items():
        if any(keyword in field_name for keyword in ['address', 'property', 'location']):
            if value and len(value) > 10:
                return clean_address(value)
    
    # Fallback: look for street patterns
    street_patterns = [
        r'\b\d+\s+[\w\s]+(st|street|ave|avenue|dr|drive|rd|road|ln|lane|blvd|boulevard|ct|court|cir|circle|pl|place|way)\b',
    ]
    
    for value in row_data.values():
        for pattern in street_patterns:
            match = re.search(pattern, value, re.IGNORECASE)
            if match:
                return clean_address(match.group(0))
    
    return None

def extract_auction_date(row_data: Dict[str, str]) -> Optional[str]:
    """Extract auction date from row data"""
    
    # Look for date fields first
    for field_name, value in row_data.items():
        if any(keyword in field_name for keyword in ['date', 'auction', 'sale']):
            normalized_date = normalize_date(value)
            if normalized_date:
                return normalized_date
    
    # Fallback: look for date patterns in all fields
    for value in row_data.values():
        normalized_date = normalize_date(value)
        if normalized_date:
            return normalized_date
    
    return None

def extract_status(row_data: Dict[str, str]) -> str:
    """Extract auction status from row data"""
    
    status_keywords = {
        'sold': ['sold', 'purchased'],
        'canceled': ['cancel', 'cancelled', 'withdrawn'],
        'postponed': ['postpone', 'reset', 'continued'],
        'scheduled': ['scheduled', 'upcoming']
    }
    
    all_text = ' '.join(row_data.values()).lower()
    
    for status, keywords in status_keywords.items():
        if any(keyword in all_text for keyword in keywords):
            return status
    
    return 'scheduled'  # Default

def extract_sale_type(row_data: Dict[str, str]) -> str:
    """Extract sale type from row data"""
    
    all_text = ' '.join(row_data.values()).lower()
    
    if any(keyword in all_text for keyword in ['tax', 'deed', 'certificate']):
        return 'tax_deed'
    elif any(keyword in all_text for keyword in ['foreclosure', 'mortgage']):
        return 'foreclosure'
    
    return 'foreclosure'  # Default assumption

def clean_address(address: str) -> str:
    """Clean and normalize address string"""
    if not address:
        return ""
    
    # Remove extra whitespace and normalize
    cleaned = re.sub(r'\s+', ' ', address.strip())
    
    # Remove common prefixes
    cleaned = re.sub(r'^(property|address|located at):?\s*', '', cleaned, flags=re.IGNORECASE)
    
    return cleaned.title()

def normalize_date(date_str: str) -> Optional[str]:
    """Convert various date formats to YYYY-MM-DD"""
    if not date_str:
        return None
    
    # Common date formats
    formats = [
        "%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d",
        "%m/%d/%y", "%m-%d-%y",
        "%B %d, %Y", "%b %d, %Y",
        "%d %B %Y", "%d %b %Y"
    ]
    
    # Clean the date string
    date_clean = re.sub(r'[^\w\s/\-,:]', '', date_str).strip()
    
    for fmt in formats:
        try:
            parsed_date = datetime.strptime(date_clean, fmt)
            return parsed_date.strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    return None

def upsert_auctions_to_db(auctions: List[Dict], county: str) -> int:
    """Upsert auction records to Supabase"""
    logger.info(f"Upserting {len(auctions)} auctions to database for {county}")
    
    if not auctions:
        return 0
    
    try:
        # Upsert to multi_county_auctions
        url = f"{BASE}/multi_county_auctions"
        
        inserted_count = 0
        
        for auction in auctions:
            response = client.post(url, headers=get_headers(), json=auction)
            
            if response.status_code in [200, 201]:
                inserted_count += 1
            else:
                logger.warning(f"Failed to insert auction {auction.get('case_number')}: {response.status_code}")
        
        logger.info(f"Successfully upserted {inserted_count} auctions for {county}")
        return inserted_count
        
    except Exception as e:
        logger.error(f"Error upserting auctions for {county}: {e}")
        return 0

def scrape_county_auctions(county: str, dry_run: bool = False) -> Dict:
    """Scrape all auctions for a specific county"""
    logger.info(f"Scraping auctions for {county} county")
    
    # Discover auction pages
    pages = discover_auction_pages(county)
    
    if not pages:
        logger.warning(f"No auction pages found for {county}")
        return {'success': False, 'error': 'no_pages_discovered'}
    
    all_auctions = []
    
    # Scrape each discovered page
    for page_url in pages:
        page_auctions = scrape_auction_page(page_url, county)
        all_auctions.extend(page_auctions)
        
        # Rate limiting
        time.sleep(2)
    
    logger.info(f"Total auctions discovered for {county}: {len(all_auctions)}")
    
    if dry_run:
        logger.info("DRY RUN: Not inserting to database")
        return {
            'success': True,
            'auctions_found': len(all_auctions),
            'pages_scraped': len(pages),
            'sample_auctions': all_auctions[:3]  # Sample for review
        }
    
    # Insert to database
    inserted_count = upsert_auctions_to_db(all_auctions, county)
    
    return {
        'success': True,
        'auctions_found': len(all_auctions),
        'auctions_inserted': inserted_count,
        'pages_scraped': len(pages),
        'insertion_rate': inserted_count / len(all_auctions) if all_auctions else 0
    }

def main():
    parser = argparse.ArgumentParser(description='SHARD-10 Multi-County Auction Scraper')
    parser.add_argument('--county', choices=list(CLERK_TARGETS.keys()), help='Single county to scrape')
    parser.add_argument('--all-counties', action='store_true', help='Scrape all SHARD-10 counties')
    parser.add_argument('--discover-only', action='store_true', help='Discover pages only, no scraping')
    parser.add_argument('--dry-run', action='store_true', help='Parse only, no database inserts')
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("SHARD-10 MULTI-COUNTY AUCTION SCRAPER")
    logger.info("=" * 60)
    
    counties_to_process = []
    
    if args.all_counties:
        counties_to_process = list(CLERK_TARGETS.keys())
    elif args.county:
        counties_to_process = [args.county]
    else:
        # Default: all counties for autonomous session
        counties_to_process = list(CLERK_TARGETS.keys())
    
    results = {}
    
    for county in counties_to_process:
        logger.info(f"\n--- Processing {county} ---")
        
        if args.discover_only:
            pages = discover_auction_pages(county)
            results[county] = {'pages_discovered': pages}
            logger.info(f"Pages discovered: {pages}")
        else:
            result = scrape_county_auctions(county, dry_run=args.dry_run)
            results[county] = result
            logger.info(f"Scraping result: {result}")
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("SHARD-10 SCRAPING SUMMARY")
    logger.info("=" * 60)
    
    total_found = 0
    total_inserted = 0
    
    for county, result in results.items():
        if 'auctions_found' in result:
            found = result['auctions_found']
            inserted = result.get('auctions_inserted', 0)
            total_found += found
            total_inserted += inserted
            logger.info(f"{county}: {found} found, {inserted} inserted")
        elif 'pages_discovered' in result:
            pages = len(result['pages_discovered'])
            logger.info(f"{county}: {pages} pages discovered")
        elif result.get('error'):
            logger.info(f"{county}: ERROR - {result['error']}")
    
    if not args.discover_only:
        logger.info(f"\nTOTAL: {total_found} auctions found, {total_inserted} inserted")
    
    logger.info("\nSHARD-10 auction scraping complete")

if __name__ == "__main__":
    main()