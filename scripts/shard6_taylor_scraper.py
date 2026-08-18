#!/usr/bin/env python3
"""
SHARD-6 Taylor County Foreclosure/Tax-Deed Scraper
====================================================
Source: taylorclerk.com (in-person courthouse auctions)
Target table: multi_county_auctions
County: taylor (FL FIPS 12123)

Usage:
  python scripts/shard6_taylor_scraper.py
  python scripts/shard6_taylor_scraper.py --dry-run

Taylor County holds in-person foreclosure/tax-deed sales at the courthouse
(108 N Jefferson St, Perry FL 32347, Tues/Thurs 11am). No online auction
platform (taylor.realforeclose.com / taylor.realtaxdeed.com both 302-redirect
to realauction.com — confirmed dead 2026-06-24). taylor.realtdm.com is a live
TEST case-management instance but returns zero cases under every filter
combination tried (all 20 case statuses, 2020-2027 date range, wildcard party
name/address/case-number searches — confirmed empty 2026-07-10, not a scraper
bug). Real data instead comes from taylorclerk.com's structured department
pages:
  - https://taylorclerk.com/departments/foreclosure-sales/  (real case data)
  - https://taylorclerk.com/departments/tax-deeds/            (real case data,
    may legitimately be empty if no tax deed sales are currently scheduled)

Fail-loud invariant: if this script parses>0 rows but inserts=0, it raises.
It never falls back to placeholder/synthetic rows.

Does NOT set parity_status: this scraper only confirms a case is still
listed, it doesn't diff against a second source. clerk-ssot-parity.yml
(scripts/clerk_ssot/run_parity.py) owns parity_status and marks clean
matches PARITY_OK — a prior version of this script hardcoded
parity_status='matched_clean' on every upsert, which silently downgraded
rows run_parity.py had already verified (PARITY_OK doesn't count as a
weaker string than a literal 'matched_clean' with a non-tier1 source under
pencil_dod_evaluate_county's matched_clean filter), causing letter C to
regress on every daily run that touched an already-verified case.
"""
import os
import sys
import json
import html
import logging
import argparse
import re
from datetime import date, datetime, timezone
import httpx
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
log = logging.getLogger('taylor-scraper')

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://mocerqjnksmhcjzxrewo.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('SUPABASE_KEY', '')
BASE = f'{SUPABASE_URL}/rest/v1'
HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'resolution=merge-duplicates,return=representation',
}

TAYLOR_FC_URL = 'https://taylorclerk.com/departments/foreclosure-sales/'
TAYLOR_TD_URL = 'https://taylorclerk.com/departments/tax-deeds/'

WEB_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (BidDeed-SHARD6-Scraper/1.0; contact: ariel@everestcapitalusa.com)',
}


def parse_taylor_sales(html: str, sale_type: str, source_url: str) -> list[dict]:
    """Parse Taylor County clerk sale page for scheduled auctions.

    Page structure (verified 2026-07-10): each sale is a
    <div class="border border-primary/20 ..."> containing labeled
    Status / Sale Date / Case Number / Judgement Amount / Parties / Address
    fields, plus a link to the case PDF.
    """
    soup = BeautifulSoup(html, 'html.parser')
    records = []
    seen_cases = set()

    for card in soup.find_all('div', class_=re.compile(r'\bborder-primary/20\b')):
        text = card.get_text(separator='|', strip=True)
        if 'Case Number' not in text or 'Sale Date' not in text:
            continue

        labels = card.find_all('label')
        field_map = {}
        for label in labels:
            key = label.get_text(strip=True)
            strong = label.find_next_sibling('strong')
            if strong is not None:
                field_map[key] = strong.get_text(strip=True)
            else:
                # Address field uses <a> instead of <strong>
                sib = label.find_next_sibling()
                if sib is not None:
                    field_map[key] = sib.get_text(strip=True)

        case_number = field_map.get('Case Number', '').strip()
        sale_date_str = field_map.get('Sale Date', '').strip()
        status = field_map.get('Status', 'scheduled').strip().lower()
        judgment_str = field_map.get('Judgement Amount', '').replace('$', '').replace(',', '').strip()
        parties = field_map.get('Parties', '').strip()
        address = field_map.get('Address', '').strip()

        if not case_number or not sale_date_str or case_number in seen_cases:
            continue
        seen_cases.add(case_number)

        try:
            sale_date = datetime.strptime(sale_date_str, '%m/%d/%Y').date()
        except ValueError:
            log.warning(f'Could not parse date: {sale_date_str!r} for case {case_number}')
            continue

        judgment = float(judgment_str) if judgment_str else None
        if status in ('scheduled', 'upcoming'):
            auction_status = 'upcoming'
        elif status in ('cancelled', 'canceled', 'redeemed'):
            auction_status = 'cancelled'
        elif 'sold' in status:
            auction_status = 'sold'
        else:
            auction_status = 'upcoming'
        property_address = address if address and 'legal description' not in address.lower() else 'TAYLOR COUNTY, FL'

        pdf_link = card.find_next('a', href=re.compile(r'\.pdf$'))
        case_pdf_url = pdf_link['href'] if pdf_link else None

        records.append({
            'county': 'taylor',
            'case_number': case_number,
            'sale_type': sale_type,
            'auction_type': sale_type,
            'auction_date': sale_date.isoformat(),
            'auction_status': auction_status,
            'judgment_amount': judgment,
            'opening_bid': judgment,
            'property_address': property_address,
            'plaintiff': parties[:200] if parties else None,
            'state': 'FL',
            'clerk_url': source_url,
            'source_url': case_pdf_url,
            'provenance': f'live_source_scrape_{date.today().isoformat()}',
            'data_source': 'taylorclerk.com_shard6_scraper',
            'source_platform': 'clerk_website',
        })

    return records


