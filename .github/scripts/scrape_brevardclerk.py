#!/usr/bin/env python3
"""
Brevard Clerk Tax Deed Sales Scraper.

Fetches the auction PDF from brevardclerk.us, parses it, and updates statuses
in Supabase via public-schema wrapper RPCs.

ARCHITECTURE:
  brevardclerk.us /tax-deed-sales (calendar)
    -> /tax-deed-sales?ID=<guid> (sale-specific page)
    -> /?a=Files.Serve&File_id=<guid> (PDF with auction list)
  -> Parse PDF text via PyMuPDF
  -> RPCs:
       public.scrape_log_start / scrape_log_finish
       public.brevard_update_status
       public.brevard_update_sold
"""
import os, re, sys, json
from datetime import datetime, date
import requests
from bs4 import BeautifulSoup
import fitz  # pymupdf

# ============================================================================
# Config
# ============================================================================
SUPABASE_URL = os.environ['SUPABASE_URL'].rstrip('/')
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
AUCTION_DATE_STR = os.environ.get('AUCTION_DATE', '2026-05-14')
VERBOSE = os.environ.get('VERBOSE', 'true').lower() == 'true'
AUCTION_DATE = date.fromisoformat(AUCTION_DATE_STR)
UA = 'Mozilla/5.0 (compatible; BidDeedBot/1.0; +https://biddeed.ai)'
HEADERS = {'User-Agent': UA}
REST = f'{SUPABASE_URL}/rest/v1'
RPC_HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=representation',
}

