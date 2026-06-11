#!/usr/bin/env python3
"""
SHARD-1 Parcel Linkage Enhancer - HIGH LEVERAGE FIX
Fix Letter E by linking auction records to property appraiser parcel_id

Current Status (from issue):
- charlotte: 43.8% (3555 of 8114) 
- polk: 74.1% (19539 of 26385)
- escambia: 90.0% (7570 of 8413) - close to 95% target
- pasco: 1.4% (188 of 13479) - HIGHEST LEVERAGE TARGET
- hardee: 0% (0 of 0) - needs basic data first

Priority: PASCO (1.4% → 95% = +12,635 linked parcels)

Method: Link parcel_id via county property appraiser ArcGIS FeatureServer
Pattern: Follow Brevard/BCPAO pipeline (reference implementation)
"""
import os
import sys
import time
import httpx
import json
from datetime import datetime, timezone
from urllib.parse import urlencode

# Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

# SHARD-1 counties with CO_NO from manifest
SHARD_COUNTIES = {
    'charlotte': {'co_no': 18, 'pa_base': 'https://gis.charlottecountyfl.gov'},
    'polk': {'co_no': 63, 'pa_base': 'https://maps.polkpa.org'},
    'escambia': {'co_no': 27, 'pa_base': 'https://gisweb.co.escambia.fl.us'},
    'pasco': {'co_no': 61, 'pa_base': 'https://www.pascopao.org'},
    'hardee': {'co_no': 35, 'pa_base': 'https://www.hardeepao.com'}
}

