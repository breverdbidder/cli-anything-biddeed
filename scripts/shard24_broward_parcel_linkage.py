#!/usr/bin/env python3
"""
SHARD-24 Broward Letter E Fix - Parcel Linkage
High-leverage fix: 20.6% -> 95% parcel linkage target

Broward specific implementation targeting 30,109 auctions.
Current: 6,205 linked (20.6%), need +22,486 linkages to hit 95%.
"""
import os
import sys
import time
import httpx
import json
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional

# Broward County Property Appraiser endpoints
BROWARD_PA_CONFIG = {
    'base_url': 'https://www.bcpa.net',
    'search_endpoint': '/Property-Search',
    'api_search': 'https://www.bcpa.net/api/v1/property/search',
    'folio_pattern': r'\d{10,15}',  # Typical Broward folio format
    'rate_limit_delay': 0.5  # Seconds between requests
}

# Database connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

def log_action(msg: str, level: str = "INFO", honesty_tag: str = "UNTESTED"):
    """Log with honesty protocol tags"""
    timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{timestamp}] {level} [{honesty_tag}]: {msg}")

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

def sb_query(table: str, params: str) -> List[Dict]:
    """Query Supabase table via REST API"""
    try:
        client = httpx.Client(timeout=60)
        url = f"{SUPABASE_URL}/rest/v1/{table}?{params}"
        
        response = client.get(url, headers=sb_headers())
        
        if response.status_code == 200:
            return response.json()
        else:
            log_action(f"Query failed: {response.status_code}", "ERROR", "VERIFIED")
            return []
    except Exception as e:
        log_action(f"Query error: {e}", "ERROR", "VERIFIED")
        return []

def sb_update(table: str, match_field: str, match_value: str, updates: Dict) -> bool:
    """Update single record in Supabase"""
    try:
        client = httpx.Client(timeout=60)
        url = f"{SUPABASE_URL}/rest/v1/{table}?{match_field}=eq.{match_value}"
        
        headers = sb_headers()
        headers["Prefer"] = "resolution=merge-duplicates"
        
        response = client.patch(url, headers=headers, json=updates)
        
        if response.status_code in (200, 204):
            return True
        else:
            log_action(f"Update failed: {response.status_code}", "ERROR", "VERIFIED")
            return False
    except Exception as e:
        log_action(f"Update error: {e}", "ERROR", "VERIFIED")
        return False

def get_unlinked_broward_auctions(batch_size: int = 100) -> List[Dict]:
    """Get Broward auctions missing parcel_id"""
    params = "select=case_number,property_address,tax_parcel_id,legal_description&county=eq.broward&parcel_id=is.null&limit=" + str(batch_size)
    
    auctions = sb_query("multi_county_auctions", params)
    
    if auctions:
        log_action(f"Retrieved {len(auctions)} unlinked Broward auctions", "INFO", "VERIFIED")
    else:
        log_action("No unlinked auctions found or query failed", "WARN", "VERIFIED")
    
    return auctions

def extract_parcel_candidates(auction: Dict) -> List[str]:
    """Extract potential parcel IDs from auction data"""
    candidates = []
    
    # From tax_parcel_id field
    tax_parcel = auction.get('tax_parcel_id', '')
    if tax_parcel:
        # Clean and validate format
        clean_parcel = re.sub(r'[^\w]', '', tax_parcel)
        if re.match(BROWARD_PA_CONFIG['folio_pattern'], clean_parcel):
            candidates.append(clean_parcel)
    
    # From property address (sometimes contains folio)
    address = auction.get('property_address', '')
    if address:
        folio_matches = re.findall(BROWARD_PA_CONFIG['folio_pattern'], address)
        candidates.extend(folio_matches)
    
    # From legal description
    legal_desc = auction.get('legal_description', '')
    if legal_desc:
        folio_matches = re.findall(BROWARD_PA_CONFIG['folio_pattern'], legal_desc)
        candidates.extend(folio_matches)
    
    # Remove duplicates while preserving order
    unique_candidates = list(dict.fromkeys(candidates))
    
    if unique_candidates:
        log_action(f"Extracted {len(unique_candidates)} parcel candidates", "INFO", "VERIFIED")
    
    return unique_candidates

