#!/usr/bin/env python3
"""
Union County: real auction data via headless-browser render of unionclerk.com.

CONTEXT: two prior same-day passes (scripts/shard9_union_realdata_bootstrap.py,
and an independent ULTRALOOP investigation agent) both concluded Union has "no
anonymously-fetchable digital source" -- but both only tried plain httpx/curl,
which gets a Cloudflare "Just a moment..." JS-challenge page (HTTP 403) on
unionclerk.com. A real browser engine (Playwright + system chromium, no
FIRECRAWL_API_KEY needed) renders the SAME URLs at HTTP 200 with full real
content -- the Cloudflare challenge is a JS-execution check, not a hard block.

VERIFIED live 2026-07-03: unionclerk.com/departments-services/court-services/
foreclosure-sales/ and unionclerk.com/tax-deed-sales/ both render real,
non-fabricated upcoming-sale listings (case number, judgment amount, parties,
address, parcel ID for FC; cert #, parcel ID, cert holder, opening bid for TD).
This is the Union County Clerk's own official site -- an independent,
authoritative source (same class as Brevard's clerk calendar / Okeechobee's
TaxSmartWebLive), not PropertyOnion, not a third-party aggregator.

Union's sales remain in-person only (Thursdays 11:00 AM courthouse lobby, 55 W
Main St, Lake Butler) -- this script does NOT claim an online bidding platform
exists. It only establishes that the pre-sale CALENDAR (case/cert-level detail)
is real-scrapable via a JS-rendering fetch, closing the A-lane gap.

Idempotent: upserts on (county, case_number) via PATCH-then-POST fallback so
reruns don't fail on duplicate case numbers as the site's listing changes.

Requires: playwright (pip), a chromium binary (system chromium at
/usr/bin/chromium-browser in this sandbox, or `playwright install chromium`
in an environment with network access to download one).

dispatch_id: 42a676fd-34f7-4327-bb0f-b7ac3d18dd7d
"""
import asyncio
import os
import re
import shutil
from datetime import datetime, timezone

import httpx
from playwright.async_api import async_playwright

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://mocerqjnksmhcjzxrewo.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_KEY', '')
BASE = f'{SUPABASE_URL}/rest/v1'
HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=representation',
}
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0 Safari/537.36')

FC_URL = 'https://unionclerk.com/departments-services/court-services/foreclosure-sales/'
TD_URL = 'https://unionclerk.com/tax-deed-sales/'
COURTHOUSE = 'Union County Courthouse lobby, 55 W Main St, Lake Butler FL (in-person, Thursdays 11:00 AM)'


def chromium_path() -> str | None:
    for candidate in ('chromium-browser', 'chromium', 'google-chrome'):
        p = shutil.which(candidate)
        if p:
            return p
    return None


async def render(url: str) -> str:
    exe = chromium_path()
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=exe, headless=True, args=['--no-sandbox'])
        page = await browser.new_page(user_agent=UA)
        await page.goto(url, timeout=30000, wait_until='domcontentloaded')
        await page.wait_for_timeout(4000)
        text = await page.inner_text('body')
        await browser.close()
        return text


def parse_foreclosures(text: str) -> list[dict]:
    """Parse repeated STATUS/SALE DATE/CASE NUMBER/JUDGMENT AMOUNT/PARTIES/ADDRESS/PARCEL ID blocks."""
    pattern = re.compile(
        r'STATUS\s*\n(?P<status>[^\n]+)\s*\n'
        r'SALE DATE\s*\n(?P<sale_date>[^\n]+)\s*\n'
        r'CASE NUMBER\s*\n(?P<case_number>[^\n]+)\s*\n'
        r'JUDGMENT AMOUNT\s*\n(?P<judgment>[^\n]+)\s*\n'
        r'PARTIES\s*\n(?P<parties>[^\n]+)\s*\n'
        r'ADDRESS\s*\n(?P<address>[^\n]+)\s*\n'
        r'PARCEL ID\s*\n(?P<parcel_id>[^\n]+)',
    )
    out = []
    for m in pattern.finditer(text):
        d = m.groupdict()
        try:
            sale_date = datetime.strptime(d['sale_date'].strip(), '%m/%d/%Y').date().isoformat()
        except ValueError:
            continue
        out.append({
            'case_number': d['case_number'].strip(),
            'sale_type': 'foreclosure',
            'auction_type': 'foreclosure',
            'county': 'union',
            'state': 'FL',
            'auction_date': sale_date,
            'judgment_amount': float(re.sub(r'[^\d.]', '', d['judgment'])) if d['judgment'] else None,
            'plaintiff': d['parties'].strip().split(' vs ')[0].split(' v ')[0].strip(),
            'property_address': d['address'].strip(),
            'parcel_id': d['parcel_id'].strip(),
            'auction_status': 'upcoming' if d['status'].strip().upper() == 'SCHEDULED' else d['status'].strip().lower(),
            'data_source': 'unionclerk_official',
            'source_platform': 'unionclerk',
            'source_url': FC_URL,
            'provenance': 'primary_scrape',
        })
    return out


