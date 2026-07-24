#!/usr/bin/env python3
"""
dixie C/D Live Check — SHARD-4 2026-07-24
Checks dixieclerk.com for newly-resolved outcomes on the 8 still-unmatched rows.
Known unmatched:
  - 6 Aug-2025 tax deed parcels (still 'scheduled' on clerk site)
  - 15-2023-CA-57 (foreclosure, sale date 2026-07-21 — now 3 days past)
  - 15-2025-CA-46 (foreclosure, genuinely future or recent)
"""
import re
import html
import json
import sys
import logging
from datetime import date, datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
log = logging.getLogger('dixie-live-check')

DIXIE_TD_URL = 'https://dixieclerk.com/departments-services/court-services/tax-deed-sales/'
DIXIE_FC_URL = 'https://dixieclerk.com/departments-services/court-services/foreclosure-sales/'

WEB_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (BidDeed-SHARD4-Dixie-CDCheck/1.0; contact: ariel@everestcapitalusa.com)',
}

AUG2025_PARCELS = {
    '30-13-12-2994-0003-5550',
    '36-09-13-4502-0000-0330',
    '12-09-13-4030-0007-0050',
    '12-09-13-4030-0005-0170',
    '36-10-13-5665-0008-0330',
    '13-09-13-4051-0000-0490',
}

def fetch_tax_deed_records(client):
    log.info(f'Fetching tax deed page: {DIXIE_TD_URL}')
    r = client.get(DIXIE_TD_URL, headers=WEB_HEADERS)
    log.info(f'Tax deed page status: {r.status_code}')
    if r.status_code != 200:
        log.error(f'Failed to fetch tax deed page: {r.status_code}')
        return []

    m = re.search(r':taxdeeds="(\[.*?\])"', r.text, re.S)
    if not m:
        log.warning('No :taxdeeds= JSON found in page')
        return []

    try:
        raw = json.loads(html.unescape(m.group(1)))
        log.info(f'Parsed {len(raw)} tax deed records from clerk')
        return raw
    except json.JSONDecodeError as e:
        log.error(f'JSON parse error: {e}')
        return []


def fetch_foreclosure_records(client):
    from bs4 import BeautifulSoup
    log.info(f'Fetching foreclosure page: {DIXIE_FC_URL}')
    r = client.get(DIXIE_FC_URL, headers=WEB_HEADERS)
    log.info(f'Foreclosure page status: {r.status_code}')
    if r.status_code != 200:
        log.error(f'Failed to fetch foreclosure page: {r.status_code}')
        return []

    soup = BeautifulSoup(r.text, 'html.parser')
    records = []
    seen_cases = set()

    SALE_FIELDS = {'Sale Date', 'Case Number', 'Parcel ID', 'Judgement Amount', 'Parties', 'Status'}
    for section in soup.find_all('div'):
        text = section.get_text(separator='|', strip=True)
        if 'Sale Date' not in text or 'Case Number' not in text:
            continue
        child_divs = section.find_all('div')
        if any('Case Number' in c.get_text() and 'Sale Date' in c.get_text() for c in child_divs):
            continue

        parts = [p.strip() for p in text.split('|') if p.strip()]
        field_map = {}
        for i, part in enumerate(parts):
            if part in SALE_FIELDS and i + 1 < len(parts):
                field_map[part] = parts[i + 1]

        case_number = field_map.get('Case Number', '').strip()
        if not case_number or case_number in seen_cases:
            continue
        seen_cases.add(case_number)
        records.append({
            'case_number': case_number,
            'sale_date': field_map.get('Sale Date', '').strip(),
            'parcel_id': field_map.get('Parcel ID', '').strip(),
            'status': field_map.get('Status', '').strip().lower(),
            'parties': field_map.get('Parties', '').strip(),
        })

    log.info(f'Parsed {len(records)} foreclosure records from clerk')
    return records


def main():
    import httpx
    client = httpx.Client(timeout=30)
    today = date.today()

    print(f'\n=== DIXIE C/D LIVE CHECK — {today} ===\n')

    # --- Tax Deed Records ---
    td_records = fetch_tax_deed_records(client)
    print(f'\n--- TAX DEED RECORDS ({len(td_records)} total) ---')
    print(f'Checking the 6 Aug-2025 gap parcels...')

    newly_resolved = []
    for rec in td_records:
        parcel = (rec.get('parcel') or '').strip()
        status = (rec.get('status') or '').strip().lower()
        sale_date_raw = rec.get('sale_date', '')
        sold_amount = rec.get('sold_amount')
        cert = rec.get('cert')

        if parcel in AUG2025_PARCELS:
            print(f'\n  PARCEL: {parcel}')
            print(f'  sale_date: {sale_date_raw}')
            print(f'  status: {status}')
            print(f'  sold_amount: {sold_amount}')
            print(f'  cert: {cert}')

            if status in ('sold', 'redeemed') and sold_amount is not None:
                newly_resolved.append({
                    'parcel': parcel,
                    'case_number': f'DIXIE-SYNTH-{parcel}',
                    'status': status,
                    'sale_date_raw': sale_date_raw,
                    'sold_amount': sold_amount,
                    'cert': cert,
                })
                print(f'  *** NEWLY RESOLVED: {status} at ${sold_amount} ***')
            else:
                print(f'  Still unresolved (status={status})')

    # Also show ALL records to look for any new ones
    print(f'\n--- ALL TAX DEED RECORDS ---')
    for rec in td_records:
        parcel = (rec.get('parcel') or '').strip()
        status = (rec.get('status') or '').strip().lower()
        sale_date_raw = rec.get('sale_date', '')
        sold_amount = rec.get('sold_amount')
        print(f'  parcel={parcel} date={sale_date_raw} status={status} sold={sold_amount}')

    # --- Foreclosure Records ---
    fc_records = fetch_foreclosure_records(client)
    print(f'\n--- FORECLOSURE RECORDS ({len(fc_records)} total) ---')
    for rec in fc_records:
        cn = rec['case_number']
        print(f'  case={cn} date={rec["sale_date"]} status={rec["status"]} parcel={rec.get("parcel_id")}')
        if cn in ('15-2023-CA-57', '15-2025-CA-46'):
            print(f'  *** TRACKED CASE: {cn} | status={rec["status"]} ***')

    if newly_resolved:
        print(f'\n=== NEWLY RESOLVED ({len(newly_resolved)}) ===')
        for r in newly_resolved:
            print(f'  {r}')
    else:
        print(f'\n=== NO NEW RESOLUTIONS FOUND ===')

    return newly_resolved, fc_records


if __name__ == '__main__':
    main()
