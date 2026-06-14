#!/usr/bin/env python3
"""
SHARD-7 A-Lane Configuration
Fix columbia and madison counties (both at 0/10 - no pipeline config)

Priority: Configure basic realauction dual-product lanes for A-letter coverage
"""

import httpx
import json
from datetime import datetime

# Supabase configuration  
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_KEY = ""  # Will need to be set from environment

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

# Configuration for columbia and madison counties
COUNTY_CONFIGS = {
    'columbia': {
        'county_name': 'Columbia County',
        'state': 'FL',
        'fips_code': '12023',
        'foreclosure_platform': 'realauction',
        'foreclosure_url': 'https://www.realauction.com/florida/columbia-county',
        'tax_deed_platform': 'realauction', 
        'tax_deed_url': 'https://www.realauction.com/florida/columbia-county',
        'appraiser_url': 'https://www.columbiacountyclerk.com',
        'active': True,
        'pipeline_status': 'configured'
    },
    'madison': {
        'county_name': 'Madison County',
        'state': 'FL', 
        'fips_code': '12079',
        'foreclosure_platform': 'realauction',
        'foreclosure_url': 'https://www.realauction.com/florida/madison-county',
        'tax_deed_platform': 'realauction',
        'tax_deed_url': 'https://www.realauction.com/florida/madison-county', 
        'appraiser_url': 'https://www.madisonfl.com',
        'active': True,
        'pipeline_status': 'configured'
    }
}

def check_county_exists(county_slug):
    """Check if county exists in pipeline.counties table"""
    try:
        client = httpx.Client(timeout=30)
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/counties",
            headers=sb_headers(),
            params={'county_slug': f'eq.{county_slug}', 'select': '*'}
        )
        
        if response.status_code == 200:
            results = response.json()
            return results[0] if results else None
        else:
            print(f"❌ Failed to check {county_slug}: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Error checking {county_slug}: {e}")
        return None

def configure_county(county_slug, config):
    """Configure county in pipeline.counties table"""
    try:
        client = httpx.Client(timeout=30)
        
        # Check if exists first
        existing = check_county_exists(county_slug)
        
        if existing:
            print(f"✅ {county_slug} already configured: {existing.get('pipeline_status', 'unknown')}")
            return True
            
        # Insert new configuration
        payload = {
            'county_slug': county_slug,
            **config
        }
        
        response = client.post(
            f"{SUPABASE_URL}/rest/v1/counties",
            headers=sb_headers(),
            json=payload
        )
        
        if response.status_code == 201:
            print(f"✅ Configured {county_slug} in pipeline.counties")
            return True
        else:
            print(f"❌ Failed to configure {county_slug}: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error configuring {county_slug}: {e}")
        return False

def verify_lane_access(county_slug, config):
    """Verify realauction URLs are accessible"""
    try:
        client = httpx.Client(timeout=10, follow_redirects=True)
        
        # Test foreclosure URL
        fc_response = client.head(config['foreclosure_url'])
        fc_status = fc_response.status_code
        
        # Test tax deed URL  
        td_response = client.head(config['tax_deed_url'])
        td_status = td_response.status_code
        
        print(f"🔗 {county_slug} URL verification:")
        print(f"   Foreclosure: {fc_status} - {config['foreclosure_url']}")
        print(f"   Tax Deed: {td_status} - {config['tax_deed_url']}")
        
        return fc_status < 400 and td_status < 400
        
    except Exception as e:
        print(f"❌ URL verification failed for {county_slug}: {e}")
        return False

def main():
    """Configure A-lane for columbia and madison counties"""
    print("=== SHARD-7 A-LANE CONFIGURATION ===")
    print("Configuring columbia and madison for dual-product coverage")
    print()
    
    if not SUPABASE_KEY:
        print("❌ SUPABASE_KEY not set - this would normally fail")
        print("📋 Configuration that would be applied:")
        
        for county_slug, config in COUNTY_CONFIGS.items():
            print(f"\n{county_slug}:")
            for key, value in config.items():
                print(f"  {key}: {value}")
        
        print("\n✅ Configuration planned (dry run)")
        return
    
    # Configure each county
    for county_slug, config in COUNTY_CONFIGS.items():
        print(f"\n🔧 Configuring {county_slug}...")
        
        # Verify URLs are accessible
        if verify_lane_access(county_slug, config):
            # Configure in database
            if configure_county(county_slug, config):
                print(f"✅ {county_slug} A-lane configured")
            else:
                print(f"❌ {county_slug} configuration failed") 
        else:
            print(f"⚠️ {county_slug} URLs may be inaccessible")
            
    print("\n✅ A-lane configuration complete")

if __name__ == "__main__":
    main()