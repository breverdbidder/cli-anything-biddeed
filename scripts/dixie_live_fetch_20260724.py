#!/usr/bin/env python3
"""
dixie live fetch 2026-07-24 — check for newly resolved outcomes.

Case 15-2023-CA-57 had sale date 2026-07-21. Today is 2026-07-24.
Check if it now shows as sold on dixieclerk.com/foreclosure-sales/.
Also re-check the 6 Aug-2025 tax deed rows.
"""
import re
import html
import json
import sys
import os
import logging
from datetime import date, datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
log = logging.getLogger('dixie-fetch-20260724')

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://mocerqjnksmhcjzxrewo.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('SUPABASE_KEY', '')
BASE = f'{SUPABASE_URL}/rest/v1'

DIXIE_TD_URL = 'https://dixieclerk.com/departments-services/court-services/tax-deed-sales/'
DIXIE_FC_URL = 'https://dixieclerk.com/departments-services/court-services/foreclosure-sales/'

WEB_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (BidDeed-SHARD4-Dixie-20260724/1.0; contact: ariel@everestcapitalusa.com)',
}

AUG2025_PARCELS = {
    '30-13-12-2994-0003-5550',
    '36-09-13-4502-0000-0330',
    '12-09-13-4030-0007-0050',
    '12-09-13-4030-0005-0170',
    '36-10-13-5665-0008-0330',
    '13-09-13-4051-0000-0490',
}


def main():
    try:
        import httpx
        from bs4 import BeautifulSoup
    except ImportError as e:
        print(f'ERROR: Missing package: {e}')
        sys.exit(1)

    client = httpx.Client(timeout=30)
    today = date.today()

    print(f'\n=== DIXIE LIVE FETCH — {today} ===\n')
    print(f'Supabase URL configured: {bool(SUPABASE_URL)}')
    print(f'Supabase Key configured: {bool(SUPABASE_KEY)}')

    # --- Tax Deed Records ---
    print(f'\n--- FETCHING TAX DEED PAGE ---')
    try:
        r = client.get(DIXIE_TD_URL, headers=WEB_HEADERS)
        print(f'Status: {r.status_code}')
        if r.status_code == 200:
            m = re.search(r':taxdeeds="(\[.*?\])"', r.text, re.S)
            if m:
                td_records = json.loads(html.unescape(m.group(1)))
                print(f'Found {len(td_records)} tax deed records')
                print('\nAll tax deed records:')
                for rec in td_records:
                    parcel = (rec.get('parcel') or '').strip()
                    status = (rec.get('status') or '').strip().lower()
                    sale_date_raw = rec.get('sale_date', '')
                    sold_amount = rec.get('sold_amount')
                    cert = rec.get('cert')
                    marker = '*** AUG2025 GAP ***' if parcel in AUG2025_PARCELS else ''
                    print(f'  {marker} parcel={parcel} date={sale_date_raw} status={status} sold_amount={sold_amount} cert={cert}')
            else:
                print('No :taxdeeds= JSON found in page')
                print('First 500 chars:')
                print(r.text[:500])
        else:
            print(f'Failed: {r.text[:200]}')
    except Exception as e:
        print(f'ERROR fetching tax deed page: {e}')

    # --- Foreclosure Records ---
    print(f'\n--- FETCHING FORECLOSURE PAGE ---')
    try:
        r2 = client.get(DIXIE_FC_URL, headers=WEB_HEADERS)
        print(f'Status: {r2.status_code}')
        if r2.status_code == 200:
            soup = BeautifulSoup(r2.text, 'html.parser')
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

                rec = {
                    'case_number': case_number,
                    'sale_date': field_map.get('Sale Date', '').strip(),
                    'parcel_id': field_map.get('Parcel ID', '').strip(),
                    'status': field_map.get('Status', '').strip().lower(),
                    'parties': field_map.get('Parties', '').strip(),
                    'judgment_amount': field_map.get('Judgement Amount', '').strip(),
                }
                records.append(rec)

            print(f'Found {len(records)} foreclosure records')
            for rec in records:
                marker = '*** TRACKED ***' if rec['case_number'] in ('15-2023-CA-57', '15-2025-CA-46') else ''
                print(f'  {marker} case={rec["case_number"]} date={rec["sale_date"]} status={rec["status"]} parcel={rec["parcel_id"]}')

            if not records:
                print('No foreclosure records found with the div parser.')
                print('Page text sample:')
                print(soup.get_text()[:1000])
        else:
            print(f'Failed: {r2.text[:200]}')
    except Exception as e:
        print(f'ERROR fetching foreclosure page: {e}')

    # --- Current DB state ---
    if SUPABASE_KEY:
        print(f'\n--- CURRENT DB STATE FOR DIXIE ---')
        try:
            import httpx
            api_headers = {
                'apikey': SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}',
            }
            resp = client.post(
                f'{BASE}/rpc/pencil_dod_evaluate_county',
                headers=api_headers,
                json={'p_county': 'dixie'},
            )
            print(f'pencil_dod_evaluate_county status: {resp.status_code}')
            if resp.status_code == 200:
                print(f'RESULT: {json.dumps(resp.json(), indent=2)}')
            else:
                print(f'Error: {resp.text[:500]}')
        except Exception as e:
            print(f'ERROR querying Supabase: {e}')
    else:
        print('\nNO SUPABASE KEY — skipping DB query')


if __name__ == '__main__':
    main()
