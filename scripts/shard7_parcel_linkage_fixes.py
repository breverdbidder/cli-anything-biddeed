#!/usr/bin/env python3
"""
SHARD-7 Criterion E Fixes: Parcel Linkage for manatee and okaloosa
Addresses high-leverage failing criteria E (parcel linkage >=95%)

Current status:
- manatee: 87.9% (3961/4504) - need ~300 more links  
- okaloosa: 74.9% (1509/2016) - need ~507 more links

Strategy: Use county appraiser APIs to match addresses/case numbers to parcel IDs

Usage:
  python scripts/shard7_parcel_linkage_fixes.py --county manatee
  python scripts/shard7_parcel_linkage_fixes.py --county okaloosa
  python scripts/shard7_parcel_linkage_fixes.py --all
"""
import os
import sys
import httpx
import json
from datetime import datetime
import argparse
import re

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# County-specific parcel linkage configurations
COUNTY_CONFIGS = {
    'manatee': {
        'co_no': 41,
        'appraiser_url': 'https://www.manateecounty.com/assessor',
        'parcel_search_api': 'https://gis.mymanatee.org/arcgis/rest/services/PropertyInfo/MapServer/0/query',
        'search_fields': ['property_address', 'owner_name'],
        'current_linked': 3961,
        'total_auctions': 4504,
        'target_percentage': 95.0,
        'needed_links': 323  # (4504 * 0.95) - 3961
    },
    'okaloosa': {
        'co_no': 46, 
        'appraiser_url': 'https://www.okaloosaappraiser.com',
        'parcel_search_api': 'https://gis.okaloosa.fl.us/arcgis/rest/services/PublicWebsite/Parcels/MapServer/0/query',
        'search_fields': ['property_address', 'owner_name'],
        'current_linked': 1509,
        'total_auctions': 2016,
        'target_percentage': 95.0,
        'needed_links': 407  # (2016 * 0.95) - 1509
    }
}