def validate_parcel_at_bcpa(parcel_id: str) -> Dict:
    """Validate parcel ID at Broward County Property Appraiser"""
    try:
        client = httpx.Client(timeout=15, headers={"User-Agent": "SHARD24-BrowardLinkage"})
        
        # Try direct property search
        search_url = f"{BROWARD_PA_CONFIG['base_url']}/Property-Search"
        
        # Search by folio number
        search_params = {
            'folio': parcel_id,
            'propertyType': 'all'
        }
        
        response = client.get(search_url, params=search_params)
        
        if response.status_code == 200:
            content = response.text
            
            # Check for valid property indicators
            valid_indicators = [
                'Property Information',
                'Folio Number',
                'Owner Name',
                'Property Address'
            ]
            
            indicator_count = sum(1 for indicator in valid_indicators if indicator in content)
            
            if indicator_count >= 2:
                log_action(f"Parcel {parcel_id} validated at BCPA", "INFO", "VERIFIED")
                
                # Extract basic property info if possible
                property_info = {
                    'parcel_id': parcel_id,
                    'validated': True,
                    'source': 'bcpa_search',
                    'validated_at': datetime.now(timezone.utc).isoformat()
                }
                
                return property_info
            else:
                log_action(f"Parcel {parcel_id} not found at BCPA", "INFO", "VERIFIED")
                return {'parcel_id': parcel_id, 'validated': False}
        else:
            log_action(f"BCPA search failed for {parcel_id}: {response.status_code}", "WARN", "VERIFIED")
            return {'parcel_id': parcel_id, 'validated': False}
            
    except Exception as e:
        log_action(f"Validation error for {parcel_id}: {e}", "ERROR", "VERIFIED")
        return {'parcel_id': parcel_id, 'validated': False}

def link_auction_to_parcel(case_number: str, parcel_id: str) -> bool:
    """Update auction record with validated parcel_id"""
    updates = {
        'parcel_id': parcel_id,
        'parcel_source': 'bcpa_validated',
        'parcel_linked_at': datetime.now(timezone.utc).isoformat()
    }
    
    success = sb_update("multi_county_auctions", "case_number", case_number, updates)
    
    if success:
        log_action(f"Linked {case_number} -> parcel {parcel_id}", "INFO", "VERIFIED")
    else:
        log_action(f"Failed to link {case_number} -> parcel {parcel_id}", "ERROR", "VERIFIED")
    
    return success

