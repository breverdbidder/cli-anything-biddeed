#!/usr/bin/env python3
"""
SHARD-13 Parcel Linkage Fix - Letter E Gold Standard  
===================================================

Issue: E-letter failures across all SHARD-13 counties
- palm_beach: E=83.4% (parcel_linked=23832 of 28562)
- clay: E=86.0% (parcel_linked=2387 of 2774) 
- okaloosa: E=74.9% (parcel_linked=1511 of 2018)
- gulf: E=88.9% (parcel_linked=8 of 9)

Goal: Link auction cases to parcel_ids via county property appraiser APIs
Pattern: Based on Duval BCPAO pattern, adapted for all SHARD-13 counties
Canon: ≥95% parcel linkage required for E-letter pass

Strategy:
1. Discover property appraiser endpoints for each county
2. Match auction addresses/cases to parcel IDs via appraiser search
3. Update multi_county_auctions.parcel_id for improved E metrics
4. Verify E-letter improvements via pencil_dod_evaluate_county
"""

import os
import sys
import json
import time
import logging
import requests
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse, quote_plus
import hashlib

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# SHARD-13 County property appraiser endpoints
COUNTY_APPRAISER_ENDPOINTS = {
    'palm_beach': [
        "https://www.pbcgov.org/papa/",  # Palm Beach County Property Appraiser
        "https://www.pbcgov.org/papa/Asps/PropertySearches/PropertySearch.asp",
        "https://www.pbcgov.org/papa/Asps/PropertySearch/PropertySearch.asp",
        "https://www.pbcgov.org/papa/Property/Search/",
    ],
    'clay': [
        "https://www.ccpao.com/",  # Clay County Property Appraiser 
        "https://www.ccpao.com/property-search/",
        "https://gis.ccpao.com/",
    ],
    'okaloosa': [
        "https://www.property-appraiser.org/",  # Okaloosa County Property Appraiser
        "https://www.property-appraiser.org/search/",
        "https://qpublic.schneidercorp.com/Application.aspx?AppID=954&LayerID=17073&PageTypeID=2&PageID=8223",
    ],
    'gulf': [
        "https://qpublic.schneidercorp.com/Application.aspx?AppID=654&LayerID=11433&PageTypeID=2&PageID=5486",  # Gulf County qPublic
        "http://gulf.county-taxes.com/public/",
        "https://www.gulfcounty-fl.gov/departments/property_appraiser.php",
    ]
}

@dataclass
class ParcelMatch:
    case_number: str
    property_address: str
    parcel_id: str
    confidence: float
    match_method: str
    appraiser_url: str
    county: str