def parse_taylor_tax_deeds_json(html_text: str, source_url: str) -> list[dict]:
    """Parse Taylor County tax-deeds page for scheduled tax deed auctions.

    Page structure (verified 2026-07-19): unlike foreclosure-sales, this page
    embeds a Vue component with the full dataset as an HTML-entity-encoded
    JSON attribute:
      <tax-deed-sales :taxdeeds="[{&quot;ID&quot;:...,&quot;title&quot;:&quot;TDA 26-031&quot;,
        &quot;cert&quot;:...,&quot;parcel&quot;:&quot;R09486-414&quot;,&quot;sale_date&quot;:...,
        &quot;opening_bid&quot;:...,&quot;cert_holder&quot;:...,&quot;status&quot;:&quot;scheduled&quot;,
        &quot;iso_sale_date&quot;:&quot;2026-08-17 11:00:00&quot;,...}]"></tax-deed-sales>
    Only status=='scheduled' items are active auctions; 'redeemed' (and any
    other non-scheduled status) are excluded — those are closed cases, not
    upcoming auctions.
    """
    match = re.search(r'taxdeeds="(\[.*?\])"', html_text)
    if not match:
        log.warning('Could not find taxdeeds="[...]" attribute on tax-deeds page')
        return []

    try:
        items = json.loads(html.unescape(match.group(1)))
    except json.JSONDecodeError as e:
        log.warning(f'Failed to parse taxdeeds JSON: {e}')
        return []

    records = []
    seen_cases = set()

    for item in items:
        status = str(item.get('status', '')).strip().lower()
        if status != 'scheduled':
            continue

        case_number = str(item.get('title', '')).strip()
        if not case_number or case_number in seen_cases:
            continue

        date_str = item.get('iso_sale_date') or item.get('sale_date')
        if not date_str:
            log.warning(f'No sale date for tax deed case {case_number}')
            continue
        try:
            if 'iso_sale_date' in item and item['iso_sale_date']:
                sale_date = datetime.strptime(item['iso_sale_date'], '%Y-%m-%d %H:%M:%S').date()
            else:
                sale_date = datetime.strptime(item['sale_date'], '%b %d, %Y %I:%M %p').date()
        except ValueError:
            log.warning(f'Could not parse date: {date_str!r} for case {case_number}')
            continue

        seen_cases.add(case_number)

        opening_bid_str = str(item.get('opening_bid', '') or '').replace('$', '').replace(',', '').strip()
        opening_bid = float(opening_bid_str) if opening_bid_str else None
        parcel_id = str(item.get('parcel', '')).strip() or None
        cert_holder = str(item.get('cert_holder', '')).strip() or None
        item_link = item.get('link') or None

        records.append({
            'county': 'taylor',
            'case_number': case_number,
            'sale_type': 'tax_deed',
            'auction_type': 'tax_deed',
            'auction_date': sale_date.isoformat(),
            'auction_status': 'upcoming',
            'judgment_amount': opening_bid,
            'opening_bid': opening_bid,
            'property_address': 'TAYLOR COUNTY, FL',
            'parcel_id': parcel_id,
            'plaintiff': cert_holder[:200] if cert_holder else None,
            'state': 'FL',
            'clerk_url': source_url,
            'source_url': item_link,
            'provenance': f'live_source_scrape_{date.today().isoformat()}',
            'data_source': 'taylorclerk.com_shard6_scraper',
            'source_platform': 'clerk_website',
        })

    return records


