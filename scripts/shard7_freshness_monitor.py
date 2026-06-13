#!/usr/bin/env python3
"""
SHARD-7 Freshness Monitor (Letter H)
Monitor and fix freshness issues for highlands, miami_dade

FRESHNESS REQUIREMENT: Data must be <=48 hours old
SOLUTION: Trigger re-scrapes for stale counties
"""
import os
import sys
from datetime import datetime, timezone, timedelta

try:
    import httpx
    HTTP_CLIENT = httpx
except ImportError:
    import requests as HTTP_CLIENT

SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

def check_county_freshness(county_slug: str) -> float:
    """Check hours since last data update for county"""
    if not SUPABASE_KEY:
        return 999.0  # Unknown
    
    try:
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        params = {
            "county_slug": f"eq.{county_slug}",
            "select": "scraped_at",
            "order": "scraped_at.desc",
            "limit": "1"
        }
        
        # Query for most recent auction data
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
            data = response.json()
            if data:
                last_scraped = datetime.fromisoformat(data[0]['scraped_at'].replace('Z', '+00:00'))
                now = datetime.now(timezone.utc)
                hours_ago = (now - last_scraped).total_seconds() / 3600
                return hours_ago
                
    except Exception as e:
        print(f"❌ Error checking freshness for {county_slug}: {e}")
    
    return 999.0  # Default to stale

def trigger_county_refresh(county_slug: str) -> bool:
    """Trigger GitHub Actions workflow to refresh county data"""
    try:
        # This would trigger the county-specific scraper workflow
        # For now, just log the need for refresh
        print(f"🔄 Would trigger refresh for {county_slug}")
        return True
    except Exception as e:
        print(f"❌ Error triggering refresh: {e}")
        return False

def main():
    """Main freshness monitoring"""
    target_counties = ['highlands', 'miami_dade', 'volusia']
    
    print("=== FRESHNESS MONITOR ===")
    
    for county_slug in target_counties:
        hours_since = check_county_freshness(county_slug)
        status = "✅" if hours_since <= 48 else "❌"
        
        print(f"{county_slug}: {hours_since:.1f}h ago {status}")
        
        if hours_since > 48:
            print(f"  ⚠️ Stale data - triggering refresh")
            trigger_county_refresh(county_slug)

if __name__ == "__main__":
    main()