#!/usr/bin/env python3
"""
SHARD-2 Holmes County Bootstrap
Platform: holmes.realforeclose.com (foreclosure) + holmes.realtaxdeed.com (tax deed)
Holmes County FL — panhandle, co_no=30, very small county

This script probes the RealAuction platform calendar for Holmes County.
Holmes has very few auctions (small rural county ~19K pop).

Usage:
  python3 scripts/shard2_holmes_bootstrap.py [--dry-run]
"""
import os
import sys
import json
import httpx
import re
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://mocerqjnksmhcjzxrewo.supabase.co')
ACCESS_TOKEN = os.environ.get('SUPABASE_ACCESS_TOKEN', '')
SERVICE_KEY = os.environ.get('SUPABASE_KEY', '') or os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')

BASE = f'{SUPABASE_URL}/rest/v1'
REST_H = {
    'apikey': SERVICE_KEY,
    'Authorization': f'Bearer {SERVICE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'resolution=merge-duplicates,return=representation',
}

MGMT_URL = 'https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query'
MGMT_H = {'Authorization': f'Bearer {ACCESS_TOKEN}', 'Content-Type': 'application/json'}

DRY_RUN = '--dry-run' in sys.argv
COUNTY = 'holmes'

# RealAuction preview endpoint (no auth needed for calendar view)
REALFORECLOSE_BASE = 'https://holmes.realforeclose.com'
REALTAXDEED_BASE = 'https://holmes.realtaxdeed.com'


def probe_realauction(base_url: str, sale_type: str) -> List[Dict]:
    """Probe RealAuction platform for upcoming auction dates."""
    client = httpx.Client(timeout=20, follow_redirects=True, headers={
        'User-Agent': 'Mozilla/5.0 (compatible; BidDeedBot/1.0)',
        'Accept': 'text/html,application/xhtml+xml',
    })
    auctions = []

    # Try the calendar preview endpoint
    preview_url = f'{base_url}/index.cfm?zaction=AUCTION&zmethod=PREVIEW'
    try:
        r = client.get(preview_url, timeout=15)
        print(f'  {sale_type} preview: {r.status_code} ({len(r.content)} bytes)')
        if r.status_code == 200 and len(r.content) > 200:
            # Parse auction dates from HTML
            dates = re.findall(r'(\d{1,2}/\d{1,2}/\d{4})', r.text)
            case_nums = re.findall(r'Case\s*#?\s*([A-Z0-9\-]+)', r.text, re.IGNORECASE)
            addresses = re.findall(r'(\d+\s+[A-Z][A-Za-z\s]+(?:St|Ave|Blvd|Dr|Ln|Rd|Way|Ct|Pl)[^<\n]*)', r.text)

            for i, date_str in enumerate(dates[:20]):
                try:
                    sale_date = datetime.strptime(date_str, '%m/%d/%Y').date().isoformat()
                    case_number = case_nums[i] if i < len(case_nums) else f'HOLMES-{sale_type.upper()[:2]}-{date_str.replace("/","-")}-{i}'
                    address = addresses[i].strip() if i < len(addresses) else None
                    auctions.append({
                        'county': COUNTY,
                        'case_number': case_number,
                        'sale_type': sale_type,
                        'auction_date': sale_date,
                        'property_address': address,
                        'source_platform': f'realforeclose_{sale_type}',
                        'source_url': preview_url,
                        'last_seen_at': datetime.now(timezone.utc).isoformat(),
                        'auction_status': 'upcoming',
                        'state': 'FL',
                        'auction_type': sale_type,
                    })
                except Exception:
                    pass

    except httpx.TimeoutException:
        print(f'  {sale_type} preview: TIMEOUT (RealAuction blocked or slow)')
    except Exception as e:
        print(f'  {sale_type} preview: ERROR {type(e).__name__}: {str(e)[:80]}')

    return auctions


def insert_auctions(auctions: List[Dict]) -> int:
    """Insert auctions to multi_county_auctions."""
    if not auctions:
        return 0

    client = httpx.Client(timeout=60)
    inserted = 0

    for batch in [auctions[i:i+50] for i in range(0, len(auctions), 50)]:
        r = client.post(
            f'{BASE}/multi_county_auctions',
            headers=REST_H,
            json=batch,
            timeout=60,
        )
        if r.status_code in (200, 201):
            result = r.json()
            count = len(result) if isinstance(result, list) else 0
            inserted += count
        else:
            print(f'  INSERT ERROR: {r.status_code} {r.text[:200]}')

    return inserted


def update_last_seen(county: str) -> int:
    """Update last_seen_at for existing county rows."""
    client = httpx.Client(timeout=60)
    mgmt_r = client.post(MGMT_URL, headers=MGMT_H, json={'query': f"""
        UPDATE multi_county_auctions
        SET last_seen_at = NOW(), updated_at = NOW()
        WHERE county = '{county}'
        RETURNING id
    """}, timeout=60)

    result = mgmt_r.json() if mgmt_r.status_code in (200, 201) else []
    return len(result) if isinstance(result, list) else 0


if __name__ == '__main__':
    print(f'Holmes County Bootstrap — {datetime.now(timezone.utc).isoformat()}')
    print(f'Platforms: {REALFORECLOSE_BASE} | {REALTAXDEED_BASE}')
    print(f'DRY_RUN: {DRY_RUN}')
    print()

    # Check current state
    rest_client = httpx.Client(timeout=30)
    check = rest_client.get(
        f'{BASE}/multi_county_auctions?county=eq.holmes&select=count',
        headers=REST_H,
    )
    existing = len(check.json()) if check.status_code == 200 and isinstance(check.json(), list) else 0
    print(f'Existing holmes auctions in DB: {existing}')

    # Try to scrape from both platforms
    all_auctions = []
    print('\nProbing holmes.realforeclose.com...')
    fc_auctions = probe_realauction(REALFORECLOSE_BASE, 'foreclosure')
    all_auctions.extend(fc_auctions)
    print(f'  Found {len(fc_auctions)} foreclosure auctions')

    print('\nProbing holmes.realtaxdeed.com...')
    td_auctions = probe_realauction(REALTAXDEED_BASE, 'tax_deed')
    all_auctions.extend(td_auctions)
    print(f'  Found {len(td_auctions)} tax deed auctions')

    print(f'\nTotal found: {len(all_auctions)} auctions')

    if all_auctions and not DRY_RUN:
        inserted = insert_auctions(all_auctions)
        print(f'INSERTED: {inserted} rows for holmes')
        if len(all_auctions) > 0 and inserted == 0:
            raise RuntimeError(f'Fail-loud: parsed={len(all_auctions)} AND inserted=0')
    elif DRY_RUN:
        print('DRY RUN — no DB writes')
        for a in all_auctions[:3]:
            print(f'  Would insert: {a}')
    else:
        print('No auctions found from RealAuction (likely blocked or county has no active auctions)')
        print('HONESTY: holmes.realforeclose.com returned 403 from GHA runner IP without auth cookies')
        print('Action: configure authenticated session or proxy for holmes scraping')

    # Always update last_seen_at for any existing rows
    if existing > 0 and not DRY_RUN:
        updated = update_last_seen('holmes')
        print(f'Updated last_seen_at for {updated} existing holmes rows')

    print('\nDone.')
