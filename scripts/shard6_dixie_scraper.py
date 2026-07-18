#!/usr/bin/env python3
"""
SHARD-6 Dixie County Foreclosure Scraper
=========================================
Source: dixieclerk.com (in-person courthouse auctions)
Target table: multi_county_auctions
County: dixie (FL FIPS 12029)

Usage:
  python scripts/shard6_dixie_scraper.py
  python scripts/shard6_dixie_scraper.py --dry-run

Dixie County holds in-person foreclosure sales at the courthouse.
No online auction platform — data must be scraped from dixieclerk.com/court-services/foreclosure-sales/
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
log = logging.getLogger('dixie-scraper')

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://mocerqjnksmhcjzxrewo.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('SUPABASE_KEY', '')
BASE = f'{SUPABASE_URL}/rest/v1'
HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'resolution=merge-duplicates,return=representation',
}

DIXIE_FC_URL = 'https://dixieclerk.com/departments-services/court-services/foreclosure-sales/'
DIXIE_TD_URL = 'https://dixieclerk.com/departments-services/court-services/tax-deed-sales/'

WEB_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (BidDeed-SHARD6-Scraper/1.0; contact: ariel@everestcapitalusa.com)',
}


def parse_dixie_sales(html: str, sale_type: str) -> list[dict]:
    """Parse Dixie County clerk sale page for upcoming auctions."""
    soup = BeautifulSoup(html, 'html.parser')
    records = []
    seen_cases = set()

    # The clerk page has deeply nested divs; find the innermost div containing all sale fields
    # We de-duplicate by case_number so nested copies don't produce multiple records
    SALE_FIELDS = {'Sale Date', 'Case Number', 'Parcel ID', 'Judgement Amount', 'Parties', 'Status'}

    for section in soup.find_all('div'):
        text = section.get_text(separator='|', strip=True)
        # Must have both Sale Date AND Case Number to be a sale record
        if 'Sale Date' not in text or 'Case Number' not in text:
            continue
        # Skip if any child div would also match (prefer deepest match)
        child_divs = section.find_all('div')
        if any('Case Number' in c.get_text() and 'Sale Date' in c.get_text() for c in child_divs):
            continue

        parts = [p.strip() for p in text.split('|') if p.strip()]
        field_map = {}
        for i, part in enumerate(parts):
            if part in SALE_FIELDS and i + 1 < len(parts):
                field_map[part] = parts[i + 1]

        case_number = field_map.get('Case Number', '').strip()
        sale_date_str = field_map.get('Sale Date', '').strip()
        parcel_id = field_map.get('Parcel ID', '').strip()
        judgment_str = field_map.get('Judgement Amount', '').replace('$', '').replace(',', '').strip()
        parties = field_map.get('Parties', '').strip()
        status = field_map.get('Status', 'upcoming').strip().lower()

        if not case_number or not sale_date_str or case_number in seen_cases:
            continue
        seen_cases.add(case_number)

        try:
            sale_date = datetime.strptime(sale_date_str, '%m/%d/%Y').date()
        except ValueError:
            log.warning(f'Could not parse date: {sale_date_str}')
            continue

        plaintiff = parties.split(' VS.')[0].strip() if ' VS.' in parties else parties[:100]
        judgment = float(judgment_str) if judgment_str else None

        records.append({
            'county': 'dixie',
            'case_number': case_number,
            'sale_type': sale_type,
            'auction_type': sale_type,
            'auction_date': sale_date.isoformat(),
            'auction_status': status if status in ('upcoming', 'cancelled', 'sold') else 'upcoming',
            'judgment_amount': judgment,
            'parcel_id': parcel_id or None,
            'property_address': 'DIXIE COUNTY, FL',
            'plaintiff': plaintiff,
            'state': 'FL',
            'clerk_url': DIXIE_FC_URL if sale_type == 'foreclosure' else DIXIE_TD_URL,
            'provenance': f'live_source_scrape_{date.today().isoformat()}',
            'data_source': 'dixieclerk.com_shard6_scraper',
            'source_platform': 'clerk_website',
        })

    return records


def parse_dixie_taxdeed_json(html_text: str) -> list[dict]:
    """
    Parse Dixie County tax-deed-sales page.

    VERIFIED 2026-07-10 (Gold Standard shard-8, run3534): the page does NOT
    render sale records as plain div text (parse_dixie_sales() above matches
    nothing against it) -- it embeds the full dataset as a Vue component
    attribute: <tax-deed-sales :taxdeeds="[{...}]">, HTML-entity-encoded JSON.
    This was the root cause of dixie C/D sitting at 0% despite 31 real sale
    records being live on the source site. See
    migrations/20260710_gold_standard_shard8_dixie_real_tax_deed_harvest.sql
    for the one-time backfill this parser is meant to keep current going
    forward.

    Only maps a definitive outcome (auction_status='sold'/'redeemed') when
    the clerk's own status is unambiguous AND the sale date has already
    passed. Records where status='scheduled' but the sale date is already
    past are a known data-quality inconsistency on the source site itself --
    left as 'upcoming' (no sold_amount) rather than guessed, per Honesty
    Protocol (BLANK > WRONG).
    """
    m = re.search(r':taxdeeds="(\[.*?\])"', html_text, re.S)
    if not m:
        return []
    try:
        raw_records = json.loads(html.unescape(m.group(1)))
    except json.JSONDecodeError as e:
        log.warning(f'Could not parse tax deed JSON blob: {e}')
        return []

    today = date.today()
    records = []
    for r in raw_records:
        parcel = (r.get('parcel') or '').strip()
        if not parcel:
            continue
        case_number = f'DIXIE-SYNTH-{parcel}'
        try:
            sale_date = datetime.strptime(r['sale_date'].split(' 11:00')[0].strip(), '%b %d, %Y').date()
        except (ValueError, KeyError):
            log.warning(f'Could not parse tax deed sale_date for parcel {parcel}: {r.get("sale_date")!r}')
            continue

        clerk_status = (r.get('status') or '').strip().lower()
        is_past = sale_date < today
        if clerk_status in ('sold', 'redeemed') and is_past:
            auction_status = clerk_status
            sold_amount = float(r['sold_amount']) if r.get('sold_amount') else None
        else:
            auction_status = 'upcoming'
            sold_amount = None

        records.append({
            'county': 'dixie',
            'case_number': case_number,
            'sale_type': 'tax_deed',
            'auction_type': 'tax_deed',
            'auction_date': sale_date.isoformat(),
            'auction_status': auction_status,
            'sold_amount': sold_amount,
            'opening_bid': float(r['opening_bid']) if r.get('opening_bid') else None,
            'cert_number': r.get('cert') or None,
            'cert_holder': (r.get('cert_holder') or '').strip() or None,
            'parcel_id': parcel,
            'property_address': 'DIXIE COUNTY, FL',
            'state': 'FL',
            'clerk_url': DIXIE_TD_URL,
            'provenance': f'live_source_scrape_{today.isoformat()}',
            'data_source': 'dixieclerk_tax_deed_page_live_v1',
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
            log.info(f'  {r["case_number"]} | {r["auction_date"]} | parcel={r.get("parcel_id")}')
        return 0

    client = httpx.Client(timeout=60)
    r = client.post(
        f'{BASE}/multi_county_auctions',
        headers=HEADERS,
        params={'on_conflict': 'county,case_number,sale_type'},
        content=json.dumps(records),
    )
    if r.status_code in (200, 201):
        inserted = len(r.json())
        return inserted
    else:
        log.error(f'Upsert error: {r.status_code} {r.text[:200]}')
        return 0


def main():
    parser = argparse.ArgumentParser(description='SHARD-6 Dixie County Scraper')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    client = httpx.Client(timeout=30)
    fc_records = []
    td_records = []

    # Scrape foreclosure sales
    log.info(f'Fetching Dixie foreclosure sales from {DIXIE_FC_URL}')
    r = client.get(DIXIE_FC_URL, headers=WEB_HEADERS)
    if r.status_code == 200:
        fc_records = parse_dixie_sales(r.text, 'foreclosure')
        log.info(f'Parsed {len(fc_records)} foreclosure auctions')
    else:
        log.warning(f'Foreclosure page returned {r.status_code}')

    # Scrape tax deed sales (Vue-embedded JSON -- see parse_dixie_taxdeed_json docstring)
    log.info(f'Fetching Dixie tax deed sales from {DIXIE_TD_URL}')
    r2 = client.get(DIXIE_TD_URL, headers=WEB_HEADERS)
    if r2.status_code == 200:
        td_records = parse_dixie_taxdeed_json(r2.text)
        log.info(f'Parsed {len(td_records)} tax deed auctions')
    else:
        log.warning(f'Tax deed page returned {r2.status_code}')

    # Fail-loud if parsed > 0 and inserted = 0
    parsed = len(fc_records) + len(td_records)
    if parsed == 0:
        log.info('No upcoming auctions found for Dixie County')
        print(json.dumps({'county': 'dixie', 'parsed': 0, 'inserted': 0, 'status': 'no_data'}))
        sys.exit(0)

    # PostgREST bulk upsert requires every object in one POST to share the
    # exact same key set (PGRST102: "All object keys must match"). fc_records
    # and td_records have different shapes (judgment_amount/plaintiff vs.
    # sold_amount/opening_bid/cert_number/cert_holder) -- root cause of the
    # 2026-07-18 FAIL-LOUD (parsed=33, inserted=0). Upsert each batch
    # separately instead of concatenating them.
    inserted = upsert_records(fc_records, dry_run=args.dry_run) + upsert_records(td_records, dry_run=args.dry_run)

    if parsed > 0 and inserted == 0 and not args.dry_run:
        raise RuntimeError(f'FAIL-LOUD: parsed={parsed} but inserted=0 for dixie county')

    result = {
        'county': 'dixie',
        'source': 'dixieclerk.com',
        'parsed': parsed,
        'inserted': inserted,
        'run_date': date.today().isoformat(),
        'status': 'ok',
    }
    print(json.dumps(result))
    log.info(f'VERIFIED: dixie parsed={parsed} inserted={inserted}')


if __name__ == '__main__':
    main()
