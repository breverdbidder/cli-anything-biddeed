#!/usr/bin/env python3
"""
BREVARD & DUVAL PARCEL LINKAGE (E-lane Gold Standard)
Link auction properties to parcels via county property appraiser APIs

MISSION (from briefing):
- E: link parcel_id via county property appraiser ArcGIS FeatureServer  
- Brevard/BCPAO pipeline is reference implementation
- Dependency chain: E linkage -> I property cards -> J Shapira deal thesis

TARGETS:
- Brevard E=73.9% (need 95%+) - ~5,090 more parcel links needed
- Duval E=79.2% (need 95%+) - ~3,164 more parcel links needed

APPROACH:
1. Query multi_county_auctions for unlinked properties (parcel_id IS NULL)
2. Use property address to query county appraiser ArcGIS 
3. Match properties and update parcel_id field
4. Report exact counts for verification protocol
"""

import os
import sys
import json
import httpx
import asyncio
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
from urllib.parse import quote

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# County-specific ArcGIS endpoints
COUNTY_ENDPOINTS = {
    'brevard': {
        'name': 'Brevard County Property Appraiser',
        'arcgis_base': 'https://bcpao.maps.arcgis.com/sharing/rest',
        'search_url': 'https://bcpaweb.brevardfl.gov',  # BCPAO reference implementation
        'parcel_field': 'PARCEL_ID',
        'address_fields': ['SITE_ADDR', 'PROP_ADDR', 'MAIL_ADDR'],
        'api_type': 'bcpao'  # Use existing BCPAO bridge
    },
    'duval': {
        'name': 'Duval County Property Appraiser', 
        'arcgis_base': 'https://maps.coj.net/arcgis/rest/services',
        'search_url': 'https://paopropertysearch.coj.net',
        'parcel_field': 'PARCEL_ID',
        'address_fields': ['SITE_ADDR', 'PROP_ADDR', 'ADDR'],
        'api_type': 'arcgis'
    }
}

def normalize_address(address: str) -> str:
    """Normalize address for matching"""
    if not address:
        return ""
    
    # Remove common variations
    normalized = address.upper().strip()
    
    # Address standardization
    replacements = [
        (' STREET', ' ST'),
        (' AVENUE', ' AVE'), 
        (' BOULEVARD', ' BLVD'),
        (' DRIVE', ' DR'),
        (' COURT', ' CT'),
        (' ROAD', ' RD'),
        (' LANE', ' LN'),
        (' PLACE', ' PL'),
        (' CIRCLE', ' CIR'),
        (' NORTH ', ' N '),
        (' SOUTH ', ' S '),
        (' EAST ', ' E '),
        (' WEST ', ' W '),
    ]
    
    for old, new in replacements:
        normalized = normalized.replace(old, new)
    
    # Remove extra spaces and common noise
    normalized = re.sub(r'\s+', ' ', normalized)
    normalized = re.sub(r'[^\w\s]', ' ', normalized)
    
    return normalized.strip()

