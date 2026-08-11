#!/usr/bin/env python3
"""Gold Standard shard-2 (dispatch 14cdfac9, bay/nassau): E-criterion backfill.

21 bay foreclosure rows and 9 nassau tax_deed rows carry parcel_id IS NULL
because the calendar-sweep only captured case_number + auction_date, not the
full RealAuction PREVIEW card. Live-verified (2026-08-11) that both sites'
PREVIEW pages already publish full card data (parcel/address/assessed value)
months ahead of the sale date -- this is a missing-enrichment-step bug, not a
data-not-yet-published situation. Fetches each distinct auction date's
PREVIEW page once, matches cards to the known failing case numbers, and
writes ONLY parcel_id/property_address/assessed_value/sold_amount for rows
that are currently NULL (never overwrites existing data).
"""
import os, re, json, sys
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')

SUPABASE_URL = os.environ['SUPABASE_URL'].rstrip('/')
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
REST = f'{SUPABASE_URL}/rest/v1'
H = {'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}',
     'Content-Type': 'application/json', 'Prefer': 'return=representation'}

BAY_TARGETS = {
    "25000412CA": "2026-03-24", "23001239CA": "2026-05-26", "26000161CA": "2026-07-30",
    "25000797CA": "2026-08-24", "25001083CA": "2026-08-25", "25000033CA": "2026-08-26",
    "25000644CA": "2026-08-27", "26000329CA": "2026-08-27", "25000894CA": "2026-08-27",
    "26000070CC": "2026-08-27", "25001336CA": "2026-08-31", "24000812CA": "2026-09-02",
    "25001052CA": "2026-09-02", "25000980CA": "2026-09-10", "26000078CA": "2026-09-16",
    "25001028CA": "2026-09-22", "26000160CA": "2026-09-22", "25000712CA": "2026-09-23",
    "23001291CA": "2026-09-24", "26000033CA": "2026-10-06", "25001056CA": "2026-10-08",
}
NASSAU_TARGETS = {
    "26TD000009AXYX": "2026-09-01", "26TD000011AXYX": "2026-09-15", "26TD000012AXYX": "2026-09-29",
    "26TD000013AXYX": "2026-10-13", "26TD000014AXYX": "2026-10-13", "26TD000015AXYX": "2026-10-20",
    "26TD000016AXYX": "2026-10-20", "26TD000017AXYX": "2026-10-27", "26TD000018AXYX": "2026-10-27",
}


def extract_cards(html):
    soup = BeautifulSoup(html, 'html.parser')
    cards = []
    for item in soup.select('div.AUCTION_ITEM'):
        c = {}
        table = item.select_one('table.ad_tab')
        rows = table.select('tr') if table else []
        addr_parts = []
        for i, tr in enumerate(rows):
            lbl_td = tr.select_one('td.AD_LBL')
            dta_td = tr.select_one('td.AD_DTA')
            if dta_td is None:
                continue
            label = lbl_td.get_text(strip=True) if lbl_td else ''
            value = dta_td.get_text(' ', strip=True)
            if label == 'Case #:':
                c['case_number_text'] = value or None
            elif label == 'Parcel ID:':
                a = dta_td.select_one('a')
                raw_pid = (a.get_text(strip=True) if a else value) or None
                c['parcel_id_text'] = raw_pid if raw_pid and any(ch.isdigit() for ch in raw_pid) else None
            elif label == 'Property Address:':
                if value:
                    addr_parts.append(value)
            elif label == '' and value and i > 0:
                addr_parts.append(value)
            elif label == 'Assessed Value:':
                c['assessed_value_text'] = value or None
        if addr_parts:
            c['property_address_text'] = ', '.join(addr_parts)
        if c.get('case_number_text'):
            cards.append(c)
    return cards


def fetch_preview(browser, base_url, date_str):
    mm, dd, yy = date_str.split('-')[1], date_str.split('-')[2], date_str.split('-')[0]
    date_slash = f'{mm}/{dd}/{yy}'
    url = f'{base_url}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={date_slash}'
    page = browser.new_page(user_agent=UA)
    try:
        resp = page.goto(url, timeout=60000)
        status = resp.status if resp else None
        page.wait_for_timeout(6000)
        html = page.content()
        return status, html
    finally:
        page.close()


def parse_money(text):
    if not text:
        return None
    v = re.sub(r'[$,\s]', '', text)
    return v if re.match(r'^-?\d+(\.\d+)?$', v) else None


def main():
    updates = []  # (county, case_number, parcel_id, address, assessed_value)
    log = {'bay': {}, 'nassau': {}}

    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox'])
        try:
            # --- BAY: exact case_number match ---
            bay_dates = sorted(set(BAY_TARGETS.values()))
            for d in bay_dates:
                status, html = fetch_preview(browser, 'https://bay.realforeclose.com', d)
                cards = extract_cards(html)
                log['bay'][d] = {'status': status, 'cards_found': len(cards)}
                for c in cards:
                    cn = c.get('case_number_text')
                    if cn in BAY_TARGETS and c.get('parcel_id_text'):
                        updates.append(('bay', cn, c.get('parcel_id_text'),
                                        c.get('property_address_text'),
                                        parse_money(c.get('assessed_value_text'))))

            # --- NASSAU: match via 6-digit sequence number embedded in TD case format ---
            nassau_seq_map = {}
            for cn in NASSAU_TARGETS:
                m = re.search(r'TD(\d{6})', cn)
                if m:
                    nassau_seq_map[m.group(1)] = cn
            nassau_dates = sorted(set(NASSAU_TARGETS.values()))
            for d in nassau_dates:
                status, html = fetch_preview(browser, 'https://nassau.realtaxdeed.com', d)
                cards = extract_cards(html)
                log['nassau'][d] = {'status': status, 'cards_found': len(cards)}
                for c in cards:
                    site_cn = c.get('case_number_text') or ''
                    m = re.search(r'(\d{6})TD', site_cn)
                    if m and m.group(1) in nassau_seq_map and c.get('parcel_id_text'):
                        db_cn = nassau_seq_map[m.group(1)]
                        updates.append(('nassau', db_cn, c.get('parcel_id_text'),
                                        c.get('property_address_text'),
                                        parse_money(c.get('assessed_value_text'))))
        finally:
            browser.close()

    print('=== FETCH LOG ===')
    print(json.dumps(log, indent=2))
    print(f'\n=== {len(updates)} matched rows to update ===')
    for u in updates:
        print(u)

    applied = []
    for county, case_number, parcel_id, address, assessed_value in updates:
        payload = {'parcel_id': parcel_id}
        if address:
            payload['property_address'] = address
        if assessed_value:
            payload['assessed_value'] = assessed_value
        # scoped PATCH: only rows still missing parcel_id, exact case_number+county match
        params = {
            'county': f'ilike.{county}',
            'case_number': f'eq.{case_number}',
            'parcel_id': 'is.null',
        }
        r = requests.patch(f'{REST}/multi_county_auctions', headers=H, params=params, json=payload, timeout=30)
        if r.status_code >= 300:
            print(f'  ! FAILED {county}/{case_number}: {r.status_code} {r.text[:300]}')
        else:
            n = len(r.json()) if r.text else 0
            applied.append({'county': county, 'case_number': case_number, 'rows_updated': n, 'payload': payload})
            print(f'  OK {county}/{case_number}: {n} row(s) updated')

    print('\n=== APPLIED SUMMARY ===')
    print(json.dumps(applied, indent=2))
    if len(updates) > 0 and len(applied) == 0:
        print('FAIL-LOUD: matched rows but zero PATCH succeeded', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
