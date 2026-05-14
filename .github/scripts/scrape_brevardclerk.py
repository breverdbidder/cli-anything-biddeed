#!/usr/bin/env python3
"""Brevard Tier1 Scraper v8 - HTML table-row parsing. One <tr> = one auction. No bleed."""
import os, re, sys, json
from datetime import date
import requests
from bs4 import BeautifulSoup

SUPABASE_URL = os.environ['SUPABASE_URL'].rstrip('/')
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
FIRECRAWL_KEY = os.environ.get('FIRECRAWL_API_KEY','')
AUCTION_DATE_STR = os.environ.get('AUCTION_DATE','2026-05-14')
VERBOSE = os.environ.get('VERBOSE','true').lower() == 'true'
AUCTION_DATE = date.fromisoformat(AUCTION_DATE_STR)
DATE_SLASH = AUCTION_DATE.strftime('%m/%d/%Y')

PREVIEW_URL = f'https://brevard.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={DATE_SLASH}'

REST = f'{SUPABASE_URL}/rest/v1'
RPC_HEADERS = {'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}',
               'Content-Type': 'application/json', 'Prefer': 'return=representation'}

def rpc(name, params):
    r = requests.post(f'{REST}/rpc/{name}', json=params, headers=RPC_HEADERS, timeout=60)
    if r.status_code >= 400: raise RuntimeError(f'RPC {name} [{r.status_code}]: {r.text[:400]}')
    return r.json() if r.text and r.text.strip() else None

def select(table, query=''):
    r = requests.get(f'{REST}/{table}?{query}',
        headers={'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}'}, timeout=30)
    r.raise_for_status()
    return r.json()

run_id = rpc('scrape_log_start', {
    'p_source': 'brevard_realforeclose', 'p_county': 'brevard',
    'p_sale_type': 'tax_deed', 'p_auction_date': AUCTION_DATE_STR,
    'p_triggered_by': 'gha_workflow_dispatch_v8',
})
print(f'>>> Run id={run_id} v8 (HTML table-row parser)')
print(f'>>> URL: {PREVIEW_URL}')

