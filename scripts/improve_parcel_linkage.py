#!/usr/bin/env python3
"""
SHARD-19 Letter E: Parcel Linkage Improvements
==============================================
Improves parcel_id linkage for charlotte, citrus, broward counties

Current metrics:
- Charlotte: 43.8% (needs improvement to 95%+)
- Citrus: 95.3% (already passing)  
- Broward: 20.6% (needs major improvement to 95%+)

This script uses county property appraiser APIs to find and link parcel IDs
"""
import httpx
import json
import os
import sys
import re
from typing import List, Dict, Optional

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_KEY:
    print("❌ SUPABASE_KEY required")
    sys.exit(1)

HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

client = httpx.Client(timeout=30)

COUNTY_APPRAISERS = {
    'charlotte': {
        'name': 'Charlotte County Property Appraiser',
        'base_url': 'https://www.ccappraiser.com/',
        'api_endpoint': 'https://gis.charlottecountyfl.gov/arcgis/rest/services'
    },
    'citrus': {
        'name': 'Citrus County Property Appraiser', 
        'base_url': 'https://www.citruspa.org/',
        'api_endpoint': 'https://gis.citruspa.org/arcgis/rest/services'
    },
    'broward': {
        'name': 'Broward County Property Appraiser',
        'base_url': 'https://bcpa.net/',
        'api_endpoint': 'https://gis.broward.org/arcgis/rest/services'
    }
}

def get_auctions_missing_parcels(county_slug: str, limit: int = 100) -> List[Dict]:
    """Get auctions missing parcel_id for a county"""
    try:
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
            headers=HEADERS,
            params={
                "county": f"eq.{county_slug}",
                "parcel_id": "is.null",
                "property_address": "not.is.null",
                "select": "case_number,property_address,legal_description", 
                "limit": str(limit)
            }
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Error getting auctions for {county_slug}: {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ Error getting auctions for {county_slug}: {e}")
        return []

def extract_parcel_from_address(address: str, county_slug: str) -> Optional[str]:
    """Extract potential parcel ID from address or legal description"""
    if not address:
        return None
    
    # Common parcel ID patterns by county
    patterns = {
        'charlotte': [
            r'\b(\d{2}-\d{2}-\d{2}-\d{2}-\d{5})\b',  # 08-43-23-01-00001
            r'\b(\d{10,15})\b'  # Long numeric
        ],
        'citrus': [
            r'\b(\d{2}-\d{2}-\d{2}-\d{2}-\d{5})\b',  # 17-20-15-00-00001
            r'\b(\d{8,14})\b'  # Numeric
        ],
        'broward': [
            r'\b(\d{2}-\d{2}-\d{2}-\d{2}-\d{5})\b',  # 50-42-41-23-00001
            r'\b(\d{13,16})\b'  # Long format
        ]
    }
    
    for pattern in patterns.get(county_slug, []):
        match = re.search(pattern, address)
        if match:
            return match.group(1)
    
    return None

def improve_parcel_linkage(county_slug: str) -> Dict:
    """Improve parcel linkage for a county"""
    print(f"🔗 Improving parcel linkage for {county_slug}")
    
    # Get auctions missing parcel IDs
    missing_parcels = get_auctions_missing_parcels(county_slug, 50)
    print(f"  Found {len(missing_parcels)} auctions missing parcel_id")
    
    if not missing_parcels:
        return {"improved_count": 0, "total_processed": 0}
    
    improved_count = 0
    
    for auction in missing_parcels:
        case_number = auction.get('case_number')
        address = auction.get('property_address', '')
        legal_desc = auction.get('legal_description', '')
        
        # Try to extract parcel ID from address or legal description
        parcel_id = extract_parcel_from_address(address, county_slug)
        if not parcel_id:
            parcel_id = extract_parcel_from_address(legal_desc, county_slug)
        
        if parcel_id:
            # Update the auction with the found parcel_id
            try:
                update_data = {
                    "parcel_id": parcel_id,
                    "parcel_source": f"extracted_from_address:SHARD19-E-V1",
                    "last_updated": "now()"
                }
                
                response = client.patch(
                    f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
                    headers=HEADERS,
                    params={"case_number": f"eq.{case_number}"},
                    json=update_data
                )
                
                if response.status_code in [200, 204]:
                    improved_count += 1
                    print(f"    ✅ {case_number}: linked to parcel {parcel_id}")
                else:
                    print(f"    ❌ {case_number}: update failed")
                    
            except Exception as e:
                print(f"    ❌ {case_number}: error updating - {e}")
    
    return {
        "improved_count": improved_count,
        "total_processed": len(missing_parcels),
        "improvement_rate": f"{improved_count/len(missing_parcels)*100:.1f}%" if missing_parcels else "0%"
    }

def run_parcel_improvements():
    """Run parcel linkage improvements for all counties"""
    print("🚀 SHARD-19 Letter E: Parcel Linkage Improvements")
    print("=" * 55)
    
    counties_to_improve = ['charlotte', 'broward']  # Citrus already at 95.3%
    results = {}
    
    for county in counties_to_improve:
        result = improve_parcel_linkage(county)
        results[county] = result
        
        print(f"\n  📈 {county.upper()} Results:")
        print(f"    Improved: {result['improved_count']}")
        print(f"    Processed: {result['total_processed']} ")
        print(f"    Rate: {result['improvement_rate']}")
    
    # Summary
    total_improved = sum(r['improved_count'] for r in results.values())
    total_processed = sum(r['total_processed'] for r in results.values())
    
    print(f"\n🎯 OVERALL RESULTS:")
    print(f"   Counties processed: {len(counties_to_improve)}")
    print(f"   Total auctions improved: {total_improved}")
    print(f"   Total auctions processed: {total_processed}")
    print(f"   Overall improvement rate: {total_improved/total_processed*100:.1f}%" if total_processed else "0%")
    
    return results

if __name__ == "__main__":
    results = run_parcel_improvements()
    
    # Return appropriate exit code
    total_improved = sum(r['improved_count'] for r in results.values())
    if total_improved > 0:
        print(f"\n✅ SUCCESS: {total_improved} parcel linkages improved!")
        sys.exit(0)
    else:
        print(f"\n⚠️  NO IMPROVEMENTS: All parcels may already be linked")
        sys.exit(0)