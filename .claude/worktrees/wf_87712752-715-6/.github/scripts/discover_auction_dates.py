#!/usr/bin/env python3
"""Discover RealAuction auction dates - v2 (ASCEND Phase 3b).

Improvements over v1:
  - Initial wait bumped 8s -> 15s
  - Adds Firecrawl 'scroll' + 'wait' chain to trigger any lazy rendering
  - Probes BOTH the CALENDAR endpoint AND the user-CALENDAR endpoint (sometimes
    different RealAuction installs serve calendar grid behind a different URL)
  - Multiple regex patterns: AUCTIONDATE param, ISO dates, JS array entries
  - Writes to biddeed.discovered_auction_dates (clean schema, no legacy constraints)

Env required:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, FIRECRAWL_API_KEY,
  COUNTY_SLUG, BASE_URL, PLATFORM, SALE_TYPE
"""
import os, re, sys, json
from datetime import date
import requests

def _req(name):
    v = os.environ.get(name)
    if not v: raise RuntimeError(f'Missing required env: {name}')
    return v

SUPABASE_URL  = _req('SUPABASE_URL').rstrip('/')
SUPABASE_KEY  = _req('SUPABASE_SERVICE_ROLE_KEY')
FIRECRAWL_KEY = _req('FIRECRAWL_API_KEY')
COUNTY        = _req('COUNTY_SLUG').lower().strip()
BASE_URL      = _req('BASE_URL').rstrip('/')
PLATFORM      = _req('PLATFORM').lower().strip()
SALE_TYPE     = _req('SALE_TYPE').lower().strip()

REST = f'{SUPABASE_URL}/rest/v1'
H    = {'apikey':SUPABASE_KEY,'Authorization':f'Bearer {SUPABASE_KEY}','Content-Type':'application/json'}
TODAY = date.today()

# Try multiple calendar URLs - some RealAuction installs use different endpoints
CALENDAR_URLS = [
    f'{BASE_URL}/index.cfm?zaction=USER&zmethod=CALENDAR',
    f'{BASE_URL}/index.cfm?zaction=AUCTION&Zmethod=CALENDAR',
]

print(f'>>> Discovery v2 for {COUNTY} ({SALE_TYPE}) on {PLATFORM}')

def firecrawl(url, actions):
    body = {'url':url,'formats':['markdown','html'],
            'actions':actions,'onlyMainContent':False,'timeout':120000}
    r = requests.post('https://api.firecrawl.dev/v1/scrape',
        headers={'Authorization':f'Bearer {FIRECRAWL_KEY}','Content-Type':'application/json'},
        json=body, timeout=180)
    if r.status_code != 200:
        return None, None, f'firecrawl {r.status_code}'
    data = r.json().get('data',{})
    return data.get('markdown',''), data.get('html',''), None

ACTION_CHAIN = [
    {'type':'wait','milliseconds':15000},
    {'type':'scroll','direction':'down'},
    {'type':'wait','milliseconds':3000},
    {'type':'scroll','direction':'down'},
    {'type':'wait','milliseconds':2000},
]

best_md, best_html, best_url = '', '', None
for url in CALENDAR_URLS:
    print(f'  trying {url}')
    md, html, err = firecrawl(url, ACTION_CHAIN)
    if err:
        print(f'    failed: {err}')
        continue
    print(f'    md={len(md)} html={len(html)}')
    # Pick URL with largest combined render (better signal of full page load)
    if len(md) + len(html) > len(best_md) + len(best_html):
        best_md, best_html, best_url = md, html, url

if not best_md and not best_html:
    print('ERROR: All Firecrawl attempts returned nothing', file=sys.stderr)
    sys.exit(1)

print(f'Using {best_url}  md={len(best_md)} html={len(best_html)}')

# Extract candidate dates from BOTH markdown AND html (HTML may have data attrs that markdown drops)
dates_found = set()
combined = best_md + '\n\n' + best_html

# Pattern 1: MM/DD/YYYY
for m in re.finditer(r'(\d{2})/(\d{2})/(\d{4})', combined):
    try:
        d = date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
        if 2020 <= d.year <= 2030: dates_found.add(d)
    except (ValueError, OverflowError): pass

