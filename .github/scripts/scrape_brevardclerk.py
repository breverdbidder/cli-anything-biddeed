#!/usr/bin/env python3
"""Brevard Clerk Tax Deed Scraper v3 - calendar + surplus + lands_available."""
import os, re, sys, json
from datetime import datetime, date
import requests
from bs4 import BeautifulSoup
import fitz

SUPABASE_URL = os.environ['SUPABASE_URL'].rstrip('/')
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
AUCTION_DATE_STR = os.environ.get('AUCTION_DATE', '2026-05-14')
VERBOSE = os.environ.get('VERBOSE', 'true').lower() == 'true'
AUCTION_DATE = date.fromisoformat(AUCTION_DATE_STR)

# Known PDF endpoints
SURPLUS_URL = 'https://www.brevardclerk.us/?a=Files.Serve&File_id=847BFD73-D42A-4027-9079-E8E37E82E52B'
LANDS_URL   = 'https://www.brevardclerk.us/?a=Files.Serve&File_id=7B8E6515-1AF7-4968-977F-CC32647E2257'

HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; BidDeedBot/1.0)'}
REST = f'{SUPABASE_URL}/rest/v1'
RPC_HEADERS = {
    'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json', 'Prefer': 'return=representation',
}

def rpc(name, params):
    r = requests.post(f'{REST}/rpc/{name}', json=params, headers=RPC_HEADERS, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f'RPC {name} [{r.status_code}]: {r.text[:400]}')
    if not r.text or not r.text.strip():
        return None
    try: return r.json()
    except Exception: return r.text

def select(table, query=''):
    r = requests.get(f'{REST}/{table}?{query}',
        headers={'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}'}, timeout=30)
    r.raise_for_status()
    return r.json()

def fetch_pdf_text(url, label):
    print(f'[{label}] Fetching: {url[:80]}...')
    r = requests.get(url, headers=HEADERS, timeout=120)
    r.raise_for_status()
    pdf_bytes = r.content
    print(f'[{label}] {len(pdf_bytes):,} bytes downloaded')
    doc = fitz.open(stream=pdf_bytes, filetype='pdf')
    text = ''.join(page.get_text() + '\n' for page in doc)
    pages = len(doc)
    doc.close()
    print(f'[{label}] Parsed {pages} pages, {len(text):,} chars')
    return text, pages, len(pdf_bytes)

# Start scrape run
run_id = rpc('scrape_log_start', {
    'p_source': 'brevardclerk_full',
    'p_county': 'brevard',
    'p_sale_type': 'tax_deed',
    'p_auction_date': AUCTION_DATE_STR,
    'p_triggered_by': 'gha_workflow_dispatch',
})
print(f'>>> Run id={run_id}')