class CountyPropertyAppraiserScraper:
    def __init__(self, county: str):
        self.county = county
        self.endpoints = COUNTY_APPRAISER_ENDPOINTS.get(county, [])
        self.working_endpoint = None
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': f'BidDeed-SHARD13-ParcelLinkage/1.0 (County: {county}; contact: ariel@everestcapitalusa.com)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
    
    def discover_working_endpoint(self) -> Optional[str]:
        """Discover working property appraiser endpoint for the county"""
        logger.info(f"Discovering {self.county} property appraiser endpoint...")
        
        for endpoint in self.endpoints:
            try:
                response = self.session.get(endpoint, timeout=10)
                if response.status_code == 200:
                    html_lower = response.text.lower()
                    
                    # Look for property search indicators
                    indicators = [
                        'property search', 'parcel search', 'address search', 
                        'property appraiser', 'parcel number', 'qpublic',
                        'property details', 'assessment', 'real estate'
                    ]
                    
                    score = sum(1 for indicator in indicators if indicator in html_lower)
                    
                    if score >= 2:
                        logger.info(f"✅ {self.county}: Found working endpoint: {endpoint} (score: {score})")
                        self.working_endpoint = endpoint
                        return endpoint
                    else:
                        logger.debug(f"⚠️ {self.county}: {endpoint} reachable but low score: {score}")
                        
            except Exception as e:
                logger.debug(f"❌ {self.county}: {endpoint} failed: {e}")
                continue
        
        logger.warning(f"No suitable {self.county} property appraiser endpoint found")
        return None
    
    def search_by_address(self, address: str) -> List[Dict]:
        """Search property appraiser by address to find parcel ID"""
        if not self.working_endpoint:
            return []
        
        # Clean and prepare address for search
        clean_address = self.clean_address_for_search(address)
        if not clean_address:
            return []
        
        # Try different search URL patterns
        search_patterns = self.get_search_patterns(clean_address)
        
        for search_url in search_patterns:
            try:
                response = self.session.get(search_url, timeout=15)
                if response.status_code == 200:
                    results = self.parse_search_results(response.text, address)
                    if results:
                        return results
                time.sleep(1)  # Rate limiting
            except Exception as e:
                logger.debug(f"{self.county}: Search failed {search_url}: {e}")
                continue
        
        return []
    
    def clean_address_for_search(self, address: str) -> str:
        """Clean address for property appraiser search"""
        if not address:
            return ""
        
        # Remove common prefixes/suffixes that interfere with search
        address = re.sub(r'^\s*(LOT|PARCEL|TRACT)\s+\d+\s*[,\s]*', '', address, flags=re.IGNORECASE)
        address = re.sub(r'\s*,?\s*(FL|FLORIDA)\s*\d{5}.*$', '', address, flags=re.IGNORECASE)
        address = re.sub(r'\s*,?\s*\w+\s+COUNTY\s*,?\s*', '', address, flags=re.IGNORECASE)
        
        # Extract street address part
        match = re.search(r'\d+\s+[\w\s]+?(?:st|street|ave|avenue|rd|road|blvd|boulevard|dr|drive|way|ln|lane|ct|court|pl|place|cir|circle)\.?(?:\s|$)', 
                         address, re.IGNORECASE)
        
        if match:
            return match.group().strip()
        
        # Fallback: clean basic patterns
        address = re.sub(r'[^\w\s\-\.]', '', address)
        return address.strip()
    
    def get_search_patterns(self, clean_address: str) -> List[str]:
        """Generate search URL patterns for the county"""
        encoded_address = quote_plus(clean_address)
        
        patterns = []
        base = self.working_endpoint.rstrip('/')
        
        # Common property appraiser search patterns
        if 'qpublic' in base:
            # qPublic (common for FL counties)
            patterns.extend([
                f"{base}&SearchType=Address&SearchValue={encoded_address}",
                f"{base}?pid={encoded_address}",
            ])
        elif 'pbcgov.org' in base:
            # Palm Beach specific
            patterns.extend([
                f"{base}?search_type=address&search_value={encoded_address}",
                f"{base}?Address={encoded_address}",
            ])
        elif 'ccpao.com' in base:
            # Clay County specific  
            patterns.extend([
                f"{base}?address={encoded_address}",
                f"{base}search/?q={encoded_address}",
            ])
        elif 'property-appraiser.org' in base:
            # Okaloosa specific
            patterns.extend([
                f"{base}?address={encoded_address}",
                f"{base}search.php?address={encoded_address}",
            ])
        
        # Generic fallback patterns
        patterns.extend([
            f"{base}/search?address={encoded_address}",
            f"{base}/property-search?q={encoded_address}",
            f"{base}?search={encoded_address}",
        ])
        
        return patterns
    
    def parse_search_results(self, html: str, original_address: str) -> List[Dict]:
        """Parse search results to extract parcel IDs"""
        results = []
        
        # Look for parcel ID patterns
        parcel_patterns = [
            r'parcel[^\w]*(?:id|number)?[:\s]*([A-Z0-9\-\.]{6,20})',
            r'(?:property|account)[^\w]*(?:id|number)?[:\s]*([A-Z0-9\-\.]{6,20})',
            r'\b(\d{2,4}[-\.\s]?\d{2,4}[-\.\s]?\d{2,6}[-\.\s]?\d{0,6})\b',  # Common FL parcel format
        ]
        
        found_parcels = set()
        for pattern in parcel_patterns:
            matches = re.finditer(pattern, html, re.IGNORECASE)
            for match in matches:
                parcel_id = match.group(1).strip()
                if len(parcel_id) >= 6:  # Minimum reasonable parcel ID length
                    found_parcels.add(parcel_id)
        
        # Score matches by address similarity
        for parcel_id in found_parcels:
            # Extract context around parcel ID to find associated address
            parcel_pos = html.find(parcel_id)
            if parcel_pos > -1:
                start = max(0, parcel_pos - 300)
                end = min(len(html), parcel_pos + 300)
                context = html[start:end]
                
                # Look for address in context
                address_match = re.search(
                    r'\d+\s+[\w\s]+?(?:st|street|ave|avenue|rd|road|blvd|boulevard|dr|drive|way|ln|lane|ct|court|pl|place)\.?',
                    context, re.IGNORECASE
                )
                
                if address_match:
                    found_address = address_match.group().strip()
                    confidence = self.calculate_address_similarity(original_address, found_address)
                    
                    if confidence >= 0.6:  # Reasonable confidence threshold
                        results.append({
                            'parcel_id': parcel_id,
                            'found_address': found_address,
                            'confidence': confidence,
                            'context': context[:200] + "..." if len(context) > 200 else context
                        })
        
        # Sort by confidence and return top matches
        results.sort(key=lambda x: x['confidence'], reverse=True)
        return results[:3]  # Return top 3 matches
    
    def calculate_address_similarity(self, addr1: str, addr2: str) -> float:
        """Calculate similarity between two addresses (0.0 - 1.0)"""
        if not addr1 or not addr2:
            return 0.0
        
        # Normalize addresses
        norm1 = re.sub(r'[^\w]', ' ', addr1.lower()).split()
        norm2 = re.sub(r'[^\w]', ' ', addr2.lower()).split()
        
        if not norm1 or not norm2:
            return 0.0
        
        # Calculate Jaccard similarity
        set1, set2 = set(norm1), set(norm2)
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        return intersection / union if union > 0 else 0.0

