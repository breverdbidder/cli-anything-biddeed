#!/usr/bin/env python3
"""Generic FL county RealAuction scraper - parameterized by COUNTY_SLUG + DOMAIN."""
import os, re, sys, json
from datetime import date
import requests

SUPABASE_URL = os.environ['SUPABASE_URL'].rstrip('/')
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
FIRECRAWL_KEY = os.environ.get('FIRECRAWL_API_KEY','')
COUNTY_SLUG = os.environ['COUNTY_SLUG'].lower()
COUNTY_DOMAIN = os.environ['COUNTY_DOMAIN']
AUCTION_DATE_STR = os.environ['AUCTION_DATE']
AUCTION_DATE = date.fromisoformat(AUCTION_DATE_STR)
DATE_SLASH = AUCTION_DATE.strftime('%m/%d/%Y')

if 'realforeclose' in COUNTY_DOMAIN: PLATFORM = 'realforeclose'
elif 'realtaxdeed' in COUNTY_DOMAIN: PLATFORM = 'realtaxdeed'
else: PLATFORM = 'realauction'

PREVIEW_URL = f'https://{COUNTY_DOMAIN}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={DATE_SLASH}'
SOURCE_CODE = f'{COUNTY_SLUG}_{PLATFORM}'

REST = f'{SUPABASE_URL}/rest/v1'
RPC_HEADERS = {'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}',
               'Content-Type': 'application/json', 'Prefer': 'return=representation'}

def rpc(name, params):
    r = requests.post(f'{REST}/rpc/{name}', json=params, headers=RPC_HEADERS, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f'RPC {name} [{r.status_code}]: {r.text[:400]}')
    return r.json() if r.text and r.text.strip() else None

run_id = rpc('scrape_log_start', {
    'p_source': SOURCE_CODE, 'p_county': COUNTY_SLUG,
    'p_sale_type': 'tax_deed', 'p_auction_date': AUCTION_DATE_STR,
    'p_triggered_by': 'gha_multi_county_dispatch',
})
print(f'>>> Run id={run_id} county={COUNTY_SLUG} platform={PLATFORM}')
print(f'>>> URL: {PREVIEW_URL}')

try:
    summary = {'county': COUNTY_SLUG, 'platform': PLATFORM, 'url': PREVIEW_URL}
    fc = requests.post('https://api.firecrawl.dev/v1/scrape',
        headers={'Authorization': f'Bearer {FIRECRAWL_KEY}', 'Content-Type': 'application/json'},
        json={'url': PREVIEW_URL, 'formats': ['markdown','html'], 'waitFor': 5000, 'onlyMainContent': False},
        timeout=120)
    if fc.status_code != 200: raise RuntimeError(f'Firecrawl [{fc.status_code}]: {fc.text[:500]}')
    fc_data = fc.json()
    if not fc_data.get('success'): raise RuntimeError(f'Firecrawl !success: {fc_data}')
    md = fc_data.get('data',{}).get('markdown','')
    html = fc_data.get('data',{}).get('html','')
    text = md if md else re.sub(r'<[^>]+>', ' ', html)
    summary['fc_md_chars'] = len(md); summary['fc_html_chars'] = len(html)
    print(f'Firecrawl: md={len(md):,} html={len(html):,}')
    print('=== MD HEAD ===')
    print(text[:2500])
    print('=== END ===')
    if 'User Name or Password is Invalid' in text: summary['behind_login'] = True

    parcel_re = re.compile(r'\b(\d{7,8})\b')
    money_re = re.compile(r'\$\s*([\d,]+\.\d{2})')
    status_re = re.compile(r'(SOLD|CANCELED|CANCELLED|REDEEMED|WITHDRAWN|STRUCK\s*OFF|READY|PENDING)', re.IGNORECASE)
    case_re = re.compile(r'(\d{2,4}[-\s]?(?:TD|CA|FC)[-\s]?\d{3,6})', re.IGNORECASE)
    all_parcels = list(set(parcel_re.findall(text)))
    all_moneys = money_re.findall(text)
    all_statuses = list(set(s.upper() for s in status_re.findall(text)))
    print(f'Found: {len(all_parcels)} parcels, {len(all_moneys)} amounts, statuses={all_statuses}')
    summary.update({'parcels_found': len(all_parcels), 'amounts_found': len(all_moneys), 'statuses_present': all_statuses})

    rows = []; seen = set()
    for m in parcel_re.finditer(text):
        pid = m.group(1)
        if pid in seen: continue
        seen.add(pid)
        ctx = text[max(0, m.start()-600):min(len(text), m.end()+600)]
        ctx_moneys = money_re.findall(ctx)
        ctx_statuses = list(set(s.upper() for s in status_re.findall(ctx)))
        ctx_cases = case_re.findall(ctx)
        canonical = None
        if 'SOLD' in ctx_statuses: canonical = 'SOLD'
        elif 'CANCELED' in ctx_statuses or 'CANCELLED' in ctx_statuses: canonical = 'CANCELED'
        elif 'REDEEMED' in ctx_statuses: canonical = 'REDEEMED'
        elif 'STRUCK OFF' in ctx_statuses: canonical = 'STRUCK_OFF'
        elif 'WITHDRAWN' in ctx_statuses: canonical = 'WITHDRAWN'
        elif 'READY' in ctx_statuses or 'PENDING' in ctx_statuses: canonical = 'LISTED'
        rows.append({'parcel': pid, 'case': ctx_cases[0].upper().replace(' ','') if ctx_cases else None,
                     'amounts': ctx_moneys[:6], 'canonical_status': canonical, 'raw_statuses': ctx_statuses})

    upserted = 0
    for row in rows:
        confidence = 'tier1_verified' if row['canonical_status'] else 'tier1_inferred'
        sold_amt = None
        if row['canonical_status'] == 'SOLD' and row['amounts']:
            amts = [float(a.replace(',','')) for a in row['amounts']]
            sold_amt = max([a for a in amts if a < 5_000_000], default=None)
        try:
            rpc('tier1_upsert_rpc', {'p': {
                'county': COUNTY_SLUG, 'parcel_id': row['parcel'],
                'auction_date': AUCTION_DATE_STR, 'case_number': row['case'],
                'sale_status': row['canonical_status'] or 'LISTED',
                'sold_amount': sold_amt, 'opening_bid': None, 'aid': None,
                'source_platform': PLATFORM, 'source_url': PREVIEW_URL,
                'run_id': str(run_id),
                'raw_context': f'amounts={row["amounts"][:5]} statuses={row["raw_statuses"]}',
                'confidence': confidence,
            }})
            upserted += 1
        except Exception as e:
            if upserted < 3: print(f'  ! upsert fail {row["parcel"]}: {e}')

    summary['rows_upserted'] = upserted
    print(f'Upserted {upserted} rows to tier1_today for {COUNTY_SLUG}')
    rpc('scrape_log_finish', {'p_run_id': run_id, 'p_status': 'success',
        'p_rows_in': len(rows), 'p_rows_inserted': upserted, 'p_notes': json.dumps(summary)[:6000]})

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