def process_broward_parcel_linkage(max_auctions: int = 500) -> Dict[str, int]:
    """Main linkage processing for Broward auctions"""
    log_action(f"Starting Broward parcel linkage (max {max_auctions} auctions)...", "INFO", "UNTESTED")
    
    stats = {
        'auctions_processed': 0,
        'candidates_extracted': 0,
        'validations_attempted': 0,
        'successful_links': 0,
        'failed_validations': 0
    }
    
    # Process in batches to avoid overwhelming the API
    batch_size = 50
    total_processed = 0
    
    while total_processed < max_auctions:
        current_batch_size = min(batch_size, max_auctions - total_processed)
        
        # Get next batch of unlinked auctions
        auctions = get_unlinked_broward_auctions(current_batch_size)
        
        if not auctions:
            log_action("No more unlinked auctions found", "INFO", "VERIFIED")
            break
        
        for auction in auctions:
            case_number = auction.get('case_number', '')
            
            if not case_number:
                continue
            
            stats['auctions_processed'] += 1
            total_processed += 1
            
            # Extract parcel candidates
            candidates = extract_parcel_candidates(auction)
            stats['candidates_extracted'] += len(candidates)
            
            # Try each candidate until one validates
            linked = False
            for parcel_id in candidates:
                stats['validations_attempted'] += 1
                
                validation_result = validate_parcel_at_bcpa(parcel_id)
                
                if validation_result.get('validated'):
                    # Link this parcel to the auction
                    if link_auction_to_parcel(case_number, parcel_id):
                        stats['successful_links'] += 1
                        linked = True
                        break
                else:
                    stats['failed_validations'] += 1
                
                # Rate limiting
                time.sleep(BROWARD_PA_CONFIG['rate_limit_delay'])
            
            if not linked:
                log_action(f"No valid parcel found for {case_number}", "WARN", "VERIFIED")
        
        # Batch delay
        if len(auctions) == batch_size:
            log_action(f"Processed batch of {len(auctions)}, continuing...", "INFO", "VERIFIED")
            time.sleep(2)
        else:
            break
    
    # Calculate final stats
    success_rate = (stats['successful_links'] / stats['auctions_processed'] * 100) if stats['auctions_processed'] > 0 else 0
    
    log_action(f"Broward linkage completed:", "INFO", "VERIFIED")
    log_action(f"  Auctions processed: {stats['auctions_processed']}", "INFO", "VERIFIED")
    log_action(f"  Successful links: {stats['successful_links']}", "INFO", "VERIFIED") 
    log_action(f"  Success rate: {success_rate:.1f}%", "INFO", "VERIFIED")
    
    return stats

def verify_broward_linkage_improvement() -> Dict:
    """Verify current Broward parcel linkage percentage"""
    # Get total auctions
    total_params = "select=count&county=eq.broward"
    total_result = sb_query("multi_county_auctions", total_params)
    
    # Get linked auctions  
    linked_params = "select=count&county=eq.broward&parcel_id=not.is.null"
    linked_result = sb_query("multi_county_auctions", linked_params)
    
    if total_result and linked_result:
        total_count = total_result[0].get('count', 0)
        linked_count = linked_result[0].get('count', 0)
        
        linkage_pct = (linked_count / total_count * 100) if total_count > 0 else 0
        
        log_action(f"Current Broward linkage: {linkage_pct:.1f}% ({linked_count}/{total_count})", "INFO", "VERIFIED")
        
        return {
            'total_auctions': total_count,
            'linked_auctions': linked_count,
            'linkage_percentage': linkage_pct,
            'target_percentage': 95.0,
            'gap_to_target': 95.0 - linkage_pct
        }
    else:
        log_action("Failed to get linkage verification data", "ERROR", "VERIFIED")
        return {}

def main():
    """Main execution for Broward parcel linkage"""
    import argparse
    
    parser = argparse.ArgumentParser(description="SHARD-24 Broward Letter E Fix")
    parser.add_argument("--max-auctions", type=int, default=500, help="Max auctions to process")
    parser.add_argument("--verify-only", action="store_true", help="Only verify current status")
    args = parser.parse_args()
    
    if not SUPABASE_KEY:
        log_action("SUPABASE_KEY required", "ERROR", "VERIFIED")
        return 1
    
    log_action("Starting SHARD-24 Broward Letter E (parcel linkage) fix", "INFO", "VERIFIED")
    
    # Get baseline
    baseline = verify_broward_linkage_improvement()
    
    if args.verify_only:
        return 0
    
    if baseline.get('linkage_percentage', 0) >= 95.0:
        log_action("Broward already meets 95% linkage target", "INFO", "VERIFIED")
        return 0
    
    # Execute linkage improvement
    stats = process_broward_parcel_linkage(args.max_auctions)
    
    # Verify final status
    final_status = verify_broward_linkage_improvement()
    
    improvement = final_status.get('linkage_percentage', 0) - baseline.get('linkage_percentage', 0)
    log_action(f"Linkage improvement: +{improvement:.1f} percentage points", "INFO", "VERIFIED")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())