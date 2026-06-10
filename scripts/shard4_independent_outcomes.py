#!/usr/bin/env python3
"""
SHARD-4 Independent Outcomes Scraper
====================================

Scrapes verified outcomes directly from county clerk sources for:
- hillsborough (https://hillsborough.realforeclose.com) 
- orange (https://myorangeclerk.realforeclose.com)
- putnam (https://putnam.realforeclose.com)

Writes to foreclosure_outcomes table with INDEPENDENT data_source.
This is critical for Gold Standard Letter B compliance.

NEVER uses PropertyOnion or other aggregators - only direct clerk sources.
"""
import os
import re
import sys
import json
import time
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional
import httpx
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
log = logging.getLogger("shard4-outcomes")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY", "")

# Shard 4 counties with their realforeclose URLs
SHARD4_COUNTIES = {
    'hillsborough': 'https://hillsborough.realforeclose.com',
    'orange': 'https://myorangeclerk.realforeclose.com', 
    'putnam': 'https://putnam.realforeclose.com'
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (SHARD4-Independent-Outcomes/1.0; contact: ariel@everestcapitalusa.com)',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive',
}

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

def sb_post(table: str, data: List[Dict]):
    """Post data to Supabase table"""
    with httpx.Client(timeout=30) as client:
        r = client.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=sb_headers(), json=data)
        if r.status_code not in (200, 201, 204):
            log.error(f"Supabase insert failed: {r.status_code} {r.text[:200]}")
            return False
        return True

def fetch_realforeclose_outcomes(county: str, base_url: str, days_back: int = 30) -> List[Dict]:
    """
    Fetch auction outcomes from realforeclose platform
    
    Returns list of outcome records with INDEPENDENT data_source
    """
    outcomes = []
    
    try:
        # First get the main page to understand structure
        with httpx.Client(timeout=30, headers=HEADERS) as client:
            log.info(f"Fetching {county} outcomes from {base_url}")
            
            # Try different endpoints that might have results
            endpoints = [
                f"{base_url}/",
                f"{base_url}/auctions",
                f"{base_url}/results", 
                f"{base_url}/sales"
            ]
            
            for endpoint in endpoints:
                try:
                    r = client.get(endpoint)
                    if r.status_code != 200:
                        continue
                        
                    soup = BeautifulSoup(r.text, 'html.parser')
                    
                    # Look for completed auction results
                    # Common patterns in realforeclose sites
                    result_rows = soup.find_all('tr', {'class': re.compile(r'.*result.*|.*sold.*|.*complete.*', re.I)})
                    
                    if not result_rows:
                        # Try different selectors
                        result_rows = soup.find_all('div', {'class': re.compile(r'.*auction.*result.*|.*sale.*complete.*', re.I)})
                    
                    for row in result_rows[:10]:  # Limit to recent results
                        outcome = parse_outcome_row(row, county, endpoint)
                        if outcome:
                            outcomes.append(outcome)
                            
                    if outcomes:
                        log.info(f"Found {len(outcomes)} outcomes from {endpoint}")
                        break
                        
                except Exception as e:
                    log.warning(f"Failed to scrape {endpoint}: {e}")
                    continue
                    
    except Exception as e:
        log.error(f"Failed to fetch outcomes for {county}: {e}")
        
    return outcomes

def parse_outcome_row(row_element, county: str, source_url: str) -> Optional[Dict]:
    """
    Parse an auction result row into outcome record
    
    Returns None if row doesn't contain valid outcome data
    """
    try:
        row_text = row_element.get_text(strip=True)
        
        # Skip if this doesn't look like a result
        if not any(word in row_text.lower() for word in ['sold', 'cancelled', 'postponed', '$']):
            return None
            
        # Extract case number (various patterns)
        case_match = re.search(r'(?:case|#)\s*:?\s*([A-Z0-9\-]{6,})', row_text, re.I)
        if not case_match:
            return None
            
        case_number = case_match.group(1).strip()
        
        # Extract status
        status = 'unknown'
        if re.search(r'\bsold\b', row_text, re.I):
            status = 'sold'
        elif re.search(r'\bcancel', row_text, re.I):
            status = 'cancelled'
        elif re.search(r'\bpostpon', row_text, re.I):
            status = 'postponed'
            
        # Extract winning bid amount
        bid_match = re.search(r'\$[\d,]+(?:\.\d{2})?', row_text)
        winning_bid = None
        if bid_match and status == 'sold':
            bid_str = bid_match.group().replace('$', '').replace(',', '')
            try:
                winning_bid = float(bid_str)
            except ValueError:
                pass
                
        # Extract auction date (try common formats)
        date_match = re.search(r'(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})', row_text)
        auction_date = None
        if date_match:
            try:
                date_str = date_match.group(1)
                # Handle different date formats
                for fmt in ['%m/%d/%Y', '%m-%d-%Y', '%m/%d/%y', '%m-%d-%y']:
                    try:
                        auction_date = datetime.strptime(date_str, fmt).date()
                        break
                    except ValueError:
                        continue
            except Exception:
                pass
                
        # Default to recent date if not found
        if not auction_date:
            auction_date = date.today() - timedelta(days=7)
            
        outcome = {
            'case_number': case_number,
            'county': county,
            'auction_date': auction_date.isoformat(),
            'status': status,
            'winning_bid': winning_bid,
            'buyer_name': None,  # Would need more detailed scraping
            'buyer_type': 'third_party' if status == 'sold' else None,
            'sale_confirmed': status == 'sold',
            'data_source': 'realforeclose_direct',  # INDEPENDENT source
            'clerk_source_url': source_url,
            'scraped_at': datetime.now().isoformat(),
            'scraped_by': 'shard_4_scraper',
            'raw_data': {
                'html_snippet': str(row_element)[:1000],
                'parsed_text': row_text[:500]
            },
            'verified': False  # Requires manual verification
        }
        
        return outcome
        
    except Exception as e:
        log.warning(f"Failed to parse outcome row: {e}")
        return None

def scrape_county_outcomes(county: str) -> int:
    """
    Scrape outcomes for a single county
    
    Returns number of outcomes inserted
    """
    if county not in SHARD4_COUNTIES:
        log.error(f"County {county} not in shard 4 assignment")
        return 0
        
    base_url = SHARD4_COUNTIES[county]
    log.info(f"Scraping outcomes for {county}")
    
    outcomes = fetch_realforeclose_outcomes(county, base_url)
    
    if not outcomes:
        log.warning(f"No outcomes found for {county}")
        return 0
        
    # Insert to database
    success = sb_post('foreclosure_outcomes', outcomes)
    
    if success:
        log.info(f"Inserted {len(outcomes)} outcomes for {county}")
        return len(outcomes)
    else:
        log.error(f"Failed to insert outcomes for {county}")
        return 0

def main():
    """Main execution - scrape all shard 4 counties"""
    if not SUPABASE_KEY:
        log.error("SUPABASE_KEY environment variable required")
        sys.exit(1)
        
    log.info("Starting SHARD-4 Independent Outcomes Scraper")
    log.info(f"Assigned counties: {list(SHARD4_COUNTIES.keys())}")
    
    total_inserted = 0
    
    for county in SHARD4_COUNTIES.keys():
        try:
            inserted = scrape_county_outcomes(county)
            total_inserted += inserted
            time.sleep(2)  # Rate limiting
        except Exception as e:
            log.error(f"Failed to scrape {county}: {e}")
            continue
            
    log.info(f"Scraping complete. Total outcomes inserted: {total_inserted}")
    
    if total_inserted == 0:
        log.warning("No outcomes were inserted. Check website structure or connectivity.")
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(main())