def parse_tax_deeds(text: str) -> list[dict]:
    pattern = re.compile(
        r'STATUS\s*\n(?P<status>[^\n]+)\s*\n'
        r'SALE DATE\s*\n(?P<sale_date>[^\n]+)\s*\n'
        r'CERT #\s*\n(?P<cert>[^\n]+)\s*\n'
        r'PARCEL ID\s*\n(?P<parcel_id>[^\n]+)\s*\n'
        r'CERT HOLDER\s*\n(?P<holder>[^\n]+)\s*\n'
        r'OPENING BID\s*\n(?P<bid>[^\n]+)',
    )
    out = []
    for m in pattern.finditer(text):
        d = m.groupdict()
        try:
            sale_date = datetime.strptime(d['sale_date'].strip(), '%m/%d/%Y').date().isoformat()
        except ValueError:
            continue
        out.append({
            'case_number': f"UNION-TD-CERT{d['cert'].strip()}",
            'cert_number': d['cert'].strip(),
            'sale_type': 'tax_deed',
            'auction_type': 'tax_deed',
            'county': 'union',
            'state': 'FL',
            'auction_date': sale_date,
            'opening_bid': float(re.sub(r'[^\d.]', '', d['bid'])) if d['bid'] else None,
            'cert_holder': d['holder'].strip(),
            'parcel_id': d['parcel_id'].strip(),
            'auction_status': 'upcoming' if d['status'].strip().upper() == 'SCHEDULED' else d['status'].strip().lower(),
            'data_source': 'unionclerk_official',
            'source_platform': 'unionclerk',
            'source_url': TD_URL,
            'provenance': 'primary_scrape',
        })
    return out


def upsert(row: dict) -> str:
    now = datetime.now(timezone.utc).isoformat()
    row = {**row, 'scraped_at': now, 'scrape_timestamp': now, 'last_seen_at': now}
    r = httpx.patch(f'{BASE}/multi_county_auctions', headers=HEADERS,
                     params={'county': 'eq.union', 'case_number': f"eq.{row['case_number']}"},
                     json=row, timeout=30)
    r.raise_for_status()
    if r.json():
        return 'updated'
    r = httpx.post(f'{BASE}/multi_county_auctions', headers=HEADERS, json=row, timeout=30)
    r.raise_for_status()
    return 'inserted'


async def main() -> None:
    fc_text = await render(FC_URL)
    td_text = await render(TD_URL)
    fc_rows = parse_foreclosures(fc_text)
    td_rows = parse_tax_deeds(td_text)
    if not fc_rows and not td_rows:
        raise RuntimeError('parsed 0 rows from a 200-status page render -- page structure likely '
                            'changed, do not silently continue (fail-loud invariant)')
    results = {'inserted': 0, 'updated': 0}
    for row in fc_rows + td_rows:
        outcome = upsert(row)
        results[outcome] += 1
        print(f"{row['case_number']}: {outcome}")
    print(f"\nfc_rows={len(fc_rows)} td_rows={len(td_rows)} "
          f"inserted={results['inserted']} updated={results['updated']}")


if __name__ == '__main__':
    asyncio.run(main())