def log_with_timestamp(message):
    """Add timestamp to all log messages"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")

def get_supabase_headers():
    """Get standard Supabase headers"""
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def get_unlinked_auctions(county_slug, limit=500):
    """Get auctions without parcel_id linkage"""
    try:
        client = httpx.Client(timeout=60)
        headers = get_supabase_headers()
        
        # Get auctions missing parcel_id
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
            headers=headers,
            params={
                "select": "id,case_number,property_address,owner_name,county",
                "county": f"eq.{county_slug}",
                "parcel_id": "is.null",
                "limit": str(limit),
                "order": "created_at.desc"
            }
        )
        
        if response.status_code == 200:
            unlinked = response.json()
            log_with_timestamp(f"📋 Found {len(unlinked)} unlinked auctions for {county_slug}")
            client.close()
            return unlinked
        else:
            log_with_timestamp(f"❌ Error fetching unlinked auctions: {response.status_code}")
            client.close()
            return []
            
    except Exception as e:
        log_with_timestamp(f"❌ Error fetching unlinked auctions: {e}")
        return []

def search_parcel_by_address(county_slug, address, config):
    """Search for parcel ID by address using county appraiser API"""
    if not address or len(address.strip()) < 10:
        return None
    
    try:
        client = httpx.Client(timeout=30)
        
        # Clean address for search
        clean_address = re.sub(r'[^\w\s]', ' ', address.upper().strip())
        clean_address = ' '.join(clean_address.split())  # Normalize whitespace
        
        # Try ArcGIS REST query if available
        if config.get('parcel_search_api'):
            search_params = {
                'where': f"UPPER(ADDRESS) LIKE '%{clean_address[:50]}%'",
                'outFields': 'PARCEL_ID,PARCEL_NO,ADDRESS,OWNER',
                'returnGeometry': 'false',
                'f': 'json',
                'resultRecordCount': '5'
            }
            
            response = client.get(config['parcel_search_api'], params=search_params)
            
            if response.status_code == 200:
                data = response.json()
                features = data.get('features', [])
                
                if features:
                    # Return the best match (first result)
                    attrs = features[0].get('attributes', {})
                    parcel_id = attrs.get('PARCEL_ID') or attrs.get('PARCEL_NO')
                    
                    if parcel_id:
                        log_with_timestamp(f"   ✅ Found parcel: {parcel_id} for {address[:50]}...")
                        client.close()
                        return str(parcel_id).strip()
        
        client.close()
        return None
        
    except Exception as e:
        log_with_timestamp(f"   ❌ Error searching parcel for {address[:30]}: {e}")
        return None

def update_auction_parcel_id(auction_id, parcel_id):
    """Update multi_county_auctions with found parcel_id"""
    try:
        client = httpx.Client(timeout=30)
        headers = get_supabase_headers()
        
        response = client.patch(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions?id=eq.{auction_id}",
            headers=headers,
            json={"parcel_id": parcel_id, "updated_at": datetime.utcnow().isoformat()}
        )
        
        if response.status_code == 200:
            client.close()
            return True
        else:
            log_with_timestamp(f"❌ Error updating auction {auction_id}: {response.status_code}")
            client.close()
            return False
            
    except Exception as e:
        log_with_timestamp(f"❌ Error updating auction {auction_id}: {e}")
        return False

def fix_parcel_linkage(county_slug):
    """Main function to fix parcel linkage for a county"""
    if county_slug not in COUNTY_CONFIGS:
        log_with_timestamp(f"❌ Unknown county: {county_slug}")
        return False
    
    config = COUNTY_CONFIGS[county_slug]
    log_with_timestamp(f"🎯 Fixing criterion E for {county_slug.upper()}")
    log_with_timestamp(f"   Current: {config['current_linked']:,}/{config['total_auctions']:,} "
                      f"({config['current_linked']/config['total_auctions']*100:.1f}%)")
    log_with_timestamp(f"   Target: {config['target_percentage']:.1f}% "
                      f"({int(config['total_auctions'] * config['target_percentage']/100):,} auctions)")
    log_with_timestamp(f"   Need: {config['needed_links']} more parcel linkages")
    
    # Get unlinked auctions
    unlinked_auctions = get_unlinked_auctions(county_slug, limit=config['needed_links'] + 100)
    
    if not unlinked_auctions:
        log_with_timestamp("❌ No unlinked auctions found")
        return False
    
    log_with_timestamp(f"🔍 Processing {min(len(unlinked_auctions), config['needed_links'])} auctions...")
    
    success_count = 0
    batch_size = 20
    
    for i, auction in enumerate(unlinked_auctions[:config['needed_links']]):
        if i > 0 and i % batch_size == 0:
            log_with_timestamp(f"   Progress: {i}/{len(unlinked_auctions)} processed, {success_count} linked")
        
        address = auction.get('property_address', '').strip()
        if not address:
            continue
        
        # Search for parcel ID
        parcel_id = search_parcel_by_address(county_slug, address, config)
        
        if parcel_id:
            # Update the auction record
            if update_auction_parcel_id(auction['id'], parcel_id):
                success_count += 1
                
                # Check if we've reached our target
                current_percentage = (config['current_linked'] + success_count) / config['total_auctions'] * 100
                if current_percentage >= config['target_percentage']:
                    log_with_timestamp(f"🎯 Target reached! {current_percentage:.1f}% >= {config['target_percentage']:.1f}%")
                    break
    
    final_percentage = (config['current_linked'] + success_count) / config['total_auctions'] * 100
    
    log_with_timestamp(f"✅ Linkage fix complete for {county_slug}")
    log_with_timestamp(f"   Linked: {success_count} new parcels")
    log_with_timestamp(f"   Final: {config['current_linked'] + success_count:,}/{config['total_auctions']:,} "
                      f"({final_percentage:.1f}%)")
    
    criterion_e_pass = final_percentage >= config['target_percentage']
    log_with_timestamp(f"   Criterion E: {'✅ PASS' if criterion_e_pass else '❌ FAIL'}")
    
    return criterion_e_pass

def main():
    parser = argparse.ArgumentParser(description='Fix parcel linkage for Gold Standard criterion E')
    parser.add_argument('--county', help='County to fix (manatee, okaloosa)')
    parser.add_argument('--all', action='store_true', help='Fix all target counties')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done')
    
    args = parser.parse_args()
    
    log_with_timestamp("=" * 70)
    log_with_timestamp("SHARD-7 CRITERION E FIXES: Parcel Linkage")
    log_with_timestamp("=" * 70)
    
    if not SUPABASE_KEY:
        log_with_timestamp("❌ SUPABASE_KEY environment variable not set")
        sys.exit(1)
    
    counties_to_fix = []
    if args.all:
        counties_to_fix = ['manatee', 'okaloosa']
    elif args.county:
        counties_to_fix = [args.county.lower()]
    else:
        log_with_timestamp("❌ Must specify --county or --all")
        sys.exit(1)
    
    log_with_timestamp(f"📋 Counties to fix: {', '.join(counties_to_fix)}")
    
    if args.dry_run:
        log_with_timestamp("🔍 DRY RUN - showing planned fixes:")
        for county_slug in counties_to_fix:
            config = COUNTY_CONFIGS[county_slug]
            log_with_timestamp(f"  {county_slug}: Need {config['needed_links']} linkages via {config['appraiser_url']}")
        return
    
    success_count = 0
    for county_slug in counties_to_fix:
        log_with_timestamp(f"\n" + "-" * 50)
        success = fix_parcel_linkage(county_slug)
        if success:
            success_count += 1
    
    log_with_timestamp(f"\n🏆 Parcel linkage fixes complete: {success_count}/{len(counties_to_fix)} counties")
    
    if success_count > 0:
        log_with_timestamp(f"\n📋 Next steps:")
        log_with_timestamp(f"  1. Verify with SELECT public.pencil_dod_evaluate_county('<county>');")
        log_with_timestamp(f"  2. Check that parcel linkage >= 95% for criterion E")
        log_with_timestamp(f"  3. Note: Fixed parcels become eligible for comps pipeline (criterion J)")

if __name__ == "__main__":
    main()