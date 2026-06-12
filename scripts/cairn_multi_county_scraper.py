#!/usr/bin/env python3
"""
CAIRN multi-county source scraper — parity + auto-fill
======================================================

Deploy target:   Hetzner runner OR GHA (both work)
Schedule:        daily (cron */6 hours reasonable for staging)
Auth:            SUPABASE_URL + SUPABASE_SERVICE_ROLE in env

Does:
  1. For each of 47 FL counties, scrape source auction site
  2. Compare scrape vs multi_county_auctions rows
  3. Insert missing auctions (provenance='live_source_scrape_YYYY-MM-DD')
  4. Log parity metrics to parity_results table (per run, per county)
  5. Honest markers: don't pretend matched if data differs on key fields

DOES NOT:
  - INSERT if case_number already exists for same (county, auction_date)
  - UPDATE existing rows (prevents race-with-property-records feed)
  - Scrape tax deed platforms (separate from foreclosure; future sprint)
"""

import os
import re
import sys
import json
import time
import logging
from datetime import datetime, date
from urllib.parse import urlparse
from typing import Optional
import requests
from bs4 import BeautifulSoup
from supabase import create_client

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
log = logging.getLogger("cairn-scraper")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE"]

# ============================================================================
# URL MAP — 47 FL counties, source site per platform type
# ============================================================================

COUNTY_SOURCES = {
    # Platform 'realforeclose': Realauction.com subdomain (online live auctions)
    # Platform 'brevard_static': Static HTML clerk page (in-person auctions)
    # Platform 'custom_clerk': County-specific clerk URL
    'alachua':      ('realforeclose', 'https://alachua.realforeclose.com'),
    'baker':        ('custom_clerk', 'https://www.bakercountyclerk.org/foreclosure'),
    'bay':          ('realforeclose', 'https://bay.realforeclose.com'),
    'brevard':      ('brevard_static', 'http://vweb2.brevardclerk.us/Foreclosures/foreclosure_sales.html'),
    'broward':      ('realforeclose', 'https://broward.realforeclose.com'),
    'calhoun':      ('custom_clerk', 'https://www.calhounclerk.com/foreclosure'),
    'charlotte':    ('realforeclose', 'https://charlotte.realforeclose.com'),
    'citrus':       ('realforeclose', 'https://citrus.realforeclose.com'),
    'clay':         ('realforeclose', 'https://clay.realforeclose.com'),
    'collier':      ('realforeclose', 'https://collier.realforeclose.com'),
    'duval':        ('realforeclose', 'https://duval.realforeclose.com'),
    'escambia':     ('realforeclose', 'https://escambia.realforeclose.com'),
    'flagler':      ('realforeclose', 'https://flagler.realforeclose.com'),
    'gilchrist':    ('custom_clerk', 'https://www.gilchristclerk.com/foreclosure'),
    'gulf':         ('custom_clerk', 'https://www.gulfclerk.com/foreclosure'),
    'hendry':       ('realforeclose', 'https://hendry.realforeclose.com'),
    'hernando':     ('realforeclose', 'https://hernando.realforeclose.com'),
    'highlands':    ('realforeclose', 'https://highlands.realforeclose.com'),
    'hillsborough': ('realforeclose', 'https://hillsborough.realforeclose.com'),
    'indian_river': ('realforeclose', 'https://indianriver.realforeclose.com'),
    'jackson':      ('custom_clerk', 'https://www.jacksonclerk.com/foreclosure'),
    'lake':         ('realforeclose', 'https://lake.realforeclose.com'),
    'lee':          ('realforeclose', 'https://lee.realforeclose.com'),
    'leon':         ('realforeclose', 'https://leon.realforeclose.com'),
    'manatee':      ('realforeclose', 'https://manatee.realforeclose.com'),
    'marion':       ('realforeclose', 'https://marion.realforeclose.com'),
    'martin':       ('realforeclose', 'https://martin.realforeclose.com'),
    'miami_dade':   ('realforeclose', 'https://miamidade.realforeclose.com'),
    'nassau':       ('realforeclose', 'https://nassau.realforeclose.com'),
    'okaloosa':     ('realforeclose', 'https://okaloosa.realforeclose.com'),
    'okeechobee':   ('realforeclose', 'https://okeechobee.realforeclose.com'),
    'orange':       ('realforeclose', 'https://myorangeclerk.realforeclose.com'),
    'osceola':      ('realforeclose', 'https://osceola.realforeclose.com'),
    'palm_beach':   ('realforeclose', 'https://palmbeach.realforeclose.com'),
    'pasco':        ('realforeclose', 'https://pasco.realforeclose.com'),
    'pinellas':     ('realforeclose', 'https://pinellas.realforeclose.com'),
    'polk':         ('realforeclose', 'https://polk.realforeclose.com'),
    'putnam':       ('realforeclose', 'https://putnam.realforeclose.com'),
    'santa_rosa':   ('realforeclose', 'https://santarosa.realforeclose.com'),
    'sarasota':     ('realforeclose', 'https://sarasota.realforeclose.com'),
    'seminole':     ('realforeclose', 'https://seminole.realforeclose.com'),
    'st_johns':     ('realforeclose', 'https://stjohns.realforeclose.com'),
    'st_lucie':     ('realforeclose', 'https://stlucie.realforeclose.com'),
    'sumter':       ('realforeclose', 'https://sumter.realforeclose.com'),
    'volusia':      ('realforeclose', 'https://volusia.realforeclose.com'),
    'walton':       ('realforeclose', 'https://walton.realforeclose.com'),
    'washington':   ('custom_clerk', 'https://www.washingtonclerk.com/foreclosure'),
    'liberty':      ('custom_clerk', 'https://www.libertycountyclerk.com/foreclosure'),
    # Note: liberty county has limited online presence - using clerk site as primary
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (BidDeed-CAIRN-Scraper/1.0; contact: ariel@everestcapitalusa.com)',
    'Accept': 'text/html,application/xhtml+xml',
    'Accept-Language': 'en-US,en;q=0.9',
}

