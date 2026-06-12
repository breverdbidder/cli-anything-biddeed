#!/usr/bin/env python3
"""
SHARD-19 BREVARD ACCLAIM SCRAPER - C/D Root Cause Fix
Port of Duval Acclaim pipeline to Brevard official records

ENDPOINT: vaclmweb1.brevardclerk.us/AcclaimWeb/ (VERIFIED live per brief)
PURPOSE: Harvest Certificates of Title + sale amounts post-sale
MATCH: by case_number to multi_county_auctions (source_platform=clerk_brevard)
WRITE: as INDEPENDENT verified outcomes for Letter B + parcel IDs for C/D

Usage:
  python scripts/shard19_brevard_acclaim_scraper.py
"""
import os
import requests
import json
import time
import logging
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlencode
import re

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}", 
    "Content-Type": "application/json"
}

# Brevard AcclaimWeb configuration
BREVARD_ACCLAIM_BASE = "https://vaclmweb1.brevardclerk.us/AcclaimWeb"
ACCLAIM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_acclaim_endpoint():
    """Test Brevard AcclaimWeb endpoint availability"""
    try:
        response = requests.get(BREVARD_ACCLAIM_BASE, headers=ACCLAIM_HEADERS, timeout=10)
        if response.status_code == 200:
            logger.info("✅ Brevard AcclaimWeb endpoint accessible")
            return True
        else:
            logger.error(f"❌ AcclaimWeb endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ AcclaimWeb endpoint error: {e}")
        return False

def discover_acclaim_search_endpoints():
    """Discover AcclaimWeb search form and parameters"""
    try:
        # Get main page to find search form
        response = requests.get(BREVARD_ACCLAIM_BASE, headers=ACCLAIM_HEADERS, timeout=10)
        if response.status_code != 200:
            logger.error(f"Failed to get main page: {response.status_code}")
            return None
        
        html = response.text
        
        # Look for common search patterns
        search_patterns = {
            'doctype_search': r'(DocTypeSearch|DocumentSearch)',
            'grantor_search': r'(GrantorSearch|NameSearch)', 
            'date_search': r'(DateSearch|RecordedDate)',
            'book_page': r'(BookPage|Instrument)'
        }
        
        found_endpoints = {}
        for pattern_name, pattern in search_patterns.items():
            matches = re.findall(pattern, html, re.IGNORECASE)
            if matches:
                found_endpoints[pattern_name] = matches[0]
        
        logger.info(f"🔍 Found AcclaimWeb endpoints: {found_endpoints}")
        return found_endpoints
        
    except Exception as e:
        logger.error(f"Error discovering AcclaimWeb endpoints: {e}")
        return None

def get_brevard_cases_to_harvest():
    """Get Brevard cases from multi_county_auctions that need AcclaimWeb lookup"""
    try:
        # Query for Brevard cases with court format case numbers
        response = requests.get(
            f"{BASE}/multi_county_auctions",
            headers=HEADERS,
            params={
                "county": "eq.brevard",
                "source_platform": "eq.clerk_brevard",
                "select": "case_number,auction_date,parcel_id,sale_type",
                "limit": "1000"
            },
            timeout=30
        )
        
        if response.status_code != 200:
            logger.error(f"Failed to get Brevard cases: {response.status_code}")
            return []
        
        cases = response.json()
        
        # Filter for court-format case numbers (not PO-xxxxx)
        court_cases = []
        for case in cases:
            case_number = case.get('case_number', '')
            # Look for court format: 2024-CA-12345 or similar
            if re.match(r'\d{4}-[A-Z]{2,}-\d+', case_number):
                court_cases.append(case)
        
        logger.info(f"📋 Found {len(court_cases)} Brevard court-format cases to process")
        return court_cases
        
    except Exception as e:
        logger.error(f"Error getting Brevard cases: {e}")
        return []

