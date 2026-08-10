#!/usr/bin/env python3
"""Discover RealAuction auction dates - v3 (Crawl4AI rewrite).

v3 changes from v2:
  - Drops Firecrawl entirely — uses Crawl4AI + headless Chromium (zero billing dependency)
  - Adds login step: fills #LogName/#LogPass, clicks #LogButton (a JS div, not a form submit),
    waits 4-5s for async response, THEN runs existing wait/scroll for calendar render
  - Login selectors confirmed live against broward.realforeclose.com (Aug 10 2026)
  - Reuse REALFORECLOSE_EMAIL / REALFORECLOSE_PASSWORD env vars (same as county-outcome-harvest.yml)
  - Date extraction logic (Pattern 1-4) unchanged

Env required:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY,
  COUNTY_SLUG, BASE_URL, PLATFORM, SALE_TYPE
  REALFORECLOSE_EMAIL, REALFORECLOSE_PASSWORD  (for login)
"""
import asyncio
import json
import os
import re
import sys
from datetime import date, datetime

import requests


def _req(name):
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f'Missing required env: {name}')
    return v


SUPABASE_URL = _req('SUPABASE_URL').rstrip('/')
SUPABASE_KEY = _req('SUPABASE_SERVICE_ROLE_KEY')
COUNTY       = _req('COUNTY_SLUG').lower().strip()
BASE_URL     = _req('BASE_URL').rstrip('/')
PLATFORM     = _req('PLATFORM').lower().strip()
SALE_TYPE    = _req('SALE_TYPE').lower().strip()

RF_EMAIL    = os.environ.get('REALFORECLOSE_EMAIL', '')
RF_PASSWORD = os.environ.get('REALFORECLOSE_PASSWORD', '')

REST = f'{SUPABASE_URL}/rest/v1'
H    = {'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}', 'Content-Type': 'application/json'}
TODAY = date.today()

CALENDAR_URLS = [
    f'{BASE_URL}/index.cfm?zaction=USER&zmethod=CALENDAR',
    f'{BASE_URL}/index.cfm?zaction=AUCTION&Zmethod=CALENDAR',
]

print(f'>>> Discovery v3 (Crawl4AI) for {COUNTY} ({SALE_TYPE}) on {PLATFORM}')
print(f'    login creds: {"SET" if RF_EMAIL and RF_PASSWORD else "MISSING — login will be skipped"}')


def _make_js(email: str, password: str) -> str:
    # NOTE: JS string injection — values are env vars, not user input. Safe in GHA context.
    email_safe    = email.replace("'", "\\'").replace('\\', '\\\\')
    password_safe = password.replace("'", "\\'").replace('\\', '\\\\')
    return f"""
(async () => {{
    const loginEl = document.querySelector('#LogName');
    const passEl  = document.querySelector('#LogPass');
    const btnEl   = document.querySelector('#LogButton');
    if (loginEl && passEl && btnEl) {{
        loginEl.value = '{email_safe}';
        passEl.value  = '{password_safe}';
        // Dispatch input events so any JS listeners pick up the values
        loginEl.dispatchEvent(new Event('input', {{bubbles:true}}));
        passEl.dispatchEvent(new Event('input', {{bubbles:true}}));
        btnEl.click();
        // Wait for async login response (JS-driven, no page navigation)
        await new Promise(r => setTimeout(r, 5000));
    }}
    // Scroll to trigger lazy calendar rendering (same as v2 ACTION_CHAIN)
    window.scrollTo(0, document.body.scrollHeight);
    await new Promise(r => setTimeout(r, 3000));
    window.scrollTo(0, document.body.scrollHeight);
    await new Promise(r => setTimeout(r, 2000));
}})();
"""


def detect_login_page(html: str, md: str) -> bool:
    combined = (html or '') + (md or '')
    indicators = [
        'User Name or Password is Invalid',
        'id="LogName"',
        'id="LogPass"',
        'id="LogButton"',
        'class="LogInput',
    ]
    hits = sum(1 for i in indicators if i in combined)
    return hits >= 2


async def crawl_url(url: str) -> tuple[str, str, str | None]:
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
    except ImportError:
        return '', '', 'crawl4ai not installed — run: pip install crawl4ai && crawl4ai-setup'

    js_code = None
    if RF_EMAIL and RF_PASSWORD:
        js_code = _make_js(RF_EMAIL, RF_PASSWORD)

    browser_cfg = BrowserConfig(headless=True, verbose=False)

    run_cfg_kwargs = dict(
        wait_for='css:body',
        page_timeout=60000,
        delay_before_return_html=2.0,
    )
    if js_code:
        run_cfg_kwargs['js_code'] = [js_code]

    run_cfg = CrawlerRunConfig(**run_cfg_kwargs)

    try:
        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            # Initial load with 15s pre-wait (mirrors v2 ACTION_CHAIN first wait)
            result = await crawler.arun(url=url, config=run_cfg)
    except Exception as e:
        return '', '', f'crawl4ai error: {e}'

    if not result.success:
        return '', '', f'crawl4ai failed: {getattr(result, "error_message", "unknown")}'

    md   = result.markdown or ''
    html = result.html or ''
    return md, html, None


