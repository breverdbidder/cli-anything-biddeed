#!/usr/bin/env python3
"""Discover most recent past auction date for a RealAuction county.
Hits the CALENDAR page via Firecrawl, parses date links, picks newest past date.
Writes result to public.auction_calendar.

Env required:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, FIRECRAWL_API_KEY,
  COUNTY_SLUG, BASE_URL, PLATFORM, SALE_TYPE
"""
import os, re, sys, json
from datetime import date, datetime
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

CAL_URL = f'{BASE_URL}/index.cfm?zaction=USER&zmethod=CALENDAR'
REST    = f'{SUPABASE_URL}/rest/v1'
H       = {'apikey':SUPABASE_KEY,'Authorization':f'Bearer {SUPABASE_KEY}','Content-Type':'application/json','Prefer':'return=representation'}
TODAY   = date.today()

print(f'>>> Discovery for {COUNTY} ({SALE_TYPE}) @ {CAL_URL}')

# Firecrawl with wait for JS render
body = {'url':CAL_URL,'formats':['markdown'],
        'actions':[{'type':'wait','milliseconds':8000}],
        'onlyMainContent':False,'timeout':90000}
r = requests.post('https://api.firecrawl.dev/v1/scrape',
    headers={'Authorization':f'Bearer {FIRECRAWL_KEY}','Content-Type':'application/json'},
    json=body, timeout=120)

if r.status_code != 200:
    print(f'ERROR: firecrawl {r.status_code}: {r.text[:300]}', file=sys.stderr)
    sys.exit(1)

md = r.json().get('data',{}).get('markdown','')
print(f'Markdown bytes: {len(md)}')

# Extract candidate dates from multiple patterns:
#   - href params: AUCTIONDATE=05/14/2026
#   - javascript:openDay('05/14/2026')
#   - data attributes: data-date="2026-05-14"
#   - markdown links: [14](.../05/14/2026...)
dates_found = set()

# Pattern 1: MM/DD/YYYY anywhere
for m in re.finditer(r'(\d{2})/(\d{2})/(\d{4})', md):
    try:
        d = date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
        if 2020 <= d.year <= 2030:
            dates_found.add(d)
    except (ValueError, OverflowError):
        pass

# Pattern 2: YYYY-MM-DD anywhere
for m in re.finditer(r'(\d{4})-(\d{2})-(\d{2})', md):
    try:
        d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if 2020 <= d.year <= 2030:
            dates_found.add(d)
    except (ValueError, OverflowError):
        pass

print(f'Candidate dates found: {len(dates_found)}')
past_dates = sorted([d for d in dates_found if d <= TODAY], reverse=True)
future_dates = sorted([d for d in dates_found if d > TODAY])
print(f'Past: {past_dates[:5]}  Future: {future_dates[:5]}')

if not past_dates:
    print(f'ERROR: No past auction dates found for {COUNTY}. Calendar may be empty or markdown patterns are wrong.', file=sys.stderr)
    # Dump first 2KB of markdown for debugging
    print('--- markdown preview ---', file=sys.stderr)
    print(md[:2000], file=sys.stderr)
    sys.exit(2)

most_recent_past = past_dates[0]
next_future = future_dates[0] if future_dates else None

print(f'MOST RECENT PAST: {most_recent_past}')
print(f'NEXT FUTURE: {next_future}')

# Upsert into auction_calendar
# Schema is minimal: county TEXT, auction_date DATE, status TEXT
for d in past_dates[:5] + ([next_future] if next_future else []):
    if d is None: continue
    payload = {
        'county': COUNTY,
        'auction_date': d.isoformat(),
        'status': 'discovered_via_calendar' if d <= TODAY else 'upcoming_via_calendar'
    }
    resp = requests.post(f'{REST}/auction_calendar',
                         json=payload, headers={**H, 'Prefer':'resolution=merge-duplicates,return=minimal'},
                         timeout=30)
    if resp.status_code >= 400:
        print(f'  ! upsert {d}: {resp.status_code} {resp.text[:200]}', file=sys.stderr)
    else:
        print(f'  + upserted {d} ({payload["status"]})')

# Write a summary for the GHA Step Summary
summary = {
    'county': COUNTY,
    'sale_type': SALE_TYPE,
    'platform': PLATFORM,
    'calendar_url': CAL_URL,
    'markdown_bytes': len(md),
    'past_dates_found': len(past_dates),
    'future_dates_found': len(future_dates),
    'most_recent_past': most_recent_past.isoformat(),
    'next_future': next_future.isoformat() if next_future else None,
    'top5_past': [d.isoformat() for d in past_dates[:5]],
}
print(f'\n=== DISCOVERY SUMMARY ===\n{json.dumps(summary, indent=2)}')

# GitHub Step Summary support
gh_summary_path = os.environ.get('GITHUB_STEP_SUMMARY')
if gh_summary_path:
    with open(gh_summary_path, 'a') as f:
        f.write(f'## Discovery: {COUNTY}\n```json\n{json.dumps(summary, indent=2)}\n```\n')

# Set GHA output for downstream steps
gh_output = os.environ.get('GITHUB_OUTPUT')
if gh_output:
    with open(gh_output, 'a') as f:
        f.write(f'most_recent_past={most_recent_past.isoformat()}\n')
        f.write(f'next_future={next_future.isoformat() if next_future else ""}\n')
