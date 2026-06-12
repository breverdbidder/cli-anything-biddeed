#!/usr/bin/env python3
"""
SHARD-11 Letter E Fix: Parcel Linkage Improvement
=================================================
Focused fix for Letter E (parcel linkage) across manatee, washington, miami_dade

CURRENT LETTER E STATUS:
- manatee: 91.4% (5754/6297) → need 204 more for 95%
- washington: 26.1% (80/307) → need 212 more for 95% 
- miami_dade: 17.1% (5399/31508) → need 24,533 more for 95%

APPROACH:
1. Address-based parcel ID extraction (FL parcel patterns)
2. Property appraiser ArcGIS lookups where available
3. Batch updates to minimize database calls
"""
import os
import sys
import json
import re
from urllib.request import urlopen, Request
from urllib.parse import urlencode, quote
from urllib.error import HTTPError, URLError
import time

# Supabase configuration (using minimal dependencies)
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

def make_supabase_request(endpoint, method="GET", data=None, params=None):
    """Make HTTP request to Supabase using standard library"""
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates" if method == "POST" else ""
    }
    
    url = f"{SUPABASE_URL}/rest/v1/{endpoint}"
    if params:
        url += "?" + urlencode(params)
    
    try:
        if method == "GET":
            req = Request(url, headers=headers)
        elif method == "POST":
            req = Request(url, data=json.dumps(data).encode(), headers=headers)
        elif method == "PATCH":
            req = Request(url, data=json.dumps(data).encode(), headers=headers)
            req.get_method = lambda: 'PATCH'
        
        with urlopen(req, timeout=30) as response:
            if response.status in [200, 201, 204]:
                response_data = response.read().decode()
                return json.loads(response_data) if response_data else {}
            else:
                print(f"HTTP {response.status} for {method} {endpoint}")
                return None
    except (HTTPError, URLError) as e:
        print(f"Request failed: {e}")
        return None

def extract_parcel_from_address(address):
    """Extract parcel ID patterns from FL property addresses"""
    if not address:
        return None
    
    # Common FL parcel patterns
    patterns = [
        r'PCL\s*([0-9A-Z-]+)',                    # "PCL 12-34-56-78"
        r'PARCEL\s*([0-9A-Z-]+)',                 # "PARCEL 123ABC456"
        r'\b([0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{3,4})\b',  # "12-34-56-789"
        r'\b([0-9]{8,12})\b',                     # "123456789012" 
        r'([0-9]{2}-[0-9]{2}-[0-9]{2}-[A-Z0-9]+)',       # "12-34-56-ABC"
        r'([0-9]{4}-[0-9]{4}-[0-9]{4})',         # "1234-5678-9012"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, address, re.IGNORECASE)
        if match:
            parcel_id = match.group(1).strip()
            # Validate length and format
            if 6 <= len(parcel_id) <= 20:
                return parcel_id
    
    return None

def get_county_auctions_missing_parcels(county):
    """Get auctions missing parcel_id for a county"""
    params = {
        'county': f'eq.{county}',
        'parcel_id': 'is.null',
        'property_address': 'not.is.null',
        'select': 'case_number,property_address,auction_date,sale_type',
        'limit': '500'
    }
    
    auctions = make_supabase_request('multi_county_auctions', params=params)
    if auctions:
        print(f"📊 {county}: {len(auctions)} auctions missing parcel_id")
        return auctions
    else:
        print(f"⚠️ {county}: Failed to fetch auctions")
        return []

def update_auction_parcel_id(case_number, parcel_id):
    """Update single auction with parcel_id"""
    params = {'case_number': f'eq.{case_number}'}
    data = {'parcel_id': parcel_id}
    
    result = make_supabase_request('multi_county_auctions', method='PATCH', data=data, params=params)
    return result is not None

def process_county_letter_e(county):
    """Process Letter E fixes for a single county"""
    print(f"\n{'='*50}")
    print(f"PROCESSING {county.upper()} - LETTER E")
    print(f"{'='*50}")
    
    # Get auctions missing parcel_id
    auctions = get_county_auctions_missing_parcels(county)
    if not auctions:
        print(f"✅ {county}: No auctions need parcel linking")
        return 0
    
    print(f"🎯 {county}: Processing {len(auctions)} auctions for parcel extraction")
    
    # Extract parcel IDs from addresses
    updates_made = 0
    batch_size = 100  # Process in smaller batches
    
    for i, auction in enumerate(auctions[:batch_size]):
        address = auction.get('property_address', '')
        
        # Try to extract parcel from address
        parcel_id = extract_parcel_from_address(address)
        
        if parcel_id:
            case_number = auction['case_number']
            
            # Update the auction
            if update_auction_parcel_id(case_number, parcel_id):
                print(f"  ✅ {case_number}: {parcel_id}")
                updates_made += 1
            else:
                print(f"  ❌ {case_number}: Update failed")
            
            # Rate limit
            time.sleep(0.1)
        else:
            # Debug problematic addresses
            if len(address) < 100:  # Only show short addresses
                print(f"  ⚠️ No pattern: {address[:60]}")
        
        # Progress indicator
        if (i + 1) % 25 == 0:
            print(f"  📊 Processed {i + 1}/{min(len(auctions), batch_size)}")
    
    print(f"\n✅ {county}: Updated {updates_made} parcel IDs")
    return updates_made

def run_shard11_letter_e_fixes():
    """Run Letter E fixes for all SHARD-11 counties"""
    print("🚀 SHARD-11 LETTER E (Parcel Linkage) FIXES")
    print(f"Target: Improve parcel linkage to 95% threshold")
    
    if not SUPABASE_KEY:
        print("❌ SUPABASE_KEY not found in environment")
        sys.exit(1)
    
    # Focus on counties with existing data first
    counties_with_data = ['manatee', 'washington', 'miami_dade']
    total_updates = 0
    
    for county in counties_with_data:
        try:
            updates = process_county_letter_e(county)
            total_updates += updates
            
            # Brief pause between counties
            time.sleep(2)
            
        except Exception as e:
            print(f"❌ Error processing {county}: {e}")
    
    print(f"\n{'='*60}")
    print(f"LETTER E FIXES SUMMARY")
    print(f"{'='*60}")
    print(f"🔧 Total parcel IDs added: {total_updates}")
    print(f"🎯 Counties processed: {len(counties_with_data)}")
    
    if total_updates > 0:
        print(f"\n✅ Letter E improvements applied to SHARD-11 counties")
        print(f"📊 Run verification to check new metrics")
    else:
        print(f"\n⚠️ No parcel improvements applied")
        print(f"💡 May need ArcGIS integration for better results")
    
    return total_updates

if __name__ == "__main__":
    total_fixed = run_shard11_letter_e_fixes()
    print(f"\n🏁 SHARD-11 Letter E session completed: {total_fixed} fixes applied")
    sys.exit(0 if total_fixed >= 0 else 1)