try:
    summary = {'url': PREVIEW_URL, 'parser_version': 'v8_html_tr'}

    # Firecrawl with both formats
    print('Calling Firecrawl...')
    fc = requests.post('https://api.firecrawl.dev/v1/scrape',
        headers={'Authorization': f'Bearer {FIRECRAWL_KEY}', 'Content-Type': 'application/json'},
        json={'url': PREVIEW_URL, 'formats': ['html','markdown'], 'waitFor': 6000, 'onlyMainContent': False},
        timeout=120)
    if fc.status_code != 200: raise RuntimeError(f'Firecrawl [{fc.status_code}]: {fc.text[:500]}')
    fc_data = fc.json()
    html = fc_data.get('data',{}).get('html','')
    md = fc_data.get('data',{}).get('markdown','')
    print(f'Firecrawl: html={len(html):,} md={len(md):,}')
    summary['fc_html_chars'] = len(html); summary['fc_md_chars'] = len(md)

    # Pull snapshot to know what we're matching against
    snap = select('v_brevard_snapshot_minimal',
        'select=parcel_id,case_number,opening_bid,sale_status_canonical')
    snap_by_parcel = {r['parcel_id']: r for r in snap if r.get('parcel_id')}
    sold_pids_before = {pid for pid, r in snap_by_parcel.items() if r.get('sale_status_canonical') == 'SOLD'}
    print(f'Snapshot: {len(snap_by_parcel)} parcels, {len(sold_pids_before)} marked SOLD')

    # Parse HTML with BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')

    parcel_re = re.compile(r'\b(\d{7,8})\b')
    money_re = re.compile(r'\$\s*([\d,]+\.\d{2})')
    status_re = re.compile(r'\b(SOLD|CANCELED|CANCELLED|REDEEMED|WITHDRAWN|STRUCK\s*OFF|READY|PENDING|WAITING)\b', re.IGNORECASE)
    case_re = re.compile(r'(\d{2,4}[-\s]?(?:TD|CA|FC)[-\s]?\d{3,6})', re.IGNORECASE)

    # Find ALL <tr> rows - each is a closed unit
    all_trs = soup.find_all('tr')
    print(f'Found {len(all_trs)} <tr> elements')

    # ALSO find divs/cards that might contain auctions (RealAuction uses both)
    # The auction grid is rendered as repeating divs with class names containing 'AUCTION_DETAILS' or similar
    auction_divs = soup.find_all('div', class_=re.compile(r'(AUCTION_DETAILS|auctionItem|AuctionItem|saleItem)', re.IGNORECASE))
    print(f'Found {len(auction_divs)} auction divs')

    # Build candidate rows from BOTH sources
    rows_parsed = []
    seen_keys = set()

    def consider_element(el, kind):
        txt = el.get_text(' ', strip=True)
        if len(txt) < 10 or len(txt) > 3000: return  # filter noise
        parcels_in = list(set(parcel_re.findall(txt)))
        amounts_in = money_re.findall(txt)
        statuses_in = list(set(s.upper().replace('  ',' ') for s in status_re.findall(txt)))
        cases_in = case_re.findall(txt)
        # Only keep rows with at least one parcel AND some signal
        if not parcels_in: return
        if not (amounts_in or statuses_in): return
        # Filter: parcels must look like Brevard format (start with 1,2,3 typically — 8 digits)
        plausible_parcels = [p for p in parcels_in if len(p) >= 7]
        if not plausible_parcels: return
        # Dedup key
        key = (plausible_parcels[0], len(amounts_in), txt[:100])
        if key in seen_keys: return
        seen_keys.add(key)
        rows_parsed.append({
            'kind': kind,
            'parcels': plausible_parcels[:3],
            'amounts': amounts_in[:8],
            'statuses': statuses_in,
            'cases': [c.upper().replace(' ','') for c in cases_in[:2]],
            'text_sample': txt[:400],
        })

    for tr in all_trs: consider_element(tr, 'tr')
    for d in auction_divs: consider_element(d, 'div')

    print(f'\nParsed {len(rows_parsed)} candidate auction rows')
    if VERBOSE and rows_parsed[:3]:
        print('=== FIRST 3 SAMPLE ROWS ===')
        for r in rows_parsed[:3]:
            print(json.dumps(r, indent=2))
        print('=== END SAMPLES ===\n')

    # Match against our snapshot
    snap_matches = []
    for r in rows_parsed:
        for pid in r['parcels']:
            if pid in snap_by_parcel:
                snap_matches.append({'snap_parcel': pid, **r})
                break
    print(f'\nRows that contain a parcel from our snapshot: {len(snap_matches)}')

    # Apply: for each snapshot match with SOLD status, extract the sold price
    applied = []
    for m in snap_matches:
        pid = m['snap_parcel']
        if 'SOLD' not in m['statuses']: continue
        if not m['amounts']: continue
        amts = sorted([float(a.replace(',','')) for a in m['amounts'] if float(a.replace(',','')) < 10_000_000], reverse=True)
        if not amts: continue
        # Heuristic: largest amount in THE SAME ROW is the sold price
        # (since rows don't bleed, this is safe)
        sold_amt = amts[0]
        # But: opening bid should also be in this row. The 2nd largest is likely opening if amts span big range
        opening_guess = None
        if len(amts) >= 2:
            opening_guess = amts[-1] if amts[-1] < amts[0] / 2 else amts[1]
        applied.append({
            'parcel': pid,
            'sold_amount_v8': sold_amt,
            'opening_in_row': opening_guess,
            'all_amounts_in_row': amts,
            'cases': m['cases'],
            'row_kind': m['kind'],
            'row_sample': m['text_sample'][:200],
        })

    print(f'\n=== V8 PROPOSED SOLD PRICES ===')
    for a in applied:
        print(f"  {a['parcel']}: sold=${a['sold_amount_v8']:,.2f} opening_in_row=${a['opening_in_row']:,.2f}" if a['opening_in_row'] else f"  {a['parcel']}: sold=${a['sold_amount_v8']:,.2f}")
        print(f"      row amounts: {a['all_amounts_in_row']}")
        print(f"      case: {a['cases']} kind={a['row_kind']}")

    # Store ALL parsed rows for inspection
    rpc('scrape_payload_insert', {'p_run_id': run_id, 'p_rows': rows_parsed[:200]})

    # Apply to tier1_today (the SSOT) and snapshot
    sold_updated = 0
    for a in applied:
        try:
            # Update tier1_today
            rpc('tier1_upsert_rpc', {'p': {
                'county': 'brevard', 'parcel_id': a['parcel'],
                'auction_date': AUCTION_DATE_STR,
                'case_number': a['cases'][0] if a['cases'] else None,
                'sale_status': 'SOLD',
                'sold_amount': a['sold_amount_v8'],
                'opening_bid': a['opening_in_row'],
                'sold_to': None, 'aid': None,
                'source_platform': 'realforeclose', 'source_url': PREVIEW_URL,
                'run_id': str(run_id),
                'raw_context': a['row_sample'],
                'confidence': 'tier1_verified',
            }})
            # And legacy update_sold_amount for the snapshot
            rpc('brevard_update_sold', {
                'p_parcel_id': a['parcel'], 'p_auction_date': AUCTION_DATE_STR,
                'p_sold_amount': a['sold_amount_v8'], 'p_sold_to': None,
                'p_source': 'brevard_realforeclose_v8_tr_parser',
                'p_notes': f'v8 HTML-tr parser. row_amounts={a["all_amounts_in_row"]} row_kind={a["row_kind"]}',
            })
            sold_updated += 1
        except Exception as e:
            print(f'  ! apply fail {a["parcel"]}: {e}')

    summary.update({
        'tr_count': len(all_trs),
        'div_count': len(auction_divs),
        'rows_parsed': len(rows_parsed),
        'snap_matches': len(snap_matches),
        'sold_applied': sold_updated,
        'applied_details': applied,
    })
    print(f'\n=== APPLIED ===')
    print(f'  Sold prices updated: {sold_updated}')

    rpc('scrape_log_finish', {
        'p_run_id': run_id, 'p_status': 'success',
        'p_rows_in': len(rows_parsed), 'p_rows_inserted': sold_updated,
        'p_notes': json.dumps(summary)[:6000],
    })

except Exception as e:
    import traceback
    err = f'{type(e).__name__}: {e}\n{traceback.format_exc()[:1500]}'
    print(f'ERROR: {err}', file=sys.stderr)
    try:
        requests.post(f'{REST}/rpc/scrape_log_finish',
            json={'p_run_id': run_id, 'p_status': 'failed', 'p_error': err[:2000]},
            headers=RPC_HEADERS, timeout=15)
    except Exception: pass
    sys.exit(1)