def get_county_cases_needing_parcel_linkage(county: str, limit: int = 100) -> List[Dict]:
    """Get auction cases missing parcel_id for a county"""
    try:
        import httpx
        
        SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
        SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY", "")
        
        if not SUPABASE_KEY:
            logger.error("No Supabase key available")
            return []
        
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        with httpx.Client(timeout=30) as client:
            response = client.get(
                f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
                headers=headers,
                params={
                    "select": "case_number,property_address,plaintiff,defendant,property_city",
                    "county": f"eq.{county}",
                    "parcel_id": "is.null",
                    "property_address": "not.is.null",
                    "limit": str(limit),
                    "order": "auction_date.desc"
                }
            )
            
            if response.status_code == 200:
                cases = response.json()
                logger.info(f"{county}: Found {len(cases)} cases needing parcel linkage")
                return cases
            else:
                logger.error(f"{county}: Failed to get cases: {response.status_code}")
                return []
                
    except Exception as e:
        logger.error(f"{county}: Error getting cases: {e}")
        return []

def update_auction_parcel_ids(matches: List[ParcelMatch]) -> Dict:
    """Update multi_county_auctions with matched parcel IDs"""
    if not matches:
        return {'updated': 0, 'status': 'no_data'}
    
    try:
        import httpx
        
        SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
        SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY", "")
        
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        updated_count = 0
        
        with httpx.Client(timeout=60) as client:
            for match in matches:
                # Update individual case with parcel_id
                response = client.patch(
                    f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
                    headers=headers,
                    params={
                        "case_number": f"eq.{match.case_number}",
                        "county": f"eq.{match.county}"
                    },
                    json={
                        "parcel_id": match.parcel_id,
                        "parcel_match_confidence": match.confidence,
                        "parcel_match_method": match.match_method,
                        "parcel_appraiser_url": match.appraiser_url,
                        "updated_at": datetime.utcnow().isoformat()
                    }
                )
                
                if response.status_code in [200, 204]:
                    updated_count += 1
                    logger.info(f"✅ {match.case_number}: parcel_id={match.parcel_id} (conf: {match.confidence:.2f})")
                else:
                    logger.warning(f"❌ {match.case_number}: Update failed: {response.status_code}")
        
        return {'updated': updated_count, 'status': 'success'}
        
    except Exception as e:
        logger.error(f"Error updating parcel IDs: {e}")
        return {'updated': 0, 'status': 'error', 'error': str(e)}

def verify_e_letter_improvements(counties: List[str]) -> Dict:
    """Verify E-letter improvements for counties"""
    try:
        import httpx
        
        SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
        SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY", "")
        
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        results = {}
        
        with httpx.Client(timeout=60) as client:
            for county in counties:
                response = client.post(
                    f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
                    headers=headers,
                    json={"county_slug_arg": county}
                )
                
                if response.status_code == 200:
                    eval_results = response.json()
                    e_result = next((r for r in eval_results if r.get('letter') == 'E'), None)
                    if e_result:
                        results[county] = {
                            'e_pass': e_result.get('pass'),
                            'e_metric': e_result.get('metric'),
                            'e_details': e_result.get('details')
                        }
                    else:
                        results[county] = {'error': 'E metric not found'}
                else:
                    results[county] = {'error': f'Evaluation failed: {response.status_code}'}
        
        return results
        
    except Exception as e:
        logger.error(f"E-letter verification failed: {e}")
        return {'error': str(e)}

