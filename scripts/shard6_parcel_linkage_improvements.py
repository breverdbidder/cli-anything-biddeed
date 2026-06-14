#!/usr/bin/env python3
"""
SHARD-6 Parcel Linkage Improvements (Letter E) - SHIP-TO-MAIN
GOLD STANDARD CAMPAIGN RUN 27: highlands, escambia, nassau, calhoun, liberty

Current E status per issue brief:
- highlands: E❌ 50.2% [parcel_linked=121 of 241]
- escambia: E❌ 87.1% [parcel_linked=5714 of 6557] 
- nassau: E❌ 80.3% [parcel_linked=391 of 487]
- calhoun: E❌ 0.0% [parcel_linked=0 of 4]
- liberty: E❌ null [parcel_linked=0 of 0]

Letter E enables downstream fixes: "parcel linkage fixes (E) make parcels comps-eligible -> 
the valuations re-armer picks them up automatically -> J inputs flow"

Strategy: Link parcel_id via county property appraiser ArcGIS FeatureServer
"Brevard/BCPAO pipeline is the reference implementation"

Usage:
  python scripts/shard6_parcel_linkage_improvements.py --county escambia
  python scripts/shard6_parcel_linkage_improvements.py --all-counties
"""
import os
import sys
import json
import httpx
import time
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

# SHARD-6 target counties
TARGET_COUNTIES = ['highlands', 'escambia', 'nassau', 'calhoun', 'liberty']

# County DOR numbers for sample_properties linkage
COUNTY_DOR_MAP = {
    'highlands': 28,
    'escambia': 17, 
    'nassau': 48,
    'calhoun': 7,
    'liberty': 35
}

# Property appraiser GIS endpoints (to be discovered/verified)
COUNTY_APPRAISER_ENDPOINTS = {
    'highlands': 'https://maps.hcbcc.org/arcgis/rest/services/',  # To verify
    'escambia': 'https://maps.escambiapa.com/arcgis/rest/services/',  # To verify
    'nassau': 'https://gis.nassauflpa.com/arcgis/rest/services/',  # To verify
    'calhoun': None,  # Small county, may not have GIS
    'liberty': None   # Small county, may not have GIS
}

client = httpx.Client(timeout=60)

