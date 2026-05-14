#!/usr/bin/env python3
"""Brevard Tier1 v9.4 - Schema-driven + FULL PAGINATION across all PREVIEW pages.
Uses Firecrawl actions to click 'Next Page' N times before scraping each state."""
import os, re, sys, json
from datetime import date
import requests

SUPABASE_URL = os.environ['SUPABASE_URL'].rstrip('/')
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
FIRECRAWL_KEY = os.environ['FIRECRAWL_API_KEY']
AUCTION_DATE_STR = os.environ.get('AUCTION_DATE','2026-05-14')
MAX_PAGES = int(os.environ.get('MAX_PAGES','15'))
AUCTION_DATE = date.fromisoformat(AUCTION_DATE_STR)
DATE_SLASH = AUCTION_DATE.strftime('%m/%d/%Y')
PREVIEW_URL = f'https://brevard.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={DATE_SLASH}'

REST = f'{SUPABASE_URL}/rest/v1'
H = {'apikey':SUPABASE_KEY,'Authorization':f'Bearer {SUPABASE_KEY}','Content-Type':'application/json','Prefer':'return=representation'}

def rpc(name, params):
    r = requests.post(f'{REST}/rpc/{name}', json=params, headers=H, timeout=60)
    if r.status_code >= 400: raise RuntimeError(f'RPC {name} [{r.status_code}]: {r.text[:400]}')
    return r.json() if r.text and r.text.strip() else None

def sel(table, q=''):
    r = requests.get(f'{REST}/{table}?{q}', headers={'apikey':SUPABASE_KEY,'Authorization':f'Bearer {SUPABASE_KEY}'}, timeout=30)
    r.raise_for_status(); return r.json()

# Selectors to try for "Next Page" button (RealAuction variants across counties)
NEXT_SELECTORS = "img[src*='nextpage'], a[title*='Next'], #fcdt, .NaviSt, a.pagiNext, .pagenav-next, a[onclick*='setPage']"

def firecrawl_scrape_at_page(url, clicks_before):
    """Fetch URL after clicking Next N times. Returns markdown."""
    actions = [{'type':'wait','milliseconds':6000}]
    for _ in range(clicks_before):
        actions.append({'type':'click','selector':NEXT_SELECTORS})
        actions.append({'type':'wait','milliseconds':2500})
    actions.append({'type':'wait','milliseconds':1500})

    fc = requests.post('https://api.firecrawl.dev/v1/scrape',
        headers={'Authorization':f'Bearer {FIRECRAWL_KEY}','Content-Type':'application/json'},
        json={'url':url,'formats':['markdown'],'actions':actions,'onlyMainContent':False,'timeout':90000},
        timeout=180)
    if fc.status_code != 200:
        raise RuntimeError(f'Firecrawl {fc.status_code}: {fc.text[:300]}')
    return fc.json().get('data',{}).get('markdown','')

def extract_cards_from_md(md, schema_by_field, status_map):
    parcel_anchors = list(re.finditer(r'Parcel\s*ID[^\d]+(\d{6,12})', md, re.IGNORECASE))
    at_anchors = list(re.finditer(r'Auction\s*Type', md, re.IGNORECASE))
    LEFT_FIELDS = {'auction_status','sold_timestamp','sold_amount','sold_to','auction_type','case_number','certificate_number','opening_bid'}
    RIGHT_FIELDS = {'property_address','assessed_value','name_on_title'}
    cards = []
    for i, m in enumerate(parcel_anchors):
        prev_end = parcel_anchors[i-1].end() if i > 0 else max(0, m.start() - 1500)
        left_scope = md[prev_end : m.end()]
        next_at_start = next((a.start() for a in at_anchors if a.start() > m.end()), m.end() + 400)
        right_scope = md[m.end() : next_at_start]
        raw = {'parcel_id_text': m.group(1)}
        # Status detection
        last_pos, last_label = -1, None
        for label in status_map.keys():
            for sm in re.finditer(re.escape(label), left_scope, re.IGNORECASE):
                if sm.start() > last_pos: last_pos, last_label = sm.start(), label
        if last_label: raw['raw_status_text'] = last_label
        # Schema regexes
        for fn, field in schema_by_field.items():
            if fn in ('parcel_id','auction_status'): continue
            pat = field.get('extraction_pattern')
            if not pat or pat == 'first text in left panel': continue
            scope = right_scope if fn in RIGHT_FIELDS else left_scope
            try:
                mm = re.search(pat, scope, re.IGNORECASE | re.DOTALL)
                if mm:
                    val = re.sub(r'[\s|\-_]+$','', mm.group(1).strip())[:200]
                    if val: raw[fn + '_text'] = val
            except re.error: pass
        if raw.get('sold_to_text'):
            sto = re.sub(r'[\s|\-_]+',' ', raw['sold_to_text']).strip()
            sto = re.sub(r'\s*(Auction Type|Name on Title|Bid History).*$','', sto, flags=re.IGNORECASE).strip()
            raw['sold_to_text'] = sto[:80] if sto else None
        raw['raw_card_text'] = (left_scope[-600:] + ' | RIGHT: ' + right_scope[:400])[:1500]
        raw['parse_confidence'] = 'high' if raw.get('raw_status_text') and raw.get('opening_bid_text') else 'partial'
        cards.append(raw)
    return cards

