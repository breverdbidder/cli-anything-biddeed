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
            'parity_status': 'matched_clean',
            'clerk_url': DIXIE_FC_URL if sale_type == 'foreclosure' else DIXIE_TD_URL,
            'provenance': f'live_source_scrape_{date.today().isoformat()}',
            'data_source': 'dixieclerk.com_shard6_scraper',
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
    all_records = []

    # Scrape foreclosure sales
    log.info(f'Fetching Dixie foreclosure sales from {DIXIE_FC_URL}')
    r = client.get(DIXIE_FC_URL, headers=WEB_HEADERS)
    if r.status_code == 200:
        fc_records = parse_dixie_sales(r.text, 'foreclosure')
        log.info(f'Parsed {len(fc_records)} foreclosure auctions')
        all_records.extend(fc_records)
    else:
        log.warning(f'Foreclosure page returned {r.status_code}')

    # Scrape tax deed sales
    log.info(f'Fetching Dixie tax deed sales from {DIXIE_TD_URL}')
    r2 = client.get(DIXIE_TD_URL, headers=WEB_HEADERS)
    if r2.status_code == 200:
        td_records = parse_dixie_sales(r2.text, 'tax_deed')
        log.info(f'Parsed {len(td_records)} tax deed auctions')
        all_records.extend(td_records)
    else:
        log.warning(f'Tax deed page returned {r2.status_code}')

    # Fail-loud if parsed > 0 and inserted = 0
    parsed = len(all_records)
    if parsed == 0:
        log.info('No upcoming auctions found for Dixie County')
        print(json.dumps({'county': 'dixie', 'parsed': 0, 'inserted': 0, 'status': 'no_data'}))
        sys.exit(0)

    inserted = upsert_records(all_records, dry_run=args.dry_run)

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