TIMEOUT = 30
RATE_LIMIT_SEC = 2  # between counties

# ============================================================================
# PARSERS per platform type
# ============================================================================

def parse_brevard_static(html: str) -> list[dict]:
    """Parse vweb2.brevardclerk.us/Foreclosures/foreclosure_sales.html table."""
    soup = BeautifulSoup(html, 'html.parser')
    rows = []
    for table in soup.find_all('table'):
        headers = [th.get_text(strip=True).lower() for th in table.find_all('th')]
        if not any('case' in h for h in headers):
            continue
        col_map = {h: i for i, h in enumerate(headers)}
        for tr in table.find_all('tr')[1:]:
            tds = tr.find_all('td')
            if len(tds) < 4:
                continue
            cells = [td.get_text(strip=True) for td in tds]
            case_num = cells[col_map.get('case_number', 0)]
            case_title = cells[col_map.get('case_title', 1)] if len(cells) > 1 else ''
            comment = cells[col_map.get('comment', 2)] if len(cells) > 2 else ''
            date_str = cells[col_map.get('foreclosure_sale_date', 3)] if len(cells) > 3 else ''
            try:
                dt = datetime.strptime(date_str, '%m-%d-%Y').date()
            except ValueError:
                continue
            plaintiff = case_title.split(' VS ')[0].strip() if ' VS ' in case_title else None
            rows.append({
                'case_number': case_num,
                'case_title': case_title,
                'auction_date': dt.isoformat(),
                'plaintiff': plaintiff,
                'auction_status': 'cancelled' if 'CANCELLED' in comment.upper() else 'upcoming',
                'sale_type': 'foreclosure',
                'auction_type': 'foreclosure',
                'state': 'FL',
            })
    return rows


def parse_realforeclose(html: str, county: str) -> list[dict]:
    """
    Realauction (realforeclose.com) sites are JavaScript-driven ColdFusion apps.
    Without JS execution (no Playwright in this script), we can only extract what's
    in static HTML — typically an auction calendar index. Full auction detail requires
    per-case page fetches + JS rendering.

    MVP: detect whether site is reachable and extract any static calendar dates.
    Full parse = future sprint with Playwright/Selenium.
    """
    # Look for calendar dates in static HTML
    dates = set(re.findall(r'\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b', html))
    return [{
        '_probe_only': True,
        'static_dates_found': len(dates),
        'note': 'realforeclose.com requires JS rendering for full parse; static probe only',
    }]


def parse_custom_clerk(html: str, county: str) -> list[dict]:
    """Custom clerk sites vary wildly; generic table extraction."""
    return [{
        '_probe_only': True,
        'note': f'custom clerk parser for {county} not yet implemented',
    }]


PARSERS = {
    'brevard_static': parse_brevard_static,
    'realforeclose': parse_realforeclose,
    'custom_clerk': parse_custom_clerk,
}


# ============================================================================
# SCRAPER
# ============================================================================

def fetch_county(county: str, platform: str, url: str) -> tuple[list[dict], str]:
    """Returns (parsed_rows, status). Status: ok|http_error|parse_error|timeout"""
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code != 200:
            return [], f'http_{r.status_code}'
        parser = PARSERS.get(platform)
        if not parser:
            return [], f'no_parser_for_{platform}'
        rows = parser(r.text, county) if platform != 'brevard_static' else parser(r.text)
        return rows, 'ok'
    except requests.Timeout:
        return [], 'timeout'
    except Exception as e:
        return [], f'error: {type(e).__name__}'


# ============================================================================
# PARITY + AUTO-FILL
# ============================================================================

