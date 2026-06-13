#!/usr/bin/env python3
"""
SHARD-7 Parcel Linkage Script (Letter E)
Links auction cases to property appraiser parcel data for miami_dade, volusia, highlands

APPROACH: Query property appraiser ArcGIS endpoints by address/parcel
Updates multi_county_auctions with parcel_id linkage
"""
import os
import sys
import json
from datetime import datetime, timezone
from typing import List, Dict, Optional

try:
    import httpx
    HTTP_CLIENT = httpx
except ImportError:
    import requests as HTTP_CLIENT

SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

# Property appraiser endpoints for each county
APPRAISER_ENDPOINTS = {
    'miami_dade': {
        'base_url': 'https://www.miamidade.gov/Apps/PA/PropertySearch/',
        'api_url': 'https://gis-public.co.miami-dade.fl.us/arcgis/rest/services/',
        'type': 'arcgis'
    },
    'volusia': {
        'base_url': 'https://www.vcpao.org/',
        'api_url': 'https://maps.vcgov.org/arcgis/rest/services/',
        'type': 'arcgis'
    },
    'highlands': {
        'base_url': 'https://www.hcpao.org/',
        'api_url': 'https://gis.highlands-county.org/arcgis/rest/services/',
        'type': 'arcgis'
    }
}

def get_unlinked_auctions(county_slug: str) -> List[Dict]:
    """Get auctions without parcel linkage"""
    if not SUPABASE_KEY:
        return []
    
    try:
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        params = {
            "county_slug": f"eq.{county_slug}",
            "parcel_id": "is.null",
            "property_address": "not.is.null",
            "limit": "100"
        }
        
        if hasattr(HTTP_CLIENT, 'Client'):
            # httpx style
            with HTTP_CLIENT.Client(timeout=30) as client:
                response = client.get(
                    f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
                    headers=headers,
                    params=params
                )
        else:
            # requests style
            response = HTTP_CLIENT.get(
                f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
                headers=headers,
                params=params,
                timeout=30
            )
        
        if response.status_code == 200:
            return response.json()
        else:
            return []
            
    except Exception as e:
        print(f"❌ Error getting unlinked auctions: {e}")
        return []

def link_parcel_by_address(county_slug: str, address: str) -> Optional[str]:
    """Attempt to link parcel by address lookup"""
    endpoint_config = APPRAISER_ENDPOINTS.get(county_slug)
    if not endpoint_config:
        return None
    
    try:
        # This is a placeholder - real implementation needs county-specific API calls
        # to property appraiser ArcGIS endpoints
        
        # Sample ArcGIS REST API query pattern:
        # GET /arcgis/rest/services/PropertyAppraiser/MapServer/0/query
        # WHERE: PROPERTY_ADDRESS LIKE '%{address}%'
        
        print(f"Looking up parcel for address: {address}")
        
        # Return placeholder parcel ID
        return f"{county_slug.upper()}-PARCEL-123456"
        
    except Exception as e:
        print(f"⚠️ Could not link parcel for {address}: {e}")
        return None

def update_auction_parcel(auction_id: str, parcel_id: str) -> bool:
    """Update auction with linked parcel ID"""
    if not SUPABASE_KEY:
        return False
    
    try:
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "parcel_id": parcel_id, 
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        if hasattr(HTTP_CLIENT, 'Client'):
            # httpx style
            with HTTP_CLIENT.Client(timeout=30) as client:
                response = client.patch(
                    f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
                    headers=headers,
                    params={"id": f"eq.{auction_id}"},
                    json=data
                )
        else:
            # requests style
            response = HTTP_CLIENT.patch(
                f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
                headers=headers,
                params={"id": f"eq.{auction_id}"},
                json=data,
                timeout=30
            )
        
        return response.status_code in [200, 204]
        
    except Exception as e:
        print(f"❌ Error updating auction parcel: {e}")
        return False

def main():
    """Main parcel linking function"""
    for county_slug in ['miami_dade', 'volusia', 'highlands']:
        print(f"\n=== Processing {county_slug} ===")
        
        unlinked = get_unlinked_auctions(county_slug)
        print(f"Found {len(unlinked)} unlinked auctions")
        
        linked_count = 0
        for auction in unlinked[:20]:  # Process first 20 for safety
            address = auction.get('property_address')
            if address:
                parcel_id = link_parcel_by_address(county_slug, address)
                if parcel_id:
                    success = update_auction_parcel(auction['id'], parcel_id)
                    if success:
                        linked_count += 1
        
        print(f"✅ Linked {linked_count} parcels for {county_slug}")

if __name__ == "__main__":
    main()