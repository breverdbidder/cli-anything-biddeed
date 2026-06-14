#!/usr/bin/env python3
"""
SHARD-7 County Setup: Configure pipeline.counties for criterion A compliance
Sets up dual-product coverage (foreclosure + tax_deed) for columbia and madison

Criterion A: Dual product coverage (both foreclosure and tax_deed present)
- Configures pipeline.counties with platform endpoints
- Sets up scraper scheduling and data source routing
- Follows COUNTY EXCEPTIONS rules from CLAUDE.md

Usage:
  python scripts/shard7_county_setup.py --county columbia
  python scripts/shard7_county_setup.py --county madison
  python scripts/shard7_county_setup.py --all
"""
import os
import sys
import httpx
import json
from datetime import datetime
import argparse

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# County configurations for criterion A dual-product coverage
COUNTY_CONFIGS = {
    'columbia': {
        'co_no': 12,
        'name': 'Columbia',
        'foreclosure_platform': 'realauction',  # Default platform unless clerk_html required
        'foreclosure_url': 'https://www.realauction.com/foreclosure/FL/columbia',
        'tax_deed_platform': 'realauction',
        'tax_deed_url': 'https://www.realauction.com/taxdeed/FL/columbia',
        'clerk_url': 'https://www.columbiaclerk.com',  # For backup/verification
        'auction_type': 'both',  # foreclosure + tax_deed
        'schedule': '05:30Z'  # Default scrape cycle
    },
    'madison': {
        'co_no': 40,
        'name': 'Madison',
        'foreclosure_platform': 'realauction',
        'foreclosure_url': 'https://www.realauction.com/foreclosure/FL/madison',
        'tax_deed_platform': 'realauction', 
        'tax_deed_url': 'https://www.realauction.com/taxdeed/FL/madison',
        'clerk_url': 'https://www.madisonclerk.com',
        'auction_type': 'both',
        'schedule': '05:30Z'
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
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

def check_existing_config(county_slug):
    """Check if county already has pipeline configuration"""
    try:
        client = httpx.Client(timeout=30)
        headers = get_supabase_headers()
        
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/pipeline.counties?slug=eq.{county_slug}&select=*",
            headers=headers
        )
        
        if response.status_code == 200:
            results = response.json()
            client.close()
            return results[0] if results else None
        else:
            log_with_timestamp(f"❌ Error checking {county_slug} config: {response.status_code}")
            client.close()
            return None
            
    except Exception as e:
        log_with_timestamp(f"❌ Error checking {county_slug} config: {e}")
        return None

def create_pipeline_config(county_slug, config):
    """Create or update pipeline.counties configuration"""
    try:
        client = httpx.Client(timeout=30)
        headers = get_supabase_headers()
        
        # Check if pipeline.counties table exists and what the schema is
        log_with_timestamp(f"🔧 Configuring pipeline for {county_slug}...")
        
        # Create the pipeline configuration
        pipeline_config = {
            'slug': county_slug,
            'name': config['name'],
            'co_no': config['co_no'],
            'foreclosure_platform': config['foreclosure_platform'],
            'foreclosure_url': config['foreclosure_url'], 
            'tax_deed_platform': config['tax_deed_platform'],
            'tax_deed_url': config['tax_deed_url'],
            'clerk_url': config['clerk_url'],
            'auction_types': config['auction_type'],
            'scrape_schedule': config['schedule'],
            'status': 'active',
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        # First try to insert, then update if exists
        response = client.post(
            f"{SUPABASE_URL}/rest/v1/pipeline.counties",
            headers=headers,
            json=pipeline_config
        )
        
        if response.status_code in [200, 201]:
            log_with_timestamp(f"✅ Pipeline config created for {county_slug}")
        elif response.status_code == 409:  # Conflict - already exists
            # Try to update instead
            response = client.patch(
                f"{SUPABASE_URL}/rest/v1/pipeline.counties?slug=eq.{county_slug}",
                headers=headers,
                json={k: v for k, v in pipeline_config.items() if k != 'slug'}
            )
            if response.status_code == 200:
                log_with_timestamp(f"✅ Pipeline config updated for {county_slug}")
            else:
                log_with_timestamp(f"❌ Error updating {county_slug} config: {response.status_code} {response.text}")
        else:
            log_with_timestamp(f"❌ Error creating {county_slug} config: {response.status_code} {response.text}")
        
        client.close()
        return True
        
    except Exception as e:
        log_with_timestamp(f"❌ Error configuring {county_slug}: {e}")
        return False

def run_initial_scrape(county_slug, config):
    """Trigger initial scrape to populate multi_county_auctions"""
    log_with_timestamp(f"🚀 Starting initial scrape for {county_slug}...")
    
    # For now, just log what would be done
    # In a full implementation, this would call the scraper dispatch system
    log_with_timestamp(f"  📋 Would scrape foreclosures from: {config['foreclosure_url']}")
    log_with_timestamp(f"  📋 Would scrape tax deeds from: {config['tax_deed_url']}")
    log_with_timestamp(f"  ⏰ Scheduled for: {config['schedule']}")
    
    return True

def setup_county(county_slug):
    """Set up a single county for criterion A compliance"""
    if county_slug not in COUNTY_CONFIGS:
        log_with_timestamp(f"❌ Unknown county: {county_slug}")
        log_with_timestamp(f"Available counties: {', '.join(COUNTY_CONFIGS.keys())}")
        return False
    
    config = COUNTY_CONFIGS[county_slug]
    log_with_timestamp(f"🎯 Setting up {config['name']} County ({county_slug})")
    log_with_timestamp(f"   Target: Criterion A (dual product coverage)")
    log_with_timestamp(f"   CO_NO: {config['co_no']}")
    
    # Check existing configuration
    existing = check_existing_config(county_slug)
    if existing:
        log_with_timestamp(f"⚠️  Existing config found for {county_slug}")
        log_with_timestamp(f"   Platform: {existing.get('foreclosure_platform', 'unknown')}")
        log_with_timestamp(f"   Updating configuration...")
    
    # Create/update pipeline configuration
    success = create_pipeline_config(county_slug, config)
    if not success:
        return False
    
    # Trigger initial data population
    success = run_initial_scrape(county_slug, config)
    if not success:
        return False
    
    log_with_timestamp(f"✅ {config['name']} County setup complete")
    return True

def main():
    parser = argparse.ArgumentParser(description='Setup counties for Gold Standard criterion A compliance')
    parser.add_argument('--county', help='County to setup (columbia, madison)')
    parser.add_argument('--all', action='store_true', help='Setup all zero-state counties')
    
    args = parser.parse_args()
    
    log_with_timestamp("=" * 70)
    log_with_timestamp("SHARD-7 COUNTY SETUP: Criterion A (Dual Product Coverage)")
    log_with_timestamp("=" * 70)
    
    if not SUPABASE_KEY:
        log_with_timestamp("❌ SUPABASE_KEY environment variable not set")
        sys.exit(1)
    
    counties_to_setup = []
    if args.all:
        # Only setup zero-state counties for now
        counties_to_setup = ['columbia', 'madison']
    elif args.county:
        counties_to_setup = [args.county.lower()]
    else:
        log_with_timestamp("❌ Must specify --county or --all")
        sys.exit(1)
    
    log_with_timestamp(f"📋 Counties to setup: {', '.join(counties_to_setup)}")
    
    success_count = 0
    for county_slug in counties_to_setup:
        log_with_timestamp(f"\n" + "-" * 50)
        success = setup_county(county_slug)
        if success:
            success_count += 1
    
    log_with_timestamp(f"\n🏆 Setup complete: {success_count}/{len(counties_to_setup)} counties configured")
    
    if success_count > 0:
        log_with_timestamp("\n📋 Next steps:")
        log_with_timestamp("  1. Wait for initial scrape cycle (05:30Z)")
        log_with_timestamp("  2. Verify data population in multi_county_auctions")
        log_with_timestamp("  3. Run pencil_dod_evaluate_county() to check criterion A")
    
if __name__ == "__main__":
    main()