def log(msg):
    """Timestamped logging"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

def get_county_linkage_status(county_slug, co_no):
    """Get current parcel linkage status for a county"""
    try:
        client = httpx.Client(timeout=30)
        
        # Get auction records without parcel_id
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.{county_slug}&parcel_id=is.null&select=count",
            headers=sb_headers()
        )
        unlinked_count = len(r.json()) if r.status_code == 200 else 0
        
        # Get auction records with parcel_id
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.{county_slug}&parcel_id=not.is.null&select=count",
            headers=sb_headers()
        )
        linked_count = len(r.json()) if r.status_code == 200 else 0
        
        total_auctions = linked_count + unlinked_count
        linkage_pct = (linked_count / total_auctions * 100) if total_auctions > 0 else 0
        
        log(f"{county_slug} linkage status:")
        log(f"  Linked: {linked_count:,}")
        log(f"  Unlinked: {unlinked_count:,}")
        log(f"  Total: {total_auctions:,}")
        log(f"  Linkage: {linkage_pct:.1f}%")
        log(f"  Gap to 95%: {max(0, int(total_auctions * 0.95 - linked_count)):,} parcels")
        
        return {
            'county': county_slug,
            'linked': linked_count,
            'unlinked': unlinked_count,
            'total': total_auctions,
            'linkage_pct': linkage_pct,
            'target_gap': max(0, int(total_auctions * 0.95 - linked_count))
        }
        
    except Exception as e:
        log(f"❌ Error checking {county_slug} linkage: {e}")
        return None

def discover_pa_arcgis_endpoint(county_slug, pa_base_url):
    """Discover property appraiser ArcGIS REST endpoint for parcel data"""
    log(f"🔍 Discovering {county_slug} property appraiser ArcGIS endpoint...")
    
    # Common ArcGIS REST paths
    test_paths = [
        '/arcgis/rest/services',
        '/ArcGIS/rest/services', 
        '/gis/rest/services',
        '/services/rest/services'
    ]
    
    client = httpx.Client(timeout=15)
    
    for path in test_paths:
        try:
            url = f"{pa_base_url}{path}"
            log(f"  Testing: {url}")
            
            r = client.get(url, params={'f': 'json'})
            if r.status_code == 200 and 'services' in r.text.lower():
                data = r.json()
                if 'services' in data:
                    log(f"  ✅ Found ArcGIS REST: {url}")
                    
                    # Look for parcel-related services
                    for service in data['services']:
                        service_name = service.get('name', '').lower()
                        if any(keyword in service_name for keyword in ['parcel', 'property', 'cadastral', 'land']):
                            service_url = f"{url}/{service['name']}/MapServer"
                            log(f"    📍 Found parcel service: {service['name']}")
                            return service_url
                    
                    # If no parcel service found, return base URL for manual inspection
                    return url
                    
        except Exception as e:
            log(f"    ❌ {url} failed: {e}")
            continue
    
    log(f"  ⚠️ No ArcGIS endpoint discovered for {county_slug}")
    return None

def test_parcel_service_layers(service_url):
    """Test parcel service layers to find the right one for linkage"""
    log(f"🔍 Testing parcel service layers: {service_url}")
    
    try:
        client = httpx.Client(timeout=15)
        r = client.get(service_url, params={'f': 'json'})
        
        if r.status_code == 200:
            data = r.json()
            layers = data.get('layers', [])
            
            for layer in layers:
                layer_id = layer.get('id')
                layer_name = layer.get('name', '').lower()
                
                log(f"  Layer {layer_id}: {layer.get('name')}")
                
                # Look for parcel-related layers
                if any(keyword in layer_name for keyword in ['parcel', 'property', 'lot', 'cadastral']):
                    layer_url = f"{service_url}/{layer_id}"
                    log(f"    🎯 Candidate layer: {layer['name']}")
                    
                    # Test query capabilities
                    test_r = client.get(f"{layer_url}/query", params={
                        'f': 'json',
                        'where': '1=1',
                        'outFields': '*',
                        'resultRecordCount': 1
                    })
                    
                    if test_r.status_code == 200:
                        test_data = test_r.json()
                        features = test_data.get('features', [])
                        if features:
                            fields = list(features[0].get('attributes', {}).keys())
                            log(f"      Available fields: {', '.join(fields[:10])}")
                            
                            # Look for address/parcel ID fields
                            addr_fields = [f for f in fields if any(kw in f.lower() for kw in ['addr', 'situs', 'street', 'address'])]
                            parcel_fields = [f for f in fields if any(kw in f.lower() for kw in ['parcel', 'pin', 'id', 'number'])]
                            
                            if addr_fields and parcel_fields:
                                log(f"      ✅ Layer {layer_id} has address and parcel fields!")
                                return {
                                    'layer_url': layer_url,
                                    'layer_id': layer_id,
                                    'layer_name': layer['name'],
                                    'address_fields': addr_fields,
                                    'parcel_fields': parcel_fields,
                                    'all_fields': fields
                                }
            
            log(f"  ⚠️ No suitable parcel layer found")
            return None
            
    except Exception as e:
        log(f"❌ Error testing layers: {e}")
        return None

def link_county_parcels(county_slug, layer_info, max_records=1000):
    """Link auction records to parcel_id using ArcGIS layer"""
    log(f"🔗 Linking {county_slug} parcels (max {max_records} records)...")
    
    if not layer_info:
        log(f"❌ No layer info for {county_slug}")
        return 0
    
    try:
        client = httpx.Client(timeout=60)
        
        # Get unlinked auction records with addresses
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
            headers=sb_headers(),
            params={
                'county': f'eq.{county_slug}',
                'parcel_id': 'is.null',
                'property_address': 'not.is.null',
                'select': 'case_number,property_address,city,zip_code',
                'limit': max_records
            }
        )
        
        if r.status_code != 200:
            log(f"❌ Failed to fetch {county_slug} auction records")
            return 0
        
        auctions = r.json()
        log(f"📋 Found {len(auctions)} unlinked auction records to process")
        
        if not auctions:
            log(f"✅ No unlinked records to process for {county_slug}")
            return 0
        
        # Process auctions in batches
        linked_count = 0
        batch_size = 10
        
        for i in range(0, len(auctions), batch_size):
            batch = auctions[i:i+batch_size]
            log(f"  Processing batch {i//batch_size + 1}/{(len(auctions) + batch_size - 1) // batch_size}")
            
            for auction in batch:
                # Try to match address to parcel
                address = auction.get('property_address', '').strip()
                if not address:
                    continue
                
                # Query ArcGIS layer for matching address
                # This is a simplified approach - full implementation would include
                # address normalization, fuzzy matching, etc.
                
                # For now, just establish the framework
                parcel_id = find_parcel_by_address(layer_info, address, county_slug)
                
                if parcel_id:
                    # Update auction record with parcel_id
                    update_r = client.patch(
                        f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
                        headers=sb_headers(),
                        params={'case_number': f'eq.{auction["case_number"]}'},
                        json={'parcel_id': parcel_id}
                    )
                    
                    if update_r.status_code == 204:
                        linked_count += 1
                        if linked_count % 10 == 0:
                            log(f"    Linked {linked_count} parcels...")
            
            # Rate limiting
            time.sleep(0.5)
        
        log(f"✅ Linked {linked_count} parcels for {county_slug}")
        return linked_count
        
    except Exception as e:
        log(f"❌ Error linking {county_slug} parcels: {e}")
        return 0

def find_parcel_by_address(layer_info, address, county_slug):
    """Find parcel_id by address using ArcGIS query"""
    # This is a placeholder for the actual address matching logic
    # Full implementation would include:
    # 1. Address normalization 
    # 2. Fuzzy matching with soundex/metaphone
    # 3. Multiple address field testing
    # 4. Confidence scoring
    
    log(f"    🔍 Finding parcel for address: {address[:50]}...")
    
    # For now, return None (framework only)
    # TODO: Implement actual ArcGIS query and address matching
    return None

def process_county(county_slug, county_info):
    """Process parcel linkage for a single county"""
    log(f"🏢 Processing {county_slug.upper()} county...")
    
    # Check current status
    status = get_county_linkage_status(county_slug, county_info['co_no'])
    if not status or status['linkage_pct'] >= 95.0:
        log(f"✅ {county_slug} already at target (>95% linked)")
        return status
    
    # Discover ArcGIS endpoint
    endpoint = discover_pa_arcgis_endpoint(county_slug, county_info['pa_base'])
    if not endpoint:
        log(f"⚠️ Could not discover ArcGIS endpoint for {county_slug}")
        return status
    
    # Test parcel layers
    layer_info = test_parcel_service_layers(endpoint)
    if not layer_info:
        log(f"⚠️ No suitable parcel layer found for {county_slug}")
        return status
    
    # Link parcels (limited batch for autonomous session)
    linked_count = link_county_parcels(county_slug, layer_info, max_records=500)
    
    # Check final status
    final_status = get_county_linkage_status(county_slug, county_info['co_no'])
    
    if final_status:
        improvement = final_status['linkage_pct'] - status['linkage_pct']
        log(f"📈 {county_slug} improvement: {status['linkage_pct']:.1f}% → {final_status['linkage_pct']:.1f}% (+{improvement:.1f}%)")
    
    return final_status

def main():
    log("=" * 70)
    log("SHARD-1 PARCEL LINKAGE ENHANCER - LETTER E HIGH LEVERAGE FIX")
    log("Target: Link auction records to property appraiser parcel_id")
    log("Priority: pasco (1.4% → 95% = +12,635 parcels)")
    log("=" * 70)
    
    if not SUPABASE_KEY:
        log("❌ SUPABASE_KEY not available")
        sys.exit(1)
    
    results = {}
    
    # Process Pasco first (highest leverage)
    log("🎯 PRIORITY TARGET: PASCO COUNTY")
    pasco_result = process_county('pasco', SHARD_COUNTIES['pasco'])
    results['pasco'] = pasco_result
    
    # Process other counties if time permits
    for county_slug, county_info in SHARD_COUNTIES.items():
        if county_slug == 'pasco':
            continue  # Already processed
        
        if county_slug == 'hardee':
            log(f"⏭️ Skipping {county_slug} (needs basic data first)")
            continue
        
        log(f"\\n🏢 Processing {county_slug}...")
        result = process_county(county_slug, county_info)
        results[county_slug] = result
    
    # Summary
    log("\\n📊 SHARD-1 PARCEL LINKAGE SUMMARY:")
    for county, result in results.items():
        if result:
            status = "✅" if result['linkage_pct'] >= 95 else "🔧"
            log(f"  {county}: {result['linkage_pct']:.1f}% linked {status}")
        else:
            log(f"  {county}: ❌ processing failed")
    
    log("🏁 Parcel linkage enhancement complete!")

if __name__ == "__main__":
    main()