def rpc(name, params):
    """Call a PostgREST RPC."""
    r = requests.post(f'{REST}/rpc/{name}', json=params, headers=RPC_HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()

def select(table, query=''):
    """Lightweight select."""
    url = f'{REST}/{table}?{query}'
    r = requests.get(url, headers={'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}'}, timeout=30)
    r.raise_for_status()
    return r.json()

# ============================================================================
# Start scrape run
# ============================================================================
run_id = rpc('scrape_log_start', {
    'p_source': 'brevardclerk_results',
    'p_county': 'brevard',
    'p_sale_type': 'tax_deed',
    'p_auction_date': AUCTION_DATE_STR,
    'p_triggered_by': 'gha_workflow_dispatch',
})
print(f'>>> Scrape run id={run_id}, auction_date={AUCTION_DATE_STR}')

try:
    # ========================================================================
    # Step 1: Find today's sale link on the calendar page
    # ========================================================================
    print('Fetching calendar...')
    r = requests.get('https://www.brevardclerk.us/tax-deed-sales', headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, 'html.parser')

    short = f'{AUCTION_DATE.month}/{AUCTION_DATE.day}/{AUCTION_DATE.strftime("%y")}'
    print(f'Looking for date: {short}')
    sale_link = None
    for td in soup.select('td.recordListDate'):
        if td.get_text(strip=True) == short:
            next_td = td.find_next('td')
            if next_td:
                a = next_td.find('a', class_='ContentGrid')
                if a and a.get('href'):
                    sale_link = a['href']
                    break
    if not sale_link:
        raise RuntimeError(f'No sale found for date {short}')
    print(f'Found sale page: {sale_link}')

    # ========================================================================
    # Step 2: Fetch sale page, find PDF link
    # ========================================================================
    sale_url = f'https://www.brevardclerk.us{sale_link}'
    r = requests.get(sale_url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    ssoup = BeautifulSoup(r.text, 'html.parser')

    pdf_links = []
    for a in ssoup.find_all('a', href=True):
        if 'Files.Serve' in a['href']:
            # Filter out icon-only links (those have an img child)
            if a.find('img'):
                continue
            pdf_links.append(a['href'])
    if not pdf_links:
        # fallback: any Files.Serve link
        for a in ssoup.find_all('a', href=True):
            if 'Files.Serve' in a['href']:
                pdf_links.append(a['href'])
                break
    if not pdf_links:
        raise RuntimeError('No PDF link on sale page')
    pdf_link = pdf_links[0]
    pdf_url = f'https://www.brevardclerk.us{pdf_link}' if pdf_link.startswith('/') else pdf_link
    print(f'PDF URL: {pdf_url}')

    # ========================================================================
    # Step 3: Download + parse PDF
    # ========================================================================
    pdf_resp = requests.get(pdf_url, headers=HEADERS, timeout=60)
    pdf_resp.raise_for_status()
    pdf_bytes = pdf_resp.content
    print(f'PDF: {len(pdf_bytes)} bytes')

    doc = fitz.open(stream=pdf_bytes, filetype='pdf')
    num_pages = len(doc)
    full_text = ''
    for page in doc:
        full_text += page.get_text() + '\n'
    doc.close()
    print(f'PDF text: {len(full_text)} chars, {num_pages} pages')

    if VERBOSE:
        print('=' * 70)
        print('PDF TEXT (first 4000 chars):')
        print(full_text[:4000])
        print('=' * 70)

    # ========================================================================
    # Step 4: Extract auction rows from PDF
    # Brevard tax-deed format varies but typically: tax-deed case number,
    # parcel/account, opening bid (dollar amount), optional status keyword
    # ========================================================================
    parcel_re = re.compile(r'\b(\d{7,8})\b')
    money_re = re.compile(r'\$\s*([\d,]+\.\d{2})')
    case_re = re.compile(r'(\d{4}-?TD-?\d+|TD-?\d{4}-?\d+|\d{2}\d{4}\d+)', re.IGNORECASE)
    status_re = re.compile(r'\b(SOLD|REDEEMED|CANCELLED|CANCELED|STRUCK\s*OFF|WITHDRAWN|PENDING|UPCOMING)\b', re.IGNORECASE)

    rows = []
    # Strategy: walk lines; whenever we see a parcel, start a new "row" with
    # surrounding context (prev + next 2 lines) for money/status detection.
    lines = [ln.strip() for ln in full_text.split('\n')]
    for i, ln in enumerate(lines):
        if not ln:
            continue
        pm = parcel_re.search(ln)
        if not pm:
            continue
        # Context = this line + next 2 + prev 1
        ctx = ' | '.join(filter(None, [lines[max(0,i-1)], ln, lines[min(len(lines)-1,i+1)], lines[min(len(lines)-1,i+2)]]))
        parcel = pm.group(1)
        if len(parcel) < 7:
            continue
        money_match = money_re.search(ctx)
        case_match = case_re.search(ctx)
        status_match = status_re.search(ctx)
        rows.append({
            'parcel': parcel,
            'opening_bid': float(money_match.group(1).replace(',', '')) if money_match else None,
            'case': case_match.group(1) if case_match else None,
            'pdf_status': status_match.group(1).upper() if status_match else None,
            'ctx': ctx[:300],
        })

    # Dedupe by parcel (keep first)
    seen = set()
    unique_rows = []
    for r in rows:
        if r['parcel'] in seen:
            continue
        seen.add(r['parcel'])
        unique_rows.append(r)
    rows = unique_rows
    print(f'Extracted {len(rows)} unique parcels from PDF')

    if VERBOSE and rows:
        print('First 3 rows:')
        for r in rows[:3]:
            print(f'  {r}')

    # ========================================================================
    # Step 5: Cross-reference with snapshot
    # ========================================================================
    snap = select('v_brevard_snapshot_minimal', 'select=parcel_id,case_number,opening_bid,sale_status_canonical,sold_amount&limit=500')
    snap_by_parcel = {row['parcel_id']: row for row in snap if row.get('parcel_id')}
    print(f'Snapshot has {len(snap_by_parcel)} parcels')

    matched = 0
    new_to_us = 0
    status_changes = []
    for r in rows:
        if r['parcel'] in snap_by_parcel:
            matched += 1
            current_status = snap_by_parcel[r['parcel']].get('sale_status_canonical')
            pdf_status_map = {
                'SOLD': 'SOLD', 'REDEEMED': 'REDEEMED',
                'CANCELLED': 'CANCELED', 'CANCELED': 'CANCELED',
                'STRUCK OFF': 'STRUCK_OFF', 'STRUCKOFF': 'STRUCK_OFF',
                'WITHDRAWN': 'WITHDRAWN', 'PENDING': 'LISTED', 'UPCOMING': 'LISTED',
            }
            pdf_canonical = pdf_status_map.get(r['pdf_status'])
            if pdf_canonical and pdf_canonical != current_status:
                status_changes.append({'parcel': r['parcel'], 'from': current_status, 'to': pdf_canonical, 'raw': r['pdf_status']})
        else:
            new_to_us += 1

    print(f'Cross-ref: {matched}/{len(rows)} matched our snapshot, {new_to_us} new-to-us')
    print(f'Status changes detected: {len(status_changes)}')

    # ========================================================================
    # Step 6: Apply status updates
    # ========================================================================
    applied = 0
    for change in status_changes:
        try:
            rpc('brevard_update_status', {
                'p_parcel_id': change['parcel'],
                'p_auction_date': AUCTION_DATE_STR,
                'p_new_status': change['to'],
                'p_source': 'brevardclerk_pdf',
                'p_raw_status': change['raw'],
                'p_notes': f'PDF scrape: {change["from"]} -> {change["to"]}',
            })
            applied += 1
        except Exception as e:
            print(f'  ! Update failed for {change["parcel"]}: {e}')

    # ========================================================================
    # Step 7: Finish run with summary
    # ========================================================================
    summary = {
        'pdf_url': pdf_url,
        'pdf_bytes': len(pdf_bytes),
        'pdf_pages': num_pages,
        'pdf_rows_extracted': len(rows),
        'matched_snapshot': matched,
        'new_to_us': new_to_us,
        'status_changes_detected': len(status_changes),
        'status_changes_applied': applied,
        'sample_changes': status_changes[:5],
        'note': 'Sold prices not in this PDF (auction-calendar PDF). For sold prices, run after sale day or use Official Records scraper.',
    }
    rpc('scrape_log_finish', {
        'p_run_id': run_id, 'p_status': 'success',
        'p_rows_in': len(rows), 'p_rows_inserted': applied, 'p_rows_deduped': 0,
        'p_notes': json.dumps(summary)[:4000],
    })
    print('=' * 70)
    print('SUMMARY:', json.dumps(summary, indent=2)[:2000])
    print('=' * 70)
    print(f'Run id={run_id} complete')

except Exception as e:
    import traceback
    err = f'{type(e).__name__}: {e}\n{traceback.format_exc()[:1500]}'
    print(f'ERROR: {err}', file=sys.stderr)
    try:
        rpc('scrape_log_finish', {
            'p_run_id': run_id, 'p_status': 'failed',
            'p_error': err[:2000],
        })
    except Exception:
        pass
    sys.exit(1)