def get_county_linkage_status(county_slug: str) -> Dict:
    """Get current Letter E status using pencil_dod_evaluate_county"""
    
    logger.info(f"Getting Letter E status for {county_slug}...")
    
    try:
        response = client.post(
            f"{BASE}/rpc/pencil_dod_evaluate_county",
            headers=HEADERS,
            json={"county_param": county_slug},
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # Find Letter E result
            e_status = None
            for row in result:
                if isinstance(row, dict) and row.get('letter', '').upper() == 'E':
                    e_status = {
                        'pass': row.get('pass', False),
                        'metric': row.get('metric'),
                        'detail': row.get('detail', ''),
                        'threshold': row.get('threshold', 95.0)
                    }
                    break
            
            return {
                'county': county_slug,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'status': 'success',
                'letter_e': e_status,
                'raw_result': result
            }
        else:
            logger.error(f"❌ Failed to get status for {county_slug}: {response.status_code}")
            return {
                'county': county_slug,
                'status': 'failed',
                'error': f"HTTP {response.status_code}: {response.text}"
            }
            
    except Exception as e:
        logger.error(f"❌ Error getting status for {county_slug}: {e}")
        return {
            'county': county_slug,
            'status': 'error', 
            'error': str(e)
        }

def get_unlinked_auctions(county_slug: str, limit: int = 200) -> List[Dict]:
    """Get auctions missing parcel_id"""
    
    logger.info(f"Getting unlinked auctions for {county_slug}...")
    
    try:
        response = client.get(
            f"{BASE}/multi_county_auctions",
            headers=HEADERS,
            params={
                'county': f'eq.{county_slug}',
                'parcel_id': 'is.null',
                'select': 'case_number,address,sale_type,auction_date',
                'limit': str(limit)
            }
        )
        
        if response.status_code == 200:
            auctions = response.json()
            logger.info(f"✅ Found {len(auctions)} unlinked auctions for {county_slug}")
            return auctions
        else:
            logger.error(f"❌ Failed to get auctions for {county_slug}: {response.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"❌ Error getting auctions for {county_slug}: {e}")
        return []

def get_sample_properties_for_county(county_slug: str, limit: int = 1000) -> List[Dict]:
    """Get sample_properties for address matching"""
    
    co_no = COUNTY_DOR_MAP.get(county_slug)
    if not co_no:
        logger.warning(f"No DOR mapping for {county_slug}")
        return []
    
    logger.info(f"Getting sample properties for {county_slug} (co_no={co_no})...")
    
    try:
        response = client.get(
            f"{BASE}/sample_properties",
            headers=HEADERS,
            params={
                'co_no': f'eq.{co_no}',
                'select': 'parcel_id,address,city',
                'limit': str(limit)
            }
        )
        
        if response.status_code == 200:
            properties = response.json()
            logger.info(f"✅ Found {len(properties)} sample properties for {county_slug}")
            return properties
        else:
            logger.error(f"❌ Failed to get properties for {county_slug}: {response.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"❌ Error getting properties for {county_slug}: {e}")
        return []

def normalize_address_for_matching(address: str) -> str:
    """Normalize address for fuzzy matching"""
    if not address:
        return ""
    
    # Convert to uppercase and clean
    normalized = address.strip().upper()
    
    # Remove common prefixes/suffixes
    normalized = re.sub(r'\b(LOT|UNIT|APT|APARTMENT|SUITE|STE|#)\s*\d+\b', '', normalized)
    
    # Standardize street types
    street_types = {
        'STREET': 'ST', 'AVENUE': 'AVE', 'BOULEVARD': 'BLVD',
        'DRIVE': 'DR', 'LANE': 'LN', 'ROAD': 'RD', 'CIRCLE': 'CIR',
        'COURT': 'CT', 'PLACE': 'PL', 'TERRACE': 'TER', 'WAY': 'WAY'
    }
    
    for full, abbr in street_types.items():
        normalized = re.sub(f'\\b{full}\\b', abbr, normalized)
    
    # Standardize directionals
    directionals = {'NORTH': 'N', 'SOUTH': 'S', 'EAST': 'E', 'WEST': 'W'}
    for full, abbr in directionals.items():
        normalized = re.sub(f'\\b{full}\\b', abbr, normalized)
    
    # Remove excess punctuation and normalize whitespace
    normalized = re.sub(r'[^\w\s]', ' ', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    return normalized

def calculate_address_similarity(addr1: str, addr2: str) -> float:
    """Calculate similarity score between two addresses"""
    
    norm1 = normalize_address_for_matching(addr1)
    norm2 = normalize_address_for_matching(addr2)
    
    if not norm1 or not norm2:
        return 0.0
    
    # Simple word-based similarity
    words1 = set(norm1.split())
    words2 = set(norm2.split())
    
    if len(words1) == 0:
        return 0.0
    
    # Calculate intersection over union
    intersection = len(words1 & words2)
    union = len(words1 | words2)
    
    if union == 0:
        return 0.0
    
    jaccard = intersection / union
    
    # Boost score if house numbers match exactly
    num1_match = re.search(r'^\d+', norm1)
    num2_match = re.search(r'^\d+', norm2)
    
    if num1_match and num2_match:
        if num1_match.group() == num2_match.group():
            jaccard += 0.2  # Bonus for matching house numbers
    
    return min(jaccard, 1.0)

def link_auction_to_parcel(auction: Dict, properties: List[Dict]) -> Optional[Tuple[str, float]]:
    """Try to link auction to parcel via address matching"""
    
    auction_addr = auction.get('address', '')
    if not auction_addr or len(auction_addr) < 10:
        return None
    
    best_match = None
    best_score = 0.0
    
    for prop in properties:
        prop_addr = prop.get('address', '')
        if not prop_addr:
            continue
        
        similarity = calculate_address_similarity(auction_addr, prop_addr)
        
        if similarity > best_score and similarity > 0.7:  # 70% similarity threshold
            best_score = similarity
            best_match = prop['parcel_id']
    
    if best_match:
        return (best_match, best_score)
    
    return None

def update_auction_parcel(case_number: str, county_slug: str, parcel_id: str, similarity_score: float) -> bool:
    """Update auction with linked parcel_id"""
    
    try:
        updates = {
            'parcel_id': parcel_id,
            'linkage_notes': f'Address-linked (score: {similarity_score:.2f})'
        }
        
        response = client.patch(
            f"{BASE}/multi_county_auctions",
            headers={**HEADERS, "Prefer": "return=minimal"},
            params={
                'case_number': f'eq.{case_number}',
                'county': f'eq.{county_slug}'
            },
            json=updates
        )
        
        return response.status_code == 204
        
    except Exception as e:
        logger.error(f"Error updating auction {case_number}: {e}")
        return False

def improve_linkage_for_county(county_slug: str) -> Dict:
    """Improve Letter E parcel linkage for a county"""
    
    logger.info(f"🔗 Starting parcel linkage improvements for {county_slug}")
    
    # Get baseline status
    baseline_status = get_county_linkage_status(county_slug)
    logger.info(f"Baseline Letter E status: {json.dumps(baseline_status.get('letter_e', {}), indent=2)}")
    
    # Get unlinked auctions and sample properties
    unlinked_auctions = get_unlinked_auctions(county_slug, limit=100)
    sample_properties = get_sample_properties_for_county(county_slug)
    
    if not unlinked_auctions:
        logger.info(f"No unlinked auctions found for {county_slug}")
        return baseline_status
    
    if not sample_properties:
        logger.warning(f"No sample properties available for {county_slug}")
        return baseline_status
    
    logger.info(f"Working on {len(unlinked_auctions)} unlinked auctions with {len(sample_properties)} properties")
    
    improvements = {
        'parcels_linked': 0,
        'high_confidence_links': 0,  # Score > 0.85
        'medium_confidence_links': 0,  # Score 0.7-0.85
        'auctions_processed': len(unlinked_auctions)
    }
    
    for auction in unlinked_auctions:
        case_number = auction.get('case_number')
        if not case_number:
            continue
        
        # Try to find parcel match
        match_result = link_auction_to_parcel(auction, sample_properties)
        
        if match_result:
            parcel_id, similarity_score = match_result
            
            success = update_auction_parcel(case_number, county_slug, parcel_id, similarity_score)
            
            if success:
                improvements['parcels_linked'] += 1
                
                if similarity_score > 0.85:
                    improvements['high_confidence_links'] += 1
                else:
                    improvements['medium_confidence_links'] += 1
                
                logger.info(f"✅ Linked {case_number} -> {parcel_id} (score: {similarity_score:.2f})")
            else:
                logger.warning(f"❌ Failed to update {case_number}")
    
    # Get final status after improvements
    final_status = get_county_linkage_status(county_slug)
    
    # Calculate improvement metrics
    baseline_metric = baseline_status.get('letter_e', {}).get('metric')
    final_metric = final_status.get('letter_e', {}).get('metric')
    
    metric_improvement = None
    if baseline_metric is not None and final_metric is not None:
        metric_improvement = final_metric - baseline_metric
    
    result = {
        **final_status,
        'improvements': improvements,
        'baseline_status': baseline_status,
        'metric_improvement': metric_improvement
    }
    
    logger.info(f"🔗 Parcel linkage improvements complete for {county_slug}")
    logger.info(f"Improvements: {improvements}")
    
    if metric_improvement is not None:
        logger.info(f"Letter E metric change: {baseline_metric:.1f}% -> {final_metric:.1f}% (+{metric_improvement:.1f}%)")
    
    return result

def execute_linkage_protocol() -> Dict:
    """Execute parcel linkage improvements for all SHARD-6 counties"""
    
    logger.info("🔗 Executing SHARD-6 parcel linkage improvements...")
    
    results = {}
    
    for county in TARGET_COUNTIES:
        logger.info(f"\n{'='*50}")
        logger.info(f"PROCESSING: {county.upper()}")
        logger.info(f"{'='*50}")
        
        results[county] = improve_linkage_for_county(county)
        
        # Small delay between counties
        time.sleep(2)
    
    return results

def main():
    """Main execution function"""
    
    if not SUPABASE_KEY:
        logger.error("❌ No Supabase key found in environment")
        sys.exit(1)
    
    logger.info("🏆 SHARD-6 PARCEL LINKAGE IMPROVEMENTS (LETTER E) - SHIP-TO-MAIN")
    logger.info(f"Counties: {', '.join(TARGET_COUNTIES)}")
    logger.info(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    
    if len(sys.argv) > 1:
        county = sys.argv[1].lower()
        if county == '--all-counties':
            results = execute_linkage_protocol()
        elif county in TARGET_COUNTIES:
            results = {county: improve_linkage_for_county(county)}
        else:
            logger.error(f"County {county} not in SHARD-6 assignment: {TARGET_COUNTIES}")
            sys.exit(1)
    else:
        # Default: process all counties
        results = execute_linkage_protocol()
    
    # Save results
    output_file = '/tmp/shard6_linkage_results.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"✅ Results saved to {output_file}")
    
    # Print summary
    logger.info("\n" + "="*60)
    logger.info("SHARD-6 PARCEL LINKAGE IMPROVEMENTS - SUMMARY")
    logger.info("="*60)
    
    for county, result in results.items():
        if result.get('status') == 'success':
            e_status = result.get('letter_e', {})
            improvements = result.get('improvements', {})
            metric_change = result.get('metric_improvement')
            
            logger.info(f"\n{county.upper()}:")
            logger.info(f"  Letter E: {'✅ PASS' if e_status.get('pass') else '❌ FAIL'} - {e_status.get('metric', 'N/A')}%")
            if metric_change is not None:
                logger.info(f"  Improvement: +{metric_change:.1f}%")
            logger.info(f"  Parcels linked: {improvements.get('parcels_linked', 0)}")
            logger.info(f"  High confidence: {improvements.get('high_confidence_links', 0)}")
        else:
            logger.info(f"\n{county.upper()}: ❌ ERROR - {result.get('error', 'Unknown')}")

if __name__ == "__main__":
    main()