run_id = rpc('scrape_log_start', {
    'p_source':'brevard_realforeclose','p_county':'brevard',
    'p_sale_type':'tax_deed','p_auction_date':AUCTION_DATE_STR,
    'p_triggered_by':'gha_workflow_dispatch_v9_4_paginated',
})
print(f'>>> v9.4 PAGINATED, run={run_id}, max_pages={MAX_PAGES}')

try:
    schema_rows = sel('v_realauction_schema', 'select=*')
    schema_by_field = {f['field_name']: f for f in schema_rows}
    status_map = schema_by_field['auction_status']['normalization'] or {}

    seen_parcels = set()
    all_cards = []
    page_stats = []
    page_n = 0
    while page_n < MAX_PAGES:
        print(f'\n--- PAGE {page_n+1} (clicks={page_n}) ---')
        try:
            md = firecrawl_scrape_at_page(PREVIEW_URL, page_n)
        except Exception as e:
            print(f'  ! firecrawl: {e}')
            break
        cards = extract_cards_from_md(md, schema_by_field, status_map)
        new = [c for c in cards if c['parcel_id_text'] not in seen_parcels]
        for c in new:
            seen_parcels.add(c['parcel_id_text'])
            all_cards.append(c)
        page_stats.append({'page':page_n+1,'md_chars':len(md),'cards':len(cards),'new':len(new)})
        print(f'  md={len(md):,} cards={len(cards)} new={len(new)} total={len(all_cards)}')
        if len(new) == 0 and page_n > 0:
            print(f'  → no new parcels, stopping')
            break
        page_n += 1

    print(f'\n=== TOTAL: {len(all_cards)} unique cards across {page_n+1} pages ===')

    upserted = 0
    for c in all_cards:
        try:
            rpc('tier1_card_upsert_rpc', {'p': {
                'county':'brevard','platform':'realforeclose','run_id':str(run_id),
                **c
            }})
            upserted += 1
        except Exception as e:
            if upserted < 3: print(f'  ! upsert {c.get("parcel_id_text")}: {e}')

    summary = {
        'parser':'v9.4_paginated',
        'pages_scraped': len(page_stats),
        'total_cards': len(all_cards),
        'high_conf': sum(1 for c in all_cards if c['parse_confidence']=='high'),
        'rows_upserted': upserted,
        'page_stats': page_stats[:20],
    }
    print(json.dumps(summary, indent=2)[:2000])

    rpc('scrape_log_finish', {
        'p_run_id':run_id,'p_status':'success',
        'p_rows_in':len(all_cards),'p_rows_inserted':upserted,
        'p_notes':json.dumps(summary)[:6000],
    })

except Exception as e:
    import traceback
    err = f'{type(e).__name__}: {e}\n{traceback.format_exc()[:1200]}'
    print(f'ERROR: {err}', file=sys.stderr)
    try:
        requests.post(f'{REST}/rpc/scrape_log_finish',
            json={'p_run_id':run_id,'p_status':'failed','p_error':err[:2000]},
            headers=H, timeout=15)
    except Exception: pass
    sys.exit(1)