# Pattern 2: YYYY-MM-DD
for m in re.finditer(r'(\d{4})-(\d{2})-(\d{2})', combined):
    try:
        d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if 2020 <= d.year <= 2030: dates_found.add(d)
    except (ValueError, OverflowError): pass

# Pattern 3: data-date or data-auction-date attrs
for m in re.finditer(r'data-(?:auction-?)?date=["\']([\d/-]+)["\']', combined):
    raw = m.group(1)
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%Y/%m/%d'):
        try:
            from datetime import datetime
            d = datetime.strptime(raw, fmt).date()
            if 2020 <= d.year <= 2030: dates_found.add(d)
            break
        except ValueError: continue

# Pattern 4: AUCTIONDATE= param values
for m in re.finditer(r'AUCTIONDATE=([\d/]+)', combined, re.IGNORECASE):
    raw = m.group(1)
    try:
        from datetime import datetime
        d = datetime.strptime(raw, '%m/%d/%Y').date()
        if 2020 <= d.year <= 2030: dates_found.add(d)
    except ValueError: pass

# Filter out today-only false positives. If only date found is today, that's likely page chrome.
print(f'Raw dates_found: {sorted(dates_found)}')
if dates_found == {TODAY}:
    print(f'WARNING: Only today\'s date found - calendar likely did not render', file=sys.stderr)

past_dates   = sorted([d for d in dates_found if d <  TODAY], reverse=True)
today_match  = TODAY in dates_found
future_dates = sorted([d for d in dates_found if d >  TODAY])

print(f'PAST ({len(past_dates)}): {past_dates[:7]}')
print(f'TODAY: {"yes" if today_match else "no"}')
print(f'FUTURE ({len(future_dates)}): {future_dates[:7]}')

# Upsert into biddeed.discovered_auction_dates
inserted = 0
def upsert(d, position, rank):
    payload = {
        'county_slug': COUNTY, 'sale_type': SALE_TYPE, 'platform': PLATFORM,
        'auction_date': d.isoformat(), 'position': position, 'rank_within': rank,
        'source_markdown_bytes': len(best_md),
        'notes': json.dumps({'discovery_version':'v2','best_url':best_url,'combined_bytes':len(combined)})
    }
    resp = requests.post(f'{REST}/biddeed.discovered_auction_dates',
        json=payload,
        headers={**H, 'Prefer':'resolution=merge-duplicates,return=minimal'},
        timeout=30)
    if resp.status_code >= 400:
        # Try alternate schema endpoint
        resp = requests.post(f'{REST}/rpc/upsert_discovered_date',
            json={'p':payload}, headers=H, timeout=30)
    if resp.status_code >= 400:
        print(f'  ! upsert {d}: {resp.status_code} {resp.text[:200]}', file=sys.stderr)
        return False
    return True

for rank, d in enumerate(past_dates[:5], 1):
    if upsert(d, 'past', rank): inserted += 1
if today_match:
    if upsert(TODAY, 'today', 1): inserted += 1
for rank, d in enumerate(future_dates[:5], 1):
    if upsert(d, 'future', rank): inserted += 1

print(f'\nINSERTED: {inserted} rows')

# GHA outputs
gh_output = os.environ.get('GITHUB_OUTPUT')
if gh_output:
    with open(gh_output, 'a') as f:
        f.write(f'past_count={len(past_dates)}\n')
        f.write(f'future_count={len(future_dates)}\n')
        f.write(f'most_recent_past={past_dates[0].isoformat() if past_dates else ""}\n')

gh_summary = os.environ.get('GITHUB_STEP_SUMMARY')
if gh_summary:
    with open(gh_summary, 'a') as f:
        f.write(f'## Discovery v2: {COUNTY}\n')
        f.write(f'- URL used: `{best_url}`\n')
        f.write(f'- Markdown: {len(best_md)} bytes, HTML: {len(best_html)} bytes\n')
        f.write(f'- Past dates ({len(past_dates)}): {past_dates[:7]}\n')
        f.write(f'- Future dates ({len(future_dates)}): {future_dates[:7]}\n')
        f.write(f'- Rows inserted: {inserted}\n')

# Exit non-zero if discovery yielded nothing useful (today-only is not useful)
if len(past_dates) == 0 and len(future_dates) == 0:
    print(f'NOTE: zero usable dates discovered for {COUNTY}', file=sys.stderr)
    sys.exit(2)