try:
    summary = {'stages': {}}

    # ========================================================================
    # STAGE 1: Auction Calendar PDF (existing logic - confirms what's scheduled)
    # ========================================================================
    print('\n=== STAGE 1: Auction Calendar ===')
    r = requests.get('https://www.brevardclerk.us/tax-deed-sales', headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, 'html.parser')
    short = f'{AUCTION_DATE.month}/{AUCTION_DATE.day}/{AUCTION_DATE.strftime("%y")}'
    sale_link = None
    for td in soup.select('td.recordListDate'):
        if td.get_text(strip=True) == short:
            next_td = td.find_next('td')
            if next_td:
                a = next_td.find('a', class_='ContentGrid')
                if a and a.get('href'):
                    sale_link = a['href']; break
    calendar_summary = {'sale_link': sale_link, 'date': AUCTION_DATE_STR}

    if sale_link:
        ssoup = BeautifulSoup(
            requests.get(f'https://www.brevardclerk.us{sale_link}', headers=HEADERS, timeout=30).text,
            'html.parser'
        )
        for a in ssoup.find_all('a', href=True):
            if 'Files.Serve' in a['href'] and not a.find('img'):
                pdf_url = f'https://www.brevardclerk.us{a["href"]}' if a['href'].startswith('/') else a['href']
                cal_text, cal_pages, cal_bytes = fetch_pdf_text(pdf_url, 'calendar')
                cal_parcels = list(set(re.findall(r'\b(\d{7,8})\b', cal_text)))
                calendar_summary['parcels_in_pdf'] = len(cal_parcels)
                calendar_summary['pdf_bytes'] = cal_bytes
                calendar_summary['pdf_pages'] = cal_pages
                break

    summary['stages']['calendar'] = calendar_summary

    # ========================================================================
    # STAGE 2: Surplus PDF - extract surplus filings (SOLD prices live here)
    # ========================================================================
    print('\n=== STAGE 2: Tax Deed Surplus PDF ===')
    surplus_text, sp_pages, sp_bytes = fetch_pdf_text(SURPLUS_URL, 'surplus')

    if VERBOSE:
        print('SAMPLE SURPLUS TEXT (first 3000 chars):')
        print(surplus_text[:3000])
        print('-' * 70)

    # Pull our 10 SOLD parcels (and all 129 for full match)
    snap = select('v_brevard_snapshot_minimal', 'select=parcel_id,case_number,opening_bid,sale_status_canonical')
    snap_by_parcel = {row['parcel_id']: row for row in snap if row.get('parcel_id')}
    sold_pids = {pid for pid, r in snap_by_parcel.items() if r.get('sale_status_canonical') == 'SOLD'}
    print(f'Snapshot parcels: {len(snap_by_parcel)}, SOLD today: {len(sold_pids)}')

    # Brevard surplus PDFs typically organize entries by case number 26-TD-NNNN or 2024-CA / 2025-TD
    # Each row contains: case#, parcel, sale date, sale price, surplus, former owner, address
    # Extract candidate surplus rows by chunking around case-number anchors
    case_anchor_re = re.compile(r'(\d{2,4}[-\s]?TD[-\s]?\d{3,6}|\d{4}[-\s]?CA[-\s]?\d{4,8})', re.IGNORECASE)
    parcel_re = re.compile(r'\b(\d{7,8})\b')
    money_re = re.compile(r'\$\s*([\d,]+\.\d{2})')
    date_re = re.compile(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})')

    # First, locate all our known parcels in the surplus text
    parcel_hits = {}
    for pid in snap_by_parcel.keys():
        idx = surplus_text.find(pid)
        if idx > 0:
            ctx = surplus_text[max(0, idx-500):idx+500]
            moneys = money_re.findall(ctx)
            cases = case_anchor_re.findall(ctx)
            dates = date_re.findall(ctx)
            parcel_hits[pid] = {
                'context': ctx[:800],
                'amounts': moneys,
                'cases': cases,
                'dates': dates,
                'is_sold_today': pid in sold_pids,
            }

    print(f'Parcels found in surplus PDF: {len(parcel_hits)}')
    print(f'  Of which SOLD today: {sum(1 for h in parcel_hits.values() if h["is_sold_today"])}')

    # Also do a global scan: extract every candidate surplus row
    # Group text into chunks per case anchor
    all_surplus_rows = []
    anchors = [(m.start(), m.group(1)) for m in case_anchor_re.finditer(surplus_text)]
    for i, (start, case) in enumerate(anchors):
        end = anchors[i+1][0] if i+1 < len(anchors) else min(start + 800, len(surplus_text))
        chunk = surplus_text[start:end]
        if len(chunk) < 30: continue
        parcels = list(set(parcel_re.findall(chunk)))
        moneys = money_re.findall(chunk)
        dates = date_re.findall(chunk)
        if parcels and moneys:
            all_surplus_rows.append({
                'case_number': case.upper().replace(' ',''),
                'parcels': parcels[:3],
                'amounts': moneys[:5],
                'dates': dates[:3],
                'chunk_size': len(chunk),
            })

    print(f'Total surplus-row candidates: {len(all_surplus_rows)}')

    # Store all payload data for inspection
    payload_rows = []
    for pid, hit in parcel_hits.items():
        payload_rows.append({'kind': 'surplus_match', 'parcel': pid, **hit})
    for row in all_surplus_rows[:200]:  # cap at 200 to keep payload size reasonable
        payload_rows.append({'kind': 'surplus_candidate', **row})

    rpc('scrape_payload_insert', {'p_run_id': run_id, 'p_rows': payload_rows})
    print(f'Stored {len(payload_rows)} payload rows')

    # ========================================================================
    # STAGE 3: Upsert clean surplus rows where confident
    # ========================================================================
    upserted = 0
    for row in all_surplus_rows:
        # Need at least: case, one parcel, two amounts (sold + surplus), one date
        if len(row['parcels']) < 1 or len(row['amounts']) < 2 or len(row['dates']) < 1:
            continue
        amounts = [float(a.replace(',','')) for a in row['amounts']]
        # Heuristic: largest amount = sold_amount, second-largest = surplus
        amounts_sorted = sorted(amounts, reverse=True)
        sold_amount = amounts_sorted[0]
        surplus_amount = None
        # Try to find which is which: surplus typically smaller than sold
        if len(amounts_sorted) >= 2 and amounts_sorted[1] < amounts_sorted[0]:
            surplus_amount = amounts_sorted[1]

        # Parse first date
        try:
            d = row['dates'][0]
            parts = re.split(r'[/-]', d)
            if len(parts) == 3:
                m, dd, y = parts
                if len(y) == 2: y = '20' + y
                sale_date = f'{y}-{int(m):02d}-{int(dd):02d}'
            else:
                sale_date = None
        except Exception:
            sale_date = None

        try:
            new_id = rpc('brevard_upsert_surplus', {'p': {
                'case_number': row['case_number'],
                'parcel_id': row['parcels'][0],
                'sale_date': sale_date,
                'sold_amount': sold_amount,
                'surplus_amount': surplus_amount,
                'source_pdf_url': SURPLUS_URL,
                'scrape_run_id': str(run_id),
                'raw_context': f'parcels={row["parcels"]} amounts={amounts} dates={row["dates"]}',
            }})
            upserted += 1
        except Exception as e:
            if upserted < 3: print(f'  ! upsert fail: {e}')

    print(f'Upserted {upserted} surplus rows into pipeline.tax_deed_surplus')

    # ========================================================================
    # STAGE 4: Apply sold_amount to today's SOLD deals where match found
    # ========================================================================
    sold_amount_applied = 0
    sold_amount_details = []
    for pid in sold_pids:
        hit = parcel_hits.get(pid)
        if not hit or not hit.get('amounts'):
            continue
        amounts = [float(a.replace(',','')) for a in hit['amounts']]
        # Look for sold amount = the amount that's both > opening_bid AND plausible
        opening = snap_by_parcel[pid].get('opening_bid')
        opening_f = float(opening) if opening else 0
        # Try largest amount > opening
        candidates = [a for a in amounts if a > opening_f]
        if candidates:
            sold = max(candidates)
            try:
                rpc('brevard_update_sold', {
                    'p_parcel_id': pid,
                    'p_auction_date': AUCTION_DATE_STR,
                    'p_sold_amount': sold,
                    'p_sold_to': None,
                    'p_source': 'brevardclerk_surplus_pdf',
                    'p_notes': f'Auto-matched from surplus PDF context. Opening={opening_f}, amounts={amounts[:5]}',
                })
                sold_amount_applied += 1
                sold_amount_details.append({'parcel': pid, 'opening': opening_f, 'sold': sold, 'all_amounts': amounts[:5]})
            except Exception as e:
                print(f'  ! sold update fail {pid}: {e}')

    print(f'Applied sold_amount to {sold_amount_applied}/{len(sold_pids)} SOLD parcels')

    # ========================================================================
    # STAGE 5: Lands Available PDF (struck-off tracking)
    # ========================================================================
    print('\n=== STAGE 5: Lands Available PDF ===')
    lands_text, l_pages, l_bytes = fetch_pdf_text(LANDS_URL, 'lands')
    lands_parcels = set(parcel_re.findall(lands_text))
    # Filter to parcels we know are on FL Brevard (7-8 digits)
    lands_summary = {
        'pdf_bytes': l_bytes,
        'pdf_pages': l_pages,
        'parcels_found': len(lands_parcels),
        'matches_our_snapshot': len([p for p in lands_parcels if p in snap_by_parcel]),
    }

    # If any of our today's SOLD parcels show up in Lands Available, that's a contradiction (they didn't sell)
    sold_in_lands = sold_pids.intersection(lands_parcels)
    if sold_in_lands:
        print(f'⚠ Parcels marked SOLD that appear in Lands Available: {sold_in_lands}')
        lands_summary['sold_in_lands_contradiction'] = list(sold_in_lands)

    summary['stages']['surplus'] = {
        'pdf_bytes': sp_bytes,
        'pdf_pages': sp_pages,
        'surplus_candidates_extracted': len(all_surplus_rows),
        'snapshot_parcels_found_in_pdf': len(parcel_hits),
        'sold_today_found_in_pdf': sum(1 for h in parcel_hits.values() if h['is_sold_today']),
        'surplus_rows_upserted': upserted,
        'sold_amounts_applied': sold_amount_applied,
        'sold_details': sold_amount_details[:10],
    }
    summary['stages']['lands_available'] = lands_summary

    rpc('scrape_log_finish', {
        'p_run_id': run_id, 'p_status': 'success',
        'p_rows_in': len(all_surplus_rows),
        'p_rows_inserted': upserted,
        'p_notes': json.dumps(summary)[:6000],
    })
    print('\n=== SUMMARY ===')
    print(json.dumps(summary, indent=2)[:3000])

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
