#!/usr/bin/env python3
"""
SHARD-10 Freshness Fix (Gold Standard Letter H)  
Fix data staleness issues for counties failing ≤48h SLA

Target counties:
- alachua: 343.0 hours stale (≫48h limit) 
- martin: 222.9 hours stale (≫48h limit)

Letter H criteria: ≤48 hours since last activity (created_at, updated_at, tier1_verified_at)

Strategy:
1. Check pipeline.counties configuration 
2. Verify scraper scheduling and endpoints
3. Trigger manual refresh if needed
4. Configure automated refresh cadence
5. Test connectivity to data sources

Usage:
  python scripts/shard10_freshness_fix.py --county alachua
  python scripts/shard10_freshness_fix.py --county martin
  python scripts/shard10_freshness_fix.py --all-stale
"""
import os
import sys
import httpx
import json
from datetime import datetime, timedelta, timezone
import argparse
import time

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# Target counties with staleness issues
TARGET_COUNTIES = {
    'alachua': {'hours_stale': 343.0, 'priority': 1},
    'martin': {'hours_stale': 222.9, 'priority': 2}
}

def log(msg):
    """Log with timestamp"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

def check_county_freshness(county_slug: str) -> Dict:
    """Check current freshness status for a county"""
    try:
        client = httpx.Client(timeout=30)
        
        # Get latest activity timestamps
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions"
            f"?county=eq.{county_slug}"
            f"&select=created_at,updated_at,tier1_verified_at"
            f"&order=updated_at.desc.nullslast,created_at.desc.nullslast,tier1_verified_at.desc.nullslast"
            f"&limit=5",
            headers=sb_headers()
        )
        
        if response.status_code != 200:
            log(f"❌ Error checking freshness: {response.text}")
            return {}
        
        records = response.json()
        if not records:
            log(f"❌ No auction records found for {county_slug}")
            return {}
        
        # Find the most recent timestamp across all activity types
        latest_timestamp = None
        activity_type = None
        
        for record in records:
            timestamps = [
                (record.get('updated_at'), 'updated_at'),
                (record.get('created_at'), 'created_at'), 
                (record.get('tier1_verified_at'), 'tier1_verified_at')
            ]
            
            for ts_str, ts_type in timestamps:
                if ts_str:
                    try:
                        ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                        if not latest_timestamp or ts > latest_timestamp:
                            latest_timestamp = ts
                            activity_type = ts_type
                    except Exception:
                        continue
        
        if not latest_timestamp:
            return {'error': 'No valid timestamps found'}
        
        # Calculate hours since latest activity
        now = datetime.now(timezone.utc)
        hours_since = (now - latest_timestamp).total_seconds() / 3600
        
        return {
            'county': county_slug,
            'latest_activity': latest_timestamp.isoformat(),
            'activity_type': activity_type,
            'hours_since_activity': hours_since,
            'passes_sla': hours_since <= 48,
            'sla_status': 'PASS' if hours_since <= 48 else 'FAIL'
        }
        
    except Exception as e:
        log(f"❌ Error checking freshness for {county_slug}: {e}")
        return {'error': str(e)}

def check_pipeline_config(county_slug: str) -> Dict:
    """Check pipeline.counties configuration for a county"""
    try:
        client = httpx.Client(timeout=30)
        
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/counties?slug=eq.{county_slug}&select=*",
            headers=sb_headers()
        )
        
        if response.status_code != 200:
            log(f"❌ Error checking pipeline config: {response.text}")
            return {}
        
        configs = response.json()
        if not configs:
            return {'configured': False, 'error': 'No pipeline configuration found'}
        
        config = configs[0]
        
        return {
            'configured': True,
            'county': county_slug,
            'enabled': config.get('enabled', False),
            'foreclosure_platform': config.get('foreclosure_platform'),
            'foreclosure_url': config.get('foreclosure_url'),
            'tax_deed_platform': config.get('tax_deed_platform'), 
            'tax_deed_url': config.get('tax_deed_url'),
            'priority': config.get('priority', 0),
            'last_scraped': config.get('last_scraped'),
            'scrape_frequency': config.get('scrape_frequency', 'unknown'),
            'notes': config.get('notes', '')
        }
        
    except Exception as e:
        log(f"❌ Error checking pipeline config for {county_slug}: {e}")
        return {'error': str(e)}

def test_scraper_endpoints(county_slug: str, config: Dict) -> Dict:
    """Test connectivity to county scraper endpoints"""
    log(f"🔗 Testing scraper endpoints for {county_slug}")
    
    results = {
        'foreclosure_endpoint': {'tested': False},
        'tax_deed_endpoint': {'tested': False}
    }
    
    try:
        client = httpx.Client(timeout=15, follow_redirects=True)
        
        # Test foreclosure endpoint
        fc_url = config.get('foreclosure_url')
        if fc_url:
            try:
                log(f"  Testing foreclosure URL: {fc_url}")
                response = client.get(fc_url)
                results['foreclosure_endpoint'] = {
                    'tested': True,
                    'url': fc_url,
                    'status_code': response.status_code,
                    'accessible': response.status_code < 400,
                    'content_length': len(response.content),
                    'has_auction_data': 'auction' in response.text.lower() or 'foreclosure' in response.text.lower()
                }
                log(f"    ✅ Foreclosure endpoint: {response.status_code}")
            except Exception as e:
                results['foreclosure_endpoint'] = {
                    'tested': True,
                    'url': fc_url,
                    'accessible': False,
                    'error': str(e)
                }
                log(f"    ❌ Foreclosure endpoint failed: {e}")
        
        # Test tax deed endpoint  
        td_url = config.get('tax_deed_url')
        if td_url:
            try:
                log(f"  Testing tax deed URL: {td_url}")
                response = client.get(td_url)
                results['tax_deed_endpoint'] = {
                    'tested': True,
                    'url': td_url,
                    'status_code': response.status_code,
                    'accessible': response.status_code < 400,
                    'content_length': len(response.content),
                    'has_auction_data': 'auction' in response.text.lower() or 'tax deed' in response.text.lower()
                }
                log(f"    ✅ Tax deed endpoint: {response.status_code}")
            except Exception as e:
                results['tax_deed_endpoint'] = {
                    'tested': True,
                    'url': td_url,
                    'accessible': False,
                    'error': str(e)
                }
                log(f"    ❌ Tax deed endpoint failed: {e}")
        
        return results
        
    except Exception as e:
        log(f"❌ Endpoint testing error: {e}")
        return {'error': str(e)}

def trigger_manual_refresh(county_slug: str) -> bool:
    """Trigger manual data refresh for a county"""
    log(f"🔄 Triggering manual refresh for {county_slug}")
    
    try:
        client = httpx.Client(timeout=30)
        
        # Update last_scraped timestamp to trigger refresh
        now = datetime.now().isoformat()
        response = client.patch(
            f"{SUPABASE_URL}/rest/v1/counties?slug=eq.{county_slug}",
            headers=sb_headers(),
            json={
                'last_scraped': now,
                'notes': f'SHARD-10 manual refresh triggered - {now}',
                'refresh_requested': True
            }
        )
        
        if response.status_code in [200, 204]:
            log(f"✅ Manual refresh triggered for {county_slug}")
            return True
        else:
            log(f"❌ Failed to trigger refresh: {response.text}")
            return False
            
    except Exception as e:
        log(f"❌ Manual refresh error: {e}")
        return False

def configure_scraper_scheduling(county_slug: str, frequency: str = 'daily') -> bool:
    """Configure automated scraper scheduling"""
    log(f"⏰ Configuring scraper scheduling for {county_slug}")
    
    try:
        client = httpx.Client(timeout=30)
        
        # Update scraper frequency and enable auto-refresh
        response = client.patch(
            f"{SUPABASE_URL}/rest/v1/counties?slug=eq.{county_slug}",
            headers=sb_headers(),
            json={
                'scrape_frequency': frequency,
                'enabled': True,
                'auto_refresh': True,
                'priority': 2,  # Increase priority for freshness
                'notes': f'SHARD-10 freshness fix - {frequency} refresh enabled',
                'updated_at': datetime.now().isoformat()
            }
        )
        
        if response.status_code in [200, 204]:
            log(f"✅ Scraper scheduling configured: {frequency} refresh")
            return True
        else:
            log(f"❌ Failed to configure scheduling: {response.text}")
            return False
            
    except Exception as e:
        log(f"❌ Scheduling configuration error: {e}")
        return False

def fix_county_freshness(county_slug: str) -> Dict:
    """Main function to fix freshness issues for a county"""
    log(f"\n{'='*60}")
    log(f"FIXING FRESHNESS: {county_slug.upper()}")
    log(f"{'='*60}")
    
    result = {
        'county': county_slug,
        'success': False,
        'actions_taken': [],
        'errors': []
    }
    
    # Step 1: Check current freshness
    log(f"📊 Checking current freshness status...")
    freshness = check_county_freshness(county_slug)
    
    if 'error' in freshness:
        result['errors'].append(f"Could not check freshness: {freshness['error']}")
        return result
    
    log(f"   Latest activity: {freshness['latest_activity']}")
    log(f"   Hours since: {freshness['hours_since_activity']:.1f}")
    log(f"   SLA status: {freshness['sla_status']}")
    
    if freshness['passes_sla']:
        log(f"✅ {county_slug} already meets freshness SLA")
        result['success'] = True
        return result
    
    result['initial_hours_stale'] = freshness['hours_since_activity']
    
    # Step 2: Check pipeline configuration
    log(f"🔧 Checking pipeline configuration...")
    config = check_pipeline_config(county_slug)
    
    if 'error' in config:
        result['errors'].append(f"Pipeline config error: {config['error']}")
        return result
    
    if not config.get('configured'):
        result['errors'].append("No pipeline configuration found")
        log(f"❌ No pipeline configuration for {county_slug}")
        return result
    
    log(f"   Enabled: {config['enabled']}")
    log(f"   Foreclosure platform: {config['foreclosure_platform']}")
    log(f"   Tax deed platform: {config['tax_deed_platform']}")
    log(f"   Last scraped: {config['last_scraped']}")
    
    # Step 3: Test scraper endpoints
    log(f"🔗 Testing scraper endpoints...")
    endpoint_tests = test_scraper_endpoints(county_slug, config)
    
    # Step 4: Enable county if disabled
    if not config.get('enabled'):
        log(f"🔄 Enabling disabled county...")
        client = httpx.Client(timeout=30)
        response = client.patch(
            f"{SUPABASE_URL}/rest/v1/counties?slug=eq.{county_slug}",
            headers=sb_headers(),
            json={'enabled': True}
        )
        if response.status_code in [200, 204]:
            result['actions_taken'].append('enabled_county')
            log(f"✅ County enabled")
        else:
            log(f"❌ Failed to enable county")
    
    # Step 5: Trigger manual refresh
    if trigger_manual_refresh(county_slug):
        result['actions_taken'].append('manual_refresh')
        time.sleep(2)
    
    # Step 6: Configure automated scheduling  
    if configure_scraper_scheduling(county_slug, 'daily'):
        result['actions_taken'].append('configured_scheduling')
    
    # Step 7: Check freshness again after fixes
    log(f"🔄 Re-checking freshness after fixes...")
    time.sleep(5)  # Wait a bit for changes to take effect
    
    final_freshness = check_county_freshness(county_slug)
    
    if 'error' not in final_freshness:
        result['final_hours_stale'] = final_freshness['hours_since_activity']
        result['freshness_improved'] = final_freshness['passes_sla']
        
        if final_freshness['passes_sla']:
            log(f"✅ {county_slug} now meets freshness SLA")
            result['success'] = True
        else:
            log(f"⚠️ {county_slug} still stale - may need manual scraper run")
            result['needs_manual_scraper'] = True
    
    return result

def main():
    parser = argparse.ArgumentParser(description='SHARD-10 Freshness Fix')
    parser.add_argument('--county', choices=['alachua', 'martin'],
                        help='Fix freshness for specific county only')
    parser.add_argument('--all-stale', action='store_true',
                        help='Process all stale counties')
    args = parser.parse_args()
    
    log("🎯 SHARD-10 FRESHNESS FIX")
    log(f"Timestamp: {datetime.now().isoformat()}")
    
    if not SUPABASE_KEY:
        log("❌ SUPABASE_KEY environment variable not set")
        sys.exit(1)
    
    results = {}
    
    if args.county:
        # Single county
        counties_to_process = [args.county]
    elif args.all_stale:
        # All stale counties in priority order
        counties_to_process = sorted(TARGET_COUNTIES.keys(), 
                                   key=lambda x: TARGET_COUNTIES[x]['priority'])
    else:
        log("❌ Must specify either --county or --all-stale")
        sys.exit(1)
    
    # Process counties
    for county_slug in counties_to_process:
        results[county_slug] = fix_county_freshness(county_slug)
        time.sleep(3)  # Pause between counties
    
    # Final summary
    log(f"\n{'='*60}")
    log("FRESHNESS FIX SUMMARY")
    log(f"{'='*60}")
    
    successful_fixes = 0
    
    for county, result in results.items():
        if result.get('success'):
            successful_fixes += 1
            initial_hours = result.get('initial_hours_stale', 0)
            final_hours = result.get('final_hours_stale', 0)
            actions = ', '.join(result.get('actions_taken', []))
            
            log(f"  {county}: ✅ FIXED - {initial_hours:.1f}h → {final_hours:.1f}h ({actions})")
        else:
            errors = '; '.join(result.get('errors', ['Unknown error']))
            log(f"  {county}: ❌ FAILED - {errors}")
    
    log(f"\nCounties fixed: {successful_fixes}/{len(results)}")
    
    if successful_fixes > 0:
        log("✅ Freshness improvements applied")
        log("🔄 Monitor over next 24-48h for sustained freshness")
    else:
        log("❌ No counties successfully fixed")

if __name__ == "__main__":
    main()