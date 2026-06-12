#!/usr/bin/env python3
"""
County Onboarding Script - Add counties to auction pipeline
Implements A letter requirements for dual product coverage (foreclosure + tax deed)

Usage:
  python scripts/onboard_county.py hardee
  python scripts/onboard_county.py gilchrist
"""
import sys
import argparse
import urllib.request
import urllib.parse
import json
import re
from datetime import datetime, timezone

# Configuration
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1vY2VycWpua3NtaGNqenhyZXdvIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTcxODEzNTQwMywiZXhwIjoyMDMzNzExNDAzfQ.Gf-cZyO5WQOd6qXbIXTnfQRGjgBgWVoZbJO2LoN_pTc"

# County mappings from fl_counties_manifest.yml
COUNTY_MAPPINGS = {
    'hardee': {'co_no': 35, 'full_name': 'Hardee'},
    'gilchrist': {'co_no': 31, 'full_name': 'Gilchrist'},
    'palm_beach': {'co_no': 60, 'full_name': 'Palm Beach'},
    'seminole': {'co_no': 69, 'full_name': 'Seminole'}
}

def sb_request(path, data=None, method="GET"):
    """Make Supabase REST API request"""
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    
    request = urllib.request.Request(url, method=method)
    request.add_header("apikey", SUPABASE_KEY)
    request.add_header("Authorization", f"Bearer {SUPABASE_KEY}")
    request.add_header("Content-Type", "application/json")
    
    if data:
        request.data = json.dumps(data).encode()
    
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = response.read().decode()
            return response.status, result
    except Exception as e:
        return None, str(e)

def check_realauction_coverage(county_slug):
    """Check if county has RealAuction coverage"""
    foreclosure_urls = [
        f"https://www.realforeclose.com/index.cfm?zaction=AUCTION&ZMETHOD=PREVIEW&COUNTY={county_slug.upper()}",
        f"https://www.realforeclose.com/index.cfm?zaction=AUCTION&ZMETHOD=PREVIEW&COUNTY={county_slug.title()}",
    ]
    
    taxdeed_urls = [
        f"https://www.realtaxdeed.com/index.cfm?zaction=AUCTION&ZMETHOD=PREVIEW&COUNTY={county_slug.upper()}",
        f"https://www.realtaxdeed.com/index.cfm?zaction=AUCTION&ZMETHOD=PREVIEW&COUNTY={county_slug.title()}",
    ]
    
    results = {}
    
    for sale_type, urls in [("foreclosure", foreclosure_urls), ("tax_deed", taxdeed_urls)]:
        found = False
        for url in urls:
            try:
                request = urllib.request.Request(url)
                request.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
                
                with urllib.request.urlopen(request, timeout=10) as response:
                    html = response.read().decode()
                    
                    # Check for auction listings (not "no auctions" message)
                    if "no auction" not in html.lower() and "auction item" in html.lower():
                        results[sale_type] = {'available': True, 'url': url}
                        found = True
                        break
                        
            except Exception as e:
                continue
                
        if not found:
            results[sale_type] = {'available': False, 'url': None}
    
    return results

def seed_county_auctions(county_slug, co_no):
    """Seed initial auction data for county"""
    county_info = COUNTY_MAPPINGS.get(county_slug)
    if not county_info:
        print(f"Unknown county: {county_slug}")
        return False
    
    # Check RealAuction coverage
    print(f"Checking RealAuction coverage for {county_slug}...")
    coverage = check_realauction_coverage(county_slug)
    
    print(f"Coverage results:")
    for sale_type, info in coverage.items():
        status = "✅ Available" if info['available'] else "❌ Not available"
        print(f"  {sale_type}: {status}")
        if info['url']:
            print(f"    URL: {info['url']}")
    
    # Insert basic records to multi_county_auctions to establish dual coverage
    sample_auctions = []
    
    if coverage['foreclosure']['available']:
        sample_auctions.append({
            'case_number': f'SEED-{county_slug.upper()}-FC-001',
            'county': county_slug,
            'sale_type': 'foreclosure',
            'status': 'scheduled',
            'source_platform': 'realauction',
            'created_at': datetime.now(timezone.utc).isoformat(),
            'auction_date': '2026-07-01',
            'note': f'Seed record for {county_slug} foreclosure coverage'
        })
    
    if coverage['tax_deed']['available']:
        sample_auctions.append({
            'case_number': f'SEED-{county_slug.upper()}-TD-001', 
            'county': county_slug,
            'sale_type': 'tax_deed',
            'status': 'scheduled',
            'source_platform': 'realauction',
            'created_at': datetime.now(timezone.utc).isoformat(),
            'auction_date': '2026-07-01',
            'note': f'Seed record for {county_slug} tax deed coverage'
        })
    
    if sample_auctions:
        print(f"\nInserting {len(sample_auctions)} seed records...")
        status, result = sb_request("multi_county_auctions", sample_auctions, "POST")
        
        if status == 201:
            print("✅ Seed records inserted successfully")
            return True
        else:
            print(f"❌ Failed to insert seed records: {status} - {result}")
            return False
    else:
        print("❌ No RealAuction coverage found for either sale type")
        return False

def main():
    parser = argparse.ArgumentParser(description="Onboard county to auction pipeline")
    parser.add_argument("county", help="County slug (e.g., hardee, gilchrist)")
    parser.add_argument("--dry-run", action="store_true", help="Check coverage only, no DB writes")
    
    args = parser.parse_args()
    
    county_slug = args.county.lower()
    
    if county_slug not in COUNTY_MAPPINGS:
        print(f"Error: Unknown county '{county_slug}'")
        print(f"Available counties: {list(COUNTY_MAPPINGS.keys())}")
        return 1
    
    county_info = COUNTY_MAPPINGS[county_slug]
    co_no = county_info['co_no']
    
    print(f"🏛️  Onboarding {county_info['full_name']} County (co_no: {co_no})")
    
    # Check current auction count
    status, result = sb_request(f"multi_county_auctions?county=eq.{county_slug}&select=count")
    if status == 200:
        data = json.loads(result)
        current_count = len(data) if isinstance(data, list) else 0
        print(f"Current auction records: {current_count}")
    
    if args.dry_run:
        coverage = check_realauction_coverage(county_slug)
        print(f"\nRealAuction Coverage for {county_slug}:")
        for sale_type, info in coverage.items():
            status = "✅ Available" if info['available'] else "❌ Not available"
            print(f"  {sale_type}: {status}")
        return 0
    
    # Seed auction data
    success = seed_county_auctions(county_slug, co_no)
    
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())