def upsert_records(records: list[dict], dry_run: bool = False) -> int:
    """Upsert records into multi_county_auctions. Returns count inserted/updated."""
    if not records:
        return 0
    if dry_run:
        log.info(f'DRY RUN: would upsert {len(records)} records')
        for r in records:
            log.info(f"  {r['case_number']} | {r['auction_date']} | {r.get('property_address')}")
        return 0

    # PostgREST requires every object in a single bulk upsert to share the
    # same key set ("All object keys must match"). Foreclosure records (no
    # parcel_id) and tax-deed records (with parcel_id) have different key
    # shapes, so batch by key-shape to avoid nulling out unrelated columns
    # via a forced key union.
    client = httpx.Client(timeout=60)
    batches: dict[tuple, list[dict]] = {}
    for rec in records:
        batches.setdefault(tuple(sorted(rec.keys())), []).append(rec)

    inserted = 0
    for batch in batches.values():
        r = None
        for attempt in range(3):
            r = client.post(
                f'{BASE}/multi_county_auctions',
                headers=HEADERS,
                params={'on_conflict': 'county,case_number,sale_type'},
                content=json.dumps(batch),
            )
            if r.status_code in (200, 201) or r.status_code < 500:
                break
            log.warning(f'Upsert attempt {attempt + 1}/3 got {r.status_code} (transient), retrying...')
        if r.status_code in (200, 201):
            inserted += len(r.json())
        else:
            log.error(f'Upsert error: {r.status_code} {r.text[:300]}')
    return inserted


def main():
    parser = argparse.ArgumentParser(description='SHARD-6 Taylor County Scraper')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    client = httpx.Client(timeout=30)
    all_records = []

    # Scrape foreclosure sales
    log.info(f'Fetching Taylor foreclosure sales from {TAYLOR_FC_URL}')
    r = client.get(TAYLOR_FC_URL, headers=WEB_HEADERS)
    if r.status_code == 200:
        fc_records = parse_taylor_sales(r.text, 'foreclosure', TAYLOR_FC_URL)
        log.info(f'Parsed {len(fc_records)} foreclosure auctions')
        all_records.extend(fc_records)
    else:
        log.warning(f'Foreclosure page returned {r.status_code}')

    # Scrape tax deed sales (may legitimately be empty).
    # NOTE: tax-deeds page is structurally different from foreclosure-sales
    # (a Vue component with a taxdeeds="[...]" JSON attribute, not the
    # border-primary/20 card markup) so it needs its own parser.
    log.info(f'Fetching Taylor tax deed sales from {TAYLOR_TD_URL}')
    r2 = client.get(TAYLOR_TD_URL, headers=WEB_HEADERS)
    if r2.status_code == 200:
        td_records = parse_taylor_tax_deeds_json(r2.text, TAYLOR_TD_URL)
        log.info(f'Parsed {len(td_records)} tax deed auctions')
        all_records.extend(td_records)
    else:
        log.warning(f'Tax deed page returned {r2.status_code}')

    parsed = len(all_records)
    if parsed == 0:
        log.info('No scheduled auctions found for Taylor County (honest zero)')
        print(json.dumps({'county': 'taylor', 'parsed': 0, 'inserted': 0, 'status': 'no_data'}))
        sys.exit(0)

    inserted = upsert_records(all_records, dry_run=args.dry_run)

    # Fail-loud: parsed>0 but inserted=0 must raise, never fall back to fabricated rows
    if parsed > 0 and inserted == 0 and not args.dry_run:
        raise RuntimeError(f'FAIL-LOUD: parsed={parsed} but inserted=0 for taylor county')

    result = {
        'county': 'taylor',
        'source': 'taylorclerk.com',
        'parsed': parsed,
        'inserted': inserted,
        'run_date': date.today().isoformat(),
        'status': 'ok',
    }
    print(json.dumps(result))
    log.info(f'VERIFIED: taylor parsed={parsed} inserted={inserted}')


if __name__ == '__main__':
    main()
