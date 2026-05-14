#!/usr/bin/env python3
"""Brevard Tax Deed Scraper v6 - Firecrawl-powered scrape of realforeclose DAYLIST."""
import os, re, sys, json
from datetime import date
import requests

SUPABASE_URL = os.environ['SUPABASE_URL'].rstrip('/')
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
FIRECRAWL_KEY = os.environ.get('FIRECRAWL_API_KEY','')
AUCTION_DATE_STR = os.environ.get('AUCTION_DATE','2026-05-14')
VERBOSE = os.environ.get('VERBOSE','true').lower() == 'true'
AUCTION_DATE = date.fromisoformat(AUCTION_DATE_STR)
DATE_SLASH = AUCTION_DATE.strftime('%m/%d/%Y')

DAYLIST_URL = f'https://brevard.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=DAYLIST&AUCTIONDATE={DATE_SLASH}'

REST = f'{SUPABASE_URL}/rest/v1'
RPC_HEADERS = {'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}',
               'Content-Type': 'application/json', 'Prefer': 'return=representation'}

def rpc(name, params):
    r = requests.post(f'{REST}/rpc/{name}', json=params, headers=RPC_HEADERS, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f'RPC {name} [{r.status_code}]: {r.text[:400]}')
    return r.json() if r.text and r.text.strip() else None

def select(table, query=''):
    r = requests.get(f'{REST}/{table}?{query}',
        headers={'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}'}, timeout=30)
    r.raise_for_status()
    return r.json()

# Start run
run_id = rpc('scrape_log_start', {
    'p_source': 'brevard_realforeclose', 'p_county': 'brevard',
    'p_sale_type': 'tax_deed', 'p_auction_date': AUCTION_DATE_STR,
    'p_triggered_by': 'gha_workflow_dispatch',
})
print(f'>>> Run id={run_id}')
print(f'>>> Target URL: {DAYLIST_URL}')