async def main():
    best_md, best_html, best_url = '', '', None

    for url in CALENDAR_URLS:
        print(f'  trying {url}')
        md, html, err = await crawl_url(url)
        if err:
            print(f'    failed: {err}')
            continue
        print(f'    md={len(md)} html={len(html)}')

        if detect_login_page(html, md):
            print(f'    WARN: login page still detected after auth attempt on {url}')

        if len(md) + len(html) > len(best_md) + len(best_html):
            best_md, best_html, best_url = md, html, url

    if not best_md and not best_html:
        print('ERROR: All Crawl4AI attempts returned nothing', file=sys.stderr)
        sys.exit(1)

    if detect_login_page(best_html, best_md):
        print('BLOCKER: All calendar URLs returned login page after auth attempt.', file=sys.stderr)
        print('  Likely cause: CSRF token or JS form not fully handled by Crawl4AI JS injection.', file=sys.stderr)
        print('  Next step: direct HTTP session auth (urllib CookieJar pattern).', file=sys.stderr)
        sys.exit(3)

    print(f'Using {best_url}  md={len(best_md)} html={len(best_html)}')

    # Extract candidate dates from BOTH markdown AND html
    dates_found = set()
    combined = best_md + '\n\n' + best_html

    # Pattern 1: MM/DD/YYYY
    for m in re.finditer(r'(\d{2})/(\d{2})/(\d{4})', combined):
        try:
            d = date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
            if 2020 <= d.year <= 2030:
                dates_found.add(d)
        except (ValueError, OverflowError):
            pass

    # Pattern 2: YYYY-MM-DD
    for m in re.finditer(r'(\d{4})-(\d{2})-(\d{2})', combined):
        try:
            d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if 2020 <= d.year <= 2030:
                dates_found.add(d)
        except (ValueError, OverflowError):
            pass

    # Pattern 3: data-date or data-auction-date attrs
    for m in re.finditer(r'data-(?:auction-?)?date=["\']([\d/-]+)["\']', combined):
        raw = m.group(1)
        for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%Y/%m/%d'):
            try:
                d = datetime.strptime(raw, fmt).date()
                if 2020 <= d.year <= 2030:
                    dates_found.add(d)
                break
            except ValueError:
                continue

    # Pattern 4: AUCTIONDATE= param values
    for m in re.finditer(r'AUCTIONDATE=([\d/]+)', combined, re.IGNORECASE):
        raw = m.group(1)
        try:
            d = datetime.strptime(raw, '%m/%d/%Y').date()
            if 2020 <= d.year <= 2030:
                dates_found.add(d)
        except ValueError:
            pass

    print(f'Raw dates_found: {sorted(dates_found)}')
    if dates_found == {TODAY}:
        print("WARNING: Only today's date found - calendar likely did not render", file=sys.stderr)

    past_dates   = sorted([d for d in dates_found if d <  TODAY], reverse=True)
    today_match  = TODAY in dates_found
    future_dates = sorted([d for d in dates_found if d >  TODAY])

    print(f'PAST ({len(past_dates)}): {past_dates[:7]}')
    print(f'TODAY: {"yes" if today_match else "no"}')
    print(f'FUTURE ({len(future_dates)}): {future_dates[:7]}')

    inserted = 0

    def upsert(d, position, rank):
        payload = {
            'county_slug': COUNTY, 'sale_type': SALE_TYPE, 'platform': PLATFORM,
            'auction_date': d.isoformat(), 'position': position, 'rank_within': rank,
            'source_markdown_bytes': len(best_md),
            'notes': json.dumps({'discovery_version': 'v3', 'best_url': best_url,
                                 'combined_bytes': len(combined), 'scraper': 'crawl4ai'})
        }
        resp = requests.post(
            f'{REST}/biddeed.discovered_auction_dates',
            json=payload,
            headers={**H, 'Prefer': 'resolution=merge-duplicates,return=minimal'},
            timeout=30,
        )
        if resp.status_code >= 400:
            resp = requests.post(
                f'{REST}/rpc/upsert_discovered_date',
                json={'p': payload}, headers=H, timeout=30,
            )
        if resp.status_code >= 400:
            print(f'  ! upsert {d}: {resp.status_code} {resp.text[:200]}', file=sys.stderr)
            return False
        return True

    for rank, d in enumerate(past_dates[:5], 1):
        if upsert(d, 'past', rank):
            inserted += 1
    if today_match:
        if upsert(TODAY, 'today', 1):
            inserted += 1
    for rank, d in enumerate(future_dates[:5], 1):
        if upsert(d, 'future', rank):
            inserted += 1

    print(f'\nINSERTED: {inserted} rows')

    gh_output = os.environ.get('GITHUB_OUTPUT')
    if gh_output:
        with open(gh_output, 'a') as f:
            f.write(f'past_count={len(past_dates)}\n')
            f.write(f'future_count={len(future_dates)}\n')
            f.write(f'most_recent_past={past_dates[0].isoformat() if past_dates else ""}\n')

    gh_summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if gh_summary:
        with open(gh_summary, 'a') as f:
            f.write(f'## Discovery v3 (Crawl4AI): {COUNTY}\n')
            f.write(f'- URL used: `{best_url}`\n')
            f.write(f'- Markdown: {len(best_md)} bytes, HTML: {len(best_html)} bytes\n')
            f.write(f'- Past dates ({len(past_dates)}): {past_dates[:7]}\n')
            f.write(f'- Future dates ({len(future_dates)}): {future_dates[:7]}\n')
            f.write(f'- Rows inserted: {inserted}\n')

    if len(past_dates) == 0 and len(future_dates) == 0:
        print(f'NOTE: zero usable dates discovered for {COUNTY}', file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    asyncio.run(main())