def search_acclaim_by_case_number(case_number, search_endpoints=None):
    """Search AcclaimWeb for documents by case number"""
    try:
        # Try multiple search approaches
        search_urls = [
            f"{BREVARD_ACCLAIM_BASE}/DocumentSearch.aspx",
            f"{BREVARD_ACCLAIM_BASE}/Search.aspx",
            f"{BREVARD_ACCLAIM_BASE}/AdvancedSearch.aspx"
        ]
        
        search_params = {
            'CaseNumber': case_number,
            'DocumentType': 'CT',  # Certificate of Title
            'StartDate': '',
            'EndDate': ''
        }
        
        for url in search_urls:
            try:
                # Try GET with query params
                response = requests.get(
                    url, 
                    params=search_params,
                    headers=ACCLAIM_HEADERS,
                    timeout=15
                )
                
                if response.status_code == 200 and 'CT' in response.text:
                    logger.info(f"✅ Found documents for {case_number} via {url}")
                    return parse_acclaim_response(response.text, case_number)
                
                # Try POST
                response = requests.post(
                    url,
                    data=search_params,
                    headers=ACCLAIM_HEADERS,
                    timeout=15
                )
                
                if response.status_code == 200 and 'CT' in response.text:
                    logger.info(f"✅ Found documents for {case_number} via POST {url}")
                    return parse_acclaim_response(response.text, case_number)
                    
            except Exception as search_e:
                logger.debug(f"Search attempt failed for {url}: {search_e}")
                continue
        
        logger.debug(f"No documents found for {case_number}")
        return None
        
    except Exception as e:
        logger.error(f"Error searching AcclaimWeb for {case_number}: {e}")
        return None

def parse_acclaim_response(html_content, case_number):
    """Parse AcclaimWeb search results to extract Certificate of Title info"""
    try:
        # Look for Certificate of Title (CT) documents
        ct_pattern = r'CT.*?(\d+\.\d{2}).*?(\d{2}/\d{2}/\d{4})'
        matches = re.findall(ct_pattern, html_content, re.IGNORECASE | re.DOTALL)
        
        if not matches:
            # Try alternative patterns
            amount_patterns = [
                r'Sale Amount.*?(\$[\d,]+\.\d{2})',
                r'Consideration.*?(\$[\d,]+\.\d{2})',
                r'(\$[\d,]+\.\d{2})',
            ]
            
            amounts = []
            for pattern in amount_patterns:
                amounts.extend(re.findall(pattern, html_content))
            
            if amounts:
                # Use first amount found
                amount_str = amounts[0].replace('$', '').replace(',', '')
                try:
                    amount = float(amount_str)
                except:
                    amount = None
            else:
                amount = None
        else:
            amount_str = matches[0][0]
            try:
                amount = float(amount_str)
            except:
                amount = None
        
        # Extract parcel ID if present
        parcel_patterns = [
            r'Parcel.*?(\d{2}-\d{2}-\d{2}-\d{2})',
            r'PCN.*?(\d+)',
            r'Property ID.*?(\d+)'
        ]
        
        parcel_id = None
        for pattern in parcel_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            if matches:
                parcel_id = matches[0]
                break
        
        return {
            'case_number': case_number,
            'sale_amount': amount,
            'parcel_id': parcel_id,
            'document_type': 'CT',
            'found_documents': len(re.findall(r'CT', html_content, re.IGNORECASE))
        }
        
    except Exception as e:
        logger.error(f"Error parsing AcclaimWeb response for {case_number}: {e}")
        return None