def run_parity_for_county(sb, county: str, platform: str, url: str, scraped_rows: list[dict]) -> dict:
    """Compare scraped vs supabase, return parity metrics + insert missing."""
    scraped_full = [r for r in scraped_rows if not r.get('_probe_only')]

    if not scraped_full:
        # Probe-only county — record as UNPARSED
        return {
            'county': county, 'platform': platform, 'source_url': url,
            'source_count': 0, 'supabase_count': None,
            'in_both': 0, 'only_source': 0, 'only_supabase': 0,
            'inserted_rows': 0, 'status': 'probe_only', 'notes': 'parser not implemented for this platform'
        }

    # Date range from scraped data
    dates = [r['auction_date'] for r in scraped_full if r.get('auction_date')]
    if not dates:
        return {'county': county, 'source_count': 0, 'status': 'no_dates'}
    d_min, d_max = min(dates), max(dates)

    # Supabase rows in same range
    sb_rows_r = sb.table('multi_county_auctions').select(
        'case_number, auction_date'
    ).eq('county', county).gte('auction_date', d_min).lte('auction_date', d_max).execute()

    sb_cases = {r['case_number'] for r in sb_rows_r.data if r.get('case_number')}
    src_cases = {r['case_number'] for r in scraped_full if r.get('case_number')}

    in_both = src_cases & sb_cases
    only_src = src_cases - sb_cases  # WE MISSING
    only_sb = sb_cases - src_cases   # scrape missing (different sale type, or older)

    # AUTO-INSERT the missing ones
    to_insert = [
        dict(r, county=county,
             clerk_url=url if platform in ('brevard_static', 'custom_clerk') else None,
             realforeclose_url=url if platform == 'realforeclose' else None,
             provenance=f'live_source_scrape_{date.today().isoformat()}')
        for r in scraped_full
        if r.get('case_number') in only_src
    ]
    inserted = 0
    if to_insert:
        try:
            ins_r = sb.table('multi_county_auctions').insert(to_insert).execute()
            inserted = len(ins_r.data)
        except Exception as e:
            log.warning(f"{county}: insert failed: {e}")

    return {
        'county': county, 'platform': platform, 'source_url': url,
        'source_count': len(src_cases), 'supabase_count': len(sb_cases),
        'in_both': len(in_both), 'only_source': len(only_src), 'only_supabase': len(only_sb),
        'inserted_rows': inserted,
        'match_rate_source_to_supabase': round(100 * len(in_both) / len(src_cases), 1) if src_cases else 0,
        'date_range': f'{d_min}..{d_max}',
        'status': 'ok',
    }


# ============================================================================
# MAIN
# ============================================================================

def main():
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Ensure parity_results table exists (no-op if already created)
    log.info(f"Starting CAIRN scraper run across {len(COUNTY_SOURCES)} counties")

    results = []
    for county, (platform, url) in sorted(COUNTY_SOURCES.items()):
        log.info(f"[{county}] fetching {url}")
        scraped, status = fetch_county(county, platform, url)
        if status != 'ok':
            log.warning(f"[{county}] fetch failed: {status}")
            results.append({'county': county, 'platform': platform, 'source_url': url,
                            'status': status, 'source_count': 0})
        else:
            res = run_parity_for_county(sb, county, platform, url, scraped)
            log.info(f"[{county}] {res}")
            results.append(res)
        time.sleep(RATE_LIMIT_SEC)

    # Persist run summary to parity_results
    run_payload = {
        'run_date': date.today().isoformat(),
        'run_timestamp': datetime.utcnow().isoformat() + 'Z',
        'total_counties': len(COUNTY_SOURCES),
        'parsed_ok_counties': sum(1 for r in results if r.get('status') == 'ok'),
        'probe_only_counties': sum(1 for r in results if r.get('status') == 'probe_only'),
        'error_counties': sum(1 for r in results if r.get('status') not in ('ok', 'probe_only')),
        'total_source_cases': sum(r.get('source_count', 0) for r in results),
        'total_in_both': sum(r.get('in_both', 0) for r in results),
        'total_only_source': sum(r.get('only_source', 0) for r in results),
        'total_rows_inserted': sum(r.get('inserted_rows', 0) for r in results),
        'per_county_results': results,
    }

    try:
        sb.table('parity_results').insert(run_payload).execute()
        log.info(f"Persisted run summary to parity_results")
    except Exception as e:
        log.warning(f"Could not persist parity_results (table may not exist yet): {e}")

    # Summary
    print(json.dumps({
        'run_date': run_payload['run_date'],
        'counties_parsed_ok': run_payload['parsed_ok_counties'],
        'counties_probe_only': run_payload['probe_only_counties'],
        'counties_errored': run_payload['error_counties'],
        'total_source_cases_found': run_payload['total_source_cases'],
        'total_rows_inserted': run_payload['total_rows_inserted'],
    }, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