async def get_unlinked_auctions(county: str, limit: int = 1000) -> List[Dict]:
    """Get auction records that don't have parcel_id linked"""
    
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(
                f"{BASE}/multi_county_auctions",
                headers=HEADERS,
                params={
                    "select": "case_number,address,city,state,zip,latitude,longitude,parcel_id",
                    "county": f"eq.{county}",
                    "parcel_id": "is.null",
                    "address": "not.is.null", 
                    "limit": str(limit),
                    "order": "case_number"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"Found {len(data)} unlinked {county} auctions")
                return data
            else:
                print(f"❌ Failed to get unlinked auctions for {county}: {response.status_code}")
                return []
                
    except Exception as e:
        print(f"❌ Error getting unlinked auctions for {county}: {e}")
        return []

async def search_parcel_by_address_duval(address: str, city: str = "") -> Optional[str]:
    """Search for parcel ID in Duval using property search"""
    
    if not address:
        return None
        
    try:
        # Normalize the search address
        search_addr = normalize_address(f"{address} {city}".strip())
        
        # Use Duval property search API (discovered endpoint)
        async with httpx.AsyncClient(timeout=30) as client:
            search_url = "https://paopropertysearch.coj.net/api/search"
            
            response = await client.get(search_url, params={
                "address": search_addr,
                "limit": "5"
            })
            
            if response.status_code == 200:
                results = response.json()
                
                if results and len(results) > 0:
                    # Take the first match - could be refined with better matching
                    best_match = results[0]
                    parcel_id = best_match.get('parcel_id') or best_match.get('PARCEL_ID')
                    
                    if parcel_id:
                        return str(parcel_id).strip()
                        
    except Exception as e:
        print(f"⚠️ Duval parcel search error for '{address}': {e}")
        
    return None

async def search_parcel_by_address_brevard(address: str, city: str = "") -> Optional[str]:
    """Search for parcel ID in Brevard using BCPAO bridge pattern"""
    
    if not address:
        return None
        
    try:
        # Use BCPAO search endpoint (existing bridge implementation)
        search_addr = normalize_address(f"{address} {city}".strip())
        
        async with httpx.AsyncClient(timeout=30) as client:
            # BCPAO has a property search API
            search_url = "https://bcpaweb.brevardfl.gov/api/property/search"
            
            response = await client.get(search_url, params={
                "q": search_addr,
                "type": "address",
                "limit": "5"
            })
            
            if response.status_code == 200:
                results = response.json()
                
                if isinstance(results, list) and len(results) > 0:
                    best_match = results[0]
                    parcel_id = best_match.get('parcel_id') or best_match.get('PARCEL_ID')
                    
                    if parcel_id:
                        return str(parcel_id).strip()
                        
    except Exception as e:
        print(f"⚠️ Brevard parcel search error for '{address}': {e}")
        
    return None

async def link_parcels_for_county(county: str, batch_size: int = 50) -> Dict:
    """Link parcels for a specific county"""
    
    print(f"🔗 Starting parcel linkage for {county}")
    
    # Get unlinked auctions
    unlinked = await get_unlinked_auctions(county, limit=2000)
    
    if not unlinked:
        print(f"No unlinked auctions found for {county}")
        return {"processed": 0, "linked": 0, "county": county}
    
    linked_count = 0
    updates = []
    
    # Select appropriate search function
    if county == 'brevard':
        search_func = search_parcel_by_address_brevard
    elif county == 'duval':
        search_func = search_parcel_by_address_duval
    else:
        print(f"❌ No search implementation for {county}")
        return {"processed": 0, "linked": 0, "county": county, "error": "No implementation"}
    
    # Process in batches to avoid overwhelming APIs
    for i in range(0, len(unlinked), batch_size):
        batch = unlinked[i:i+batch_size]
        print(f"Processing batch {i//batch_size + 1}/{(len(unlinked) + batch_size - 1)//batch_size}")
        
        # Search for parcel IDs
        for auction in batch:
            case_number = auction['case_number']
            address = auction['address']
            city = auction.get('city', '')
            
            # Search for parcel
            parcel_id = await search_func(address, city)
            
            if parcel_id:
                updates.append({
                    'case_number': case_number,
                    'parcel_id': parcel_id
                })
                linked_count += 1
                
        # Small delay between batches to be respectful
        await asyncio.sleep(1)
    
    # Write updates to database
    if updates:
        success = await bulk_update_parcel_ids(updates)
        if success:
            print(f"✅ Successfully linked {linked_count} parcels for {county}")
        else:
            print(f"❌ Failed to update parcel IDs for {county}")
            linked_count = 0
    
    return {
        "processed": len(unlinked),
        "linked": linked_count, 
        "county": county,
        "updates": len(updates)
    }

async def bulk_update_parcel_ids(updates: List[Dict]) -> bool:
    """Update parcel IDs in multi_county_auctions table"""
    
    if not updates:
        return True
        
    try:
        # Use individual updates for now - could optimize with bulk UPSERT
        async with httpx.AsyncClient(timeout=120) as client:
            for update in updates:
                response = await client.patch(
                    f"{BASE}/multi_county_auctions",
                    headers=HEADERS,
                    params={"case_number": f"eq.{update['case_number']}"},
                    json={"parcel_id": update['parcel_id']}
                )
                
                if response.status_code not in [200, 204]:
                    print(f"⚠️ Failed to update {update['case_number']}: {response.status_code}")
                    
        return True
        
    except Exception as e:
        print(f"❌ Error updating parcel IDs: {e}")
        return False

async def verify_linkage_improvement(county: str) -> Dict:
    """Verify the linkage improvement for county"""
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # Get total auction count
            total_response = await client.get(
                f"{BASE}/multi_county_auctions",
                headers=HEADERS,
                params={"select": "count", "county": f"eq.{county}"}
            )
            
            # Get linked count  
            linked_response = await client.get(
                f"{BASE}/multi_county_auctions", 
                headers=HEADERS,
                params={
                    "select": "count",
                    "county": f"eq.{county}",
                    "parcel_id": "not.is.null"
                }
            )
            
            if total_response.status_code == 200 and linked_response.status_code == 200:
                total_data = total_response.json()
                linked_data = linked_response.json()
                
                total_count = len(total_data) if isinstance(total_data, list) else total_data.get('count', 0)
                linked_count = len(linked_data) if isinstance(linked_data, list) else linked_data.get('count', 0)
                
                percentage = (linked_count / total_count * 100) if total_count > 0 else 0
                
                return {
                    'county': county,
                    'total_auctions': total_count,
                    'linked_auctions': linked_count,
                    'linkage_percentage': round(percentage, 1),
                    'verified': True
                }
            else:
                return {'county': county, 'verified': False, 'error': 'Failed to get counts'}
                
    except Exception as e:
        return {'county': county, 'verified': False, 'error': str(e)}

async def main():
    """Main execution function"""
    
    print("🔗 BREVARD & DUVAL PARCEL LINKAGE (E-lane Gold Standard)")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}\n")
    
    target_counties = ['brevard', 'duval']
    results = {}
    
    # Process each county
    for county in target_counties:
        print(f"\n{'='*60}")
        print(f"PROCESSING {county.upper()}")
        print(f"{'='*60}")
        
        # Link parcels
        result = await link_parcels_for_county(county, batch_size=25)
        results[county] = result
        
        # Verify improvement
        verification = await verify_linkage_improvement(county)
        results[county]['verification'] = verification
        
        print(f"\n📊 {county.upper()} RESULTS:")
        print(f"  - Processed: {result['processed']}")
        print(f"  - Linked: {result['linked']}")
        
        if verification.get('verified'):
            print(f"  - Total auctions: {verification['total_auctions']}")
            print(f"  - Linked auctions: {verification['linked_auctions']}")
            print(f"  - Linkage percentage: {verification['linkage_percentage']}%")
            
            target_pct = 95.0
            if verification['linkage_percentage'] >= target_pct:
                print(f"  ✅ GOLD STANDARD MET ({target_pct}%+)")
            else:
                gap = target_pct - verification['linkage_percentage']
                print(f"  📈 Progress toward gold standard (need +{gap:.1}% more)")
    
    # Final summary
    print(f"\n{'='*60}")
    print("PARCEL LINKAGE SESSION SUMMARY")
    print(f"{'='*60}")
    
    total_processed = sum(r['processed'] for r in results.values())
    total_linked = sum(r['linked'] for r in results.values())
    
    print(f"Total processed: {total_processed}")
    print(f"Total linked: {total_linked}")
    print(f"Success rate: {(total_linked/total_processed*100):.1f}%" if total_processed > 0 else "N/A")
    
    # Output SQL verification
    print(f"\n### SQL VERIFICATION")
    print(f"```sql")
    for county in target_counties:
        print(f"-- {county.upper()} linkage verification")
        print(f"SELECT ")
        print(f"  COUNT(*) as total_auctions,")
        print(f"  COUNT(parcel_id) as linked_auctions,")
        print(f"  ROUND(COUNT(parcel_id) * 100.0 / COUNT(*), 1) as linkage_percentage")
        print(f"FROM multi_county_auctions WHERE county = '{county}';")
        print(f"")
    
    print(f"-- Run county evaluations")
    for county in target_counties:
        print(f"SELECT public.pencil_dod_evaluate_county('{county}');")
    print(f"```")
    
    print(f"\n💡 IMPACT: Improved E linkage feeds I (property cards) and J (Shapira deal thesis)")
    print(f"💡 NEXT: Run verification protocol to confirm E, I, J letter improvements")

if __name__ == "__main__":
    asyncio.run(main())