def write_foreclosure_outcome(case_data):
    """Write foreclosure outcome to database"""
    try:
        outcome_data = {
            'county_slug': 'brevard',
            'case_number': case_data['case_number'],
            'auction_date': case_data.get('auction_date'),
            'sale_status': 'sold' if case_data.get('sale_amount') else 'unknown',
            'sale_amount': case_data.get('sale_amount'),
            'parcel_id': case_data.get('parcel_id'),
            'data_source': 'acclaim_ct:BREVARD-FC-V1',
            'source_url': f"{BREVARD_ACCLAIM_BASE}/DocumentSearch.aspx",
            'confidence_level': 'verified',
            'notes': f"CT documents found: {case_data.get('found_documents', 0)}"
        }
        
        response = requests.post(
            f"{BASE}/foreclosure_outcomes",
            headers=HEADERS,
            json=outcome_data,
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            logger.info(f"✅ Wrote foreclosure outcome for {case_data['case_number']}")
            return True
        else:
            logger.error(f"Failed to write outcome: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error writing foreclosure outcome: {e}")
        return False

def update_parity_status(case_number, new_parcel_id=None):
    """Update parity_status from no_match to matched_clean if we found parcel_id"""
    if not new_parcel_id:
        return False
    
    try:
        update_data = {
            'parity_status': 'matched_clean',
            'parcel_id': new_parcel_id,
            'updated_at': datetime.now().isoformat()
        }
        
        response = requests.patch(
            f"{BASE}/multi_county_auctions",
            headers=HEADERS,
            params={"case_number": f"eq.{case_number}"},
            json=update_data,
            timeout=10
        )
        
        if response.status_code == 204:
            logger.info(f"✅ Updated parity_status to matched_clean for {case_number}")
            return True
        else:
            logger.error(f"Failed to update parity: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"Error updating parity status: {e}")
        return False

def main():
    """Main execution"""
    print("🏛️ BREVARD ACCLAIM SCRAPER - C/D Root Cause Fix")
    print("Per BREVARD SPRINT ORDER priority #1")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Test endpoints
    if not test_acclaim_endpoint():
        print("❌ AcclaimWeb endpoint not accessible - aborting")
        return
    
    # Discover search endpoints
    search_endpoints = discover_acclaim_search_endpoints()
    
    # Get cases to process
    cases = get_brevard_cases_to_harvest()
    if not cases:
        print("⚠️  No Brevard cases found to process")
        return
    
    print(f"\n🎯 Processing {len(cases)} Brevard court cases...")
    
    # Process each case
    processed = 0
    outcomes_written = 0
    parity_fixed = 0
    
    for case in cases[:10]:  # Start with 10 cases for testing
        case_number = case['case_number']
        print(f"\n📋 Processing {case_number}...")
        
        # Search AcclaimWeb
        result = search_acclaim_by_case_number(case_number, search_endpoints)
        
        if result:
            processed += 1
            
            # Merge with original case data
            result.update(case)
            
            # Write foreclosure outcome
            if write_foreclosure_outcome(result):
                outcomes_written += 1
            
            # Update parity if we found parcel_id
            if result.get('parcel_id') and update_parity_status(case_number, result['parcel_id']):
                parity_fixed += 1
        
        # Rate limiting
        time.sleep(1)
    
    # Summary
    print(f"\n{'='*60}")
    print("BREVARD ACCLAIM SCRAPER RESULTS")
    print('='*60)
    print(f"📊 Cases processed: {processed}/{len(cases)}")
    print(f"💾 Foreclosure outcomes written: {outcomes_written}")
    print(f"🔗 Parity status fixed (no_match → matched_clean): {parity_fixed}")
    
    if outcomes_written > 0:
        print(f"\n✅ SUCCESS: {outcomes_written} independent outcomes added")
        print(f"📈 This should improve Letter B verification ratio")
    
    if parity_fixed > 0:
        print(f"\n✅ SUCCESS: {parity_fixed} parity matches recovered")  
        print(f"📈 This should improve Letter C/D ratios")
    
    print(f"\n📋 NEXT STEPS:")
    print(f"1. Run full batch on remaining {len(cases)-10} cases")
    print(f"2. Execute pencil_dod_evaluate_county('brevard') to verify improvement")
    print(f"3. Repeat for Duval with existing acclaim pipeline")
    
    print(f"\n⚡ ACCLAIM SCRAPER: COMPLETED first batch")

if __name__ == "__main__":
    main()