def main():
    logger.info("=== SHARD-13 Parcel Linkage Fix (E-Letter Gold Standard) ===")
    
    shard13_counties = ['palm_beach', 'clay', 'okaloosa', 'gulf']
    all_matches = []
    county_results = {}
    
    for county in shard13_counties:
        logger.info(f"\n--- Processing {county} county ---")
        
        # Get cases needing parcel linkage
        cases = get_county_cases_needing_parcel_linkage(county, limit=50)  # Start with manageable batch
        if not cases:
            logger.warning(f"{county}: No cases need parcel linkage")
            county_results[county] = {'processed': 0, 'matched': 0}
            continue
        
        # Initialize scraper
        scraper = CountyPropertyAppraiserScraper(county)
        working_endpoint = scraper.discover_working_endpoint()
        
        if not working_endpoint:
            logger.warning(f"{county}: No working property appraiser endpoint found")
            county_results[county] = {'processed': 0, 'matched': 0, 'error': 'no_endpoint'}
            continue
        
        county_matches = []
        for i, case in enumerate(cases):
            if not case.get('property_address'):
                continue
                
            logger.info(f"{county} [{i+1}/{len(cases)}]: {case['case_number']} - {case['property_address']}")
            
            search_results = scraper.search_by_address(case['property_address'])
            if search_results:
                # Take the best match
                best_match = search_results[0]
                match = ParcelMatch(
                    case_number=case['case_number'],
                    property_address=case['property_address'],
                    parcel_id=best_match['parcel_id'],
                    confidence=best_match['confidence'],
                    match_method='address_search',
                    appraiser_url=working_endpoint,
                    county=county
                )
                county_matches.append(match)
                logger.info(f"  ✅ Matched: {match.parcel_id} (conf: {match.confidence:.2f})")
            else:
                logger.info(f"  ❌ No match found")
            
            time.sleep(1)  # Rate limiting
        
        all_matches.extend(county_matches)
        county_results[county] = {
            'processed': len(cases),
            'matched': len(county_matches),
            'match_rate': len(county_matches) / len(cases) if cases else 0
        }
        
        logger.info(f"{county} summary: {len(county_matches)}/{len(cases)} matched ({county_results[county]['match_rate']:.1%})")
    
    # Update database with all matches
    if all_matches:
        update_result = update_auction_parcel_ids(all_matches)
        logger.info(f"Database updates: {update_result}")
    else:
        update_result = {'updated': 0, 'status': 'no_matches'}
    
    # Verify E-letter improvements
    time.sleep(10)  # Wait for database consistency
    verification = verify_e_letter_improvements(shard13_counties)
    
    logger.info("\n=== E-letter Verification ===")
    for county, verify_data in verification.items():
        if 'error' in verify_data:
            logger.error(f"{county}: {verify_data['error']}")
        else:
            e_pass = verify_data.get('e_pass', False)
            e_metric = verify_data.get('e_metric', 'N/A')
            status = "✅ PASS" if e_pass else "❌ FAIL"
            logger.info(f"{county}: E-letter {status} (metric: {e_metric}%)")
    
    # Summary
    summary = {
        'execution_date': datetime.utcnow().isoformat(),
        'counties_processed': list(county_results.keys()),
        'total_matches_found': len(all_matches),
        'matches_updated': update_result.get('updated', 0),
        'county_results': county_results,
        'e_letter_verification': verification
    }
    
    print(json.dumps(summary, indent=2))
    
    # Success criteria: any county E-letter improved OR matches were found and updated
    improved_counties = [
        county for county, data in verification.items()
        if data.get('e_pass', False) and 'error' not in data
    ]
    
    if improved_counties or update_result.get('updated', 0) > 0:
        logger.info(f"🎉 SHARD-13 parcel linkage improvements: {len(improved_counties)} counties improved, {update_result.get('updated', 0)} parcel IDs linked")
        return 0
    else:
        logger.warning("No significant E-letter improvements achieved")
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Script failed: {e}")
        sys.exit(1)