try:
    summary = {'url': DAYLIST_URL}

    # =========================================================
    # FIRECRAWL: scrape JS-rendered page
    # =========================================================
    if not FIRECRAWL_KEY:
        raise RuntimeError('FIRECRAWL_API_KEY missing from environment')

    print('\n>>> Calling Firecrawl with JS rendering + wait for content...')
    fc_resp = requests.post(
        'https://api.firecrawl.dev/v1/scrape',
        headers={'Authorization': f'Bearer {FIRECRAWL_KEY}', 'Content-Type': 'application/json'},
        json={
            'url': DAYLIST_URL,
            'formats': ['markdown', 'html'],
            'waitFor': 5000,  # wait 5s for JS to render auction grid
            'onlyMainContent': False,
        },
        timeout=120,
    )
    print(f'Firecrawl HTTP {fc_resp.status_code}')
    if fc_resp.status_code != 200:
        raise RuntimeError(f'Firecrawl failed: {fc_resp.text[:500]}')

    fc_data = fc_resp.json()
    if not fc_data.get('success'):
        raise RuntimeError(f'Firecrawl returned !success: {fc_data}')

    md = fc_data.get('data', {}).get('markdown', '')
    html = fc_data.get('data', {}).get('html', '')
    print(f'Firecrawl markdown: {len(md):,} chars')
    print(f'Firecrawl html: {len(html):,} chars')

    if VERBOSE and md:
        print('\n=== MARKDOWN SAMPLE (first 4000 chars) ===')
        print(md[:4000])
        print('=== END SAMPLE ===\n')

    summary['fc_md_chars'] = len(md)
    summary['fc_html_chars'] = len(html)

    # =========================================================
    # PARSE: extract auction rows from rendered content
    # =========================================================
    aid_re = re.compile(r'AID[=\s]*(\d{5,8})', re.IGNORECASE)
    parcel_re = re.compile(r'\b(\d{7,8})\b')
    money_re = re.compile(r'\$\s*([\d,]+\.\d{2})')
    case_re = re.compile(r'(\d{2,4}[-\s]?(?:TD|CA|FC)[-\s]?\d{3,6})', re.IGNORECASE)
    # status patterns from RealAuction
    status_re = re.compile(r'(SOLD|CANCELED|CANCELLED|REDEEMED|WITHDRAWN|STRUCK\s*OFF|READY|PENDING)', re.IGNORECASE)
    sold_phrase_re = re.compile(r'(?:sold\s*to|winning\s*bid|final\s*bid|sale\s*amount)[:\s]*\$?([\d,]+\.\d{2})', re.IGNORECASE)
    addr_re = re.compile(r'\b(\d+\s+[NSEW]?\s*[A-Z][A-Z\s]+(?:ST|AVE|RD|DR|BLVD|LN|CT|PL|WAY|TER|CIR|HWY|PKWY|TRL)\b)', re.IGNORECASE)

    # Pull our snapshot
    snap = select('v_brevard_snapshot_minimal',
        'select=parcel_id,case_number,opening_bid,sale_status_canonical')
    snap_by_parcel = {r['parcel_id']: r for r in snap if r.get('parcel_id')}
    sold_pids = {pid for pid, r in snap_by_parcel.items() if r.get('sale_status_canonical') == 'SOLD'}
    print(f'Snapshot: {len(snap_by_parcel)} parcels, {len(sold_pids)} marked SOLD today')

    # Use markdown if present, else HTML stripped
    text = md if md else re.sub(r'<[^>]+>', ' ', html)

    # Find all AIDs in the rendered content
    all_aids = list(set(aid_re.findall(text)))
    all_parcels = list(set(parcel_re.findall(text)))
    all_moneys = money_re.findall(text)
    all_statuses = list(set(s.upper() for s in status_re.findall(text)))
    all_sold_phrases = sold_phrase_re.findall(text)

    print(f'\nExtraction summary:')
    print(f'  AIDs found: {len(all_aids)} (sample: {all_aids[:5]})')
    print(f'  Parcels found: {len(all_parcels)} (sample: {all_parcels[:5]})')
    print(f'  Dollar amounts: {len(all_moneys)} (sample: {all_moneys[:5]})')
    print(f'  Statuses present: {all_statuses}')
    print(f'  "Sold to/winning bid" amounts: {all_sold_phrases[:10]}')

    # Match parcels to our snapshot
    snap_matches = [p for p in all_parcels if p in snap_by_parcel]
    sold_matches = [p for p in all_parcels if p in sold_pids]
    print(f'  Snapshot parcels found in page: {len(snap_matches)}')
    print(f'  Our SOLD parcels found in page: {len(sold_matches)}')

    summary.update({
        'aids_total': len(all_aids),
        'parcels_total': len(all_parcels),
        'moneys_total': len(all_moneys),
        'statuses_present': all_statuses,
        'snap_matches': len(snap_matches),
        'sold_matches': len(sold_matches),
    })

    # =========================================================
    # CHUNK-PARSE: split content per parcel/AID anchor
    # =========================================================
    # Strategy: find each parcel/AID and grab a window of context around it
    rows_extracted = []
    seen = set()
    # Iterate over all parcel occurrences in text order
    for m in parcel_re.finditer(text):
        pid = m.group(1)
        if pid in seen: continue
        seen.add(pid)
        start = max(0, m.start() - 600)
        end = min(len(text), m.end() + 600)
        ctx = text[start:end]
        ctx_moneys = money_re.findall(ctx)
        ctx_statuses = list(set(s.upper() for s in status_re.findall(ctx)))
        ctx_sold_phrases = sold_phrase_re.findall(ctx)
        ctx_aids = aid_re.findall(ctx)
        ctx_cases = case_re.findall(ctx)
        rows_extracted.append({
            'parcel': pid,
            'aid': ctx_aids[0] if ctx_aids else None,
            'case': ctx_cases[0] if ctx_cases else None,
            'amounts': ctx_moneys[:8],
            'statuses': ctx_statuses,
            'sold_phrase_amounts': ctx_sold_phrases,
            'in_our_snapshot': pid in snap_by_parcel,
            'in_our_sold': pid in sold_pids,
        })

    print(f'\n>>> Extracted {len(rows_extracted)} per-parcel rows from rendered content')

    # Store ALL extracted rows for inspection
    rpc('scrape_payload_insert', {'p_run_id': run_id, 'p_rows': rows_extracted})

    # =========================================================
    # APPLY: update sold_amount + status for matches
    # =========================================================
    sold_applied = 0
    status_applied = 0
    apply_details = []
    for row in rows_extracted:
        if not row['in_our_snapshot']: continue
        pid = row['parcel']

        # Try to detect sold price
        sold_amount = None
        # Preferred: a "sold to/winning bid: $X" phrase
        if row['sold_phrase_amounts']:
            try: sold_amount = float(row['sold_phrase_amounts'][0].replace(',', ''))
            except Exception: pass

        # Fallback: largest amount > opening bid
        if sold_amount is None and row['amounts']:
            opening = snap_by_parcel[pid].get('opening_bid')
            opening_f = float(opening) if opening else 0
            amts = [float(a.replace(',', '')) for a in row['amounts']]
            candidates = [a for a in amts if a > opening_f and a < 5_000_000]
            if candidates and 'SOLD' in row['statuses']:
                sold_amount = max(candidates)

        if sold_amount and 'SOLD' in row['statuses']:
            try:
                rpc('brevard_update_sold', {
                    'p_parcel_id': pid,
                    'p_auction_date': AUCTION_DATE_STR,
                    'p_sold_amount': sold_amount,
                    'p_sold_to': None,
                    'p_source': 'brevard_realforeclose_firecrawl',
                    'p_notes': f'Auto-matched from realforeclose DAYLIST. AID={row["aid"]} amounts={row["amounts"][:5]} statuses={row["statuses"]}',
                })
                sold_applied += 1
                apply_details.append({'parcel': pid, 'sold': sold_amount, 'aid': row['aid']})
            except Exception as e:
                print(f'  ! sold update fail {pid}: {e}')

        # Status update for canonical changes
        if row['statuses']:
            canonical = None
            if 'SOLD' in row['statuses']: canonical = 'SOLD'
            elif 'CANCELED' in row['statuses'] or 'CANCELLED' in row['statuses']: canonical = 'CANCELED'
            elif 'REDEEMED' in row['statuses']: canonical = 'REDEEMED'
            elif 'STRUCK OFF' in row['statuses'] or 'STRUCK_OFF' in row['statuses']: canonical = 'STRUCK_OFF'
            elif 'WITHDRAWN' in row['statuses']: canonical = 'WITHDRAWN'
            current = snap_by_parcel[pid].get('sale_status_canonical')
            if canonical and canonical != current:
                try:
                    rpc('brevard_update_status', {
                        'p_parcel_id': pid,
                        'p_auction_date': AUCTION_DATE_STR,
                        'p_new_status': canonical,
                        'p_source': 'brevard_realforeclose_firecrawl',
                        'p_raw_status': ','.join(row['statuses']),
                        'p_notes': f'Status change from realforeclose DAYLIST. Was {current} -> now {canonical}',
                    })
                    status_applied += 1
                except Exception as e:
                    print(f'  ! status update fail {pid}: {e}')

    summary['sold_applied'] = sold_applied
    summary['status_applied'] = status_applied
    summary['apply_details'] = apply_details[:20]

    print(f'\n=== APPLIED ===')
    print(f'  Sold amounts: {sold_applied}/{len(sold_pids)}')
    print(f'  Status changes: {status_applied}')

    rpc('scrape_log_finish', {
        'p_run_id': run_id, 'p_status': 'success',
        'p_rows_in': len(rows_extracted),
        'p_rows_inserted': sold_applied + status_applied,
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
