#!/usr/bin/env python3
"""RealAuction county scraper - v9.5 Firecrawl actions pagination.
Clicks .PageRight[area='C'] iteratively to walk through all closed/canceled pages."""
import os, re, sys, json, time
from datetime import date
import requests

SUPABASE_URL = os.environ['SUPABASE_URL'].rstrip('/')
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
FIRECRAWL_KEY = os.environ['FIRECRAWL_API_KEY']
COUNTY_SLUG = os.environ['COUNTY_SLUG'].lower().strip()
COUNTY_DOMAIN = os.environ['COUNTY_DOMAIN'].strip()
AUCTION_DATE_STR = os.environ['AUCTION_DATE']
MAX_PAGES = int(os.environ.get('MAX_PAGES', '15'))
SECTION_AREA = os.environ.get('SECTION_AREA', 'C')   # 'C' closed/canceled, 'R' running
AUCTION_DATE = date.fromisoformat(AUCTION_DATE_STR)
DATE_SLASH = AUCTION_DATE.strftime('%m/%d/%Y')

PLATFORM = 'realtaxdeed' if 'realtaxdeed' in COUNTY_DOMAIN else \
           'realforeclose' if 'realforeclose' in COUNTY_DOMAIN else \
           'realtdm' if 'realtdm' in COUNTY_DOMAIN else 'realauction'
SOURCE_CODE = f'{COUNTY_SLUG}_{PLATFORM}'
URL = f'https://{COUNTY_DOMAIN}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={DATE_SLASH}'

REST = f'{SUPABASE_URL}/rest/v1'
H = {'apikey':SUPABASE_KEY,'Authorization':f'Bearer {SUPABASE_KEY}','Content-Type':'application/json','Prefer':'return=representation'}

def rpc(name, params):
    r = requests.post(f'{REST}/rpc/{name}', json=params, headers=H, timeout=60)
    if r.status_code >= 400: raise RuntimeError(f'RPC {name} [{r.status_code}]: {r.text[:400]}')
    return r.json() if r.text and r.text.strip() else None

def sel(table, q=''):
    r = requests.get(f'{REST}/{table}?{q}', headers={'apikey':SUPABASE_KEY,'Authorization':f'Bearer {SUPABASE_KEY}'}, timeout=30)
    r.raise_for_status(); return r.json()

def parse_cards(md, schema_by_field, status_map):
    parcel_anchors = list(re.finditer(r'Parcel\s*ID[^\d]+(\d{6,15})', md, re.IGNORECASE))
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
        last_status_pos, last_status_label = -1, None
        for label in status_map.keys():
            for sm in re.finditer(re.escape(label), left_scope, re.IGNORECASE):
                if sm.start() > last_status_pos:
                    last_status_pos, last_status_label = sm.start(), label
        if last_status_label: raw['raw_status_text'] = last_status_label
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
        raw['raw_card_text'] = (left_scope[-800:] + ' | RIGHT: ' + right_scope[:600])[:1500]
        raw['parse_confidence'] = 'high' if raw.get('raw_status_text') and raw.get('opening_bid_text') else 'partial'
        cards.append(raw)
    return cards

run_id = rpc('scrape_log_start', {
    'p_source':SOURCE_CODE,'p_county':COUNTY_SLUG,
    'p_sale_type':'tax_deed','p_auction_date':AUCTION_DATE_STR,
    'p_triggered_by':'gha_actions_paginated_v9_5',
})
print(f'>>> {SOURCE_CODE} v9.5 actions pagination, run={run_id}, area={SECTION_AREA}, max={MAX_PAGES}')

try:
    schema_rows = sel('v_realauction_schema', 'select=*')
    schema_by_field = {f['field_name']: f for f in schema_rows}
    status_map = schema_by_field['auction_status']['normalization'] or {}

    # Build Firecrawl actions: wait, scrape page 1, then for each subsequent page: click Next, wait, scrape
    actions = [
        {'type':'wait','milliseconds':6000},
        {'type':'screenshot'},
        {'type':'scrape'},
    ]
    selector = f".PageFrame[area='{SECTION_AREA}'] .PageRight"
    for _ in range(MAX_PAGES - 1):
        actions.append({'type':'click','selector':selector})
        actions.append({'type':'wait','milliseconds':2500})
        actions.append({'type':'scrape'})

    print(f'Firecrawl action sequence: {len(actions)} steps (selector={selector})')
    fc = requests.post('https://api.firecrawl.dev/v1/scrape',
        headers={'Authorization':f'Bearer {FIRECRAWL_KEY}','Content-Type':'application/json'},
        json={'url':URL,'formats':['markdown'],'actions':actions,'onlyMainContent':False,'timeout':120000},
        timeout=180)
    if fc.status_code != 200:
        raise RuntimeError(f'Firecrawl {fc.status_code}: {fc.text[:500]}')
    data = fc.json().get('data',{})
    scrapes = (data.get('actions') or {}).get('scrapes',[]) or []
    final_md = data.get('markdown','')
    print(f'Firecrawl returned {len(scrapes)} action-scrape snapshots, final_md={len(final_md):,} chars')
    print(f'data keys: {list(data.keys())}')
    if data.get('actions'): print(f'actions keys: {list(data['actions'].keys())}')
    if scrapes:
        print(f'first scrape keys: {list(scrapes[0].keys())}')
        print(f'first scrape sample: {json.dumps(scrapes[0])[:800]}')

    seen_parcels = set()
    all_cards = []
    per_page = []
    for i, snap in enumerate(scrapes):
        md = snap.get('markdown','') or snap.get('content','')
        cards = parse_cards(md, schema_by_field, status_map)
        new = [c for c in cards if c.get('parcel_id_text') and c['parcel_id_text'] not in seen_parcels]
        for c in cards:
            if c.get('parcel_id_text'): seen_parcels.add(c['parcel_id_text'])
        per_page.append({'page':i+1,'md_chars':len(md),'cards':len(cards),'new':len(new)})
        print(f'  page {i+1}: md={len(md):,} cards={len(cards)} new={len(new)}')
        all_cards.extend(new)
        if i > 0 and len(new) == 0:
            print(f'  page {i+1} returned no new — pagination exhausted'); break

    # Fallback: parse final_md too if scrapes was empty
    if not scrapes and final_md:
        cards = parse_cards(final_md, schema_by_field, status_map)
        for c in cards:
            if c.get('parcel_id_text') and c['parcel_id_text'] not in seen_parcels:
                seen_parcels.add(c['parcel_id_text']); all_cards.append(c)
        per_page.append({'page':'final_md_fallback','md_chars':len(final_md),'cards':len(cards)})

    print(f'\n=== UNIQUE CARDS: {len(all_cards)} across {len(per_page)} snapshots ===')
    upserted = 0
    for c in all_cards:
        try:
            rpc('tier1_card_upsert_rpc', {'p': {
                'county':COUNTY_SLUG,'platform':PLATFORM,'run_id':str(run_id), **c
            }})
            upserted += 1
        except Exception as e:
            if upserted < 5: print(f'  ! upsert {c.get("parcel_id_text")}: {e}')

    summary = {
        'parser':'v9.5_actions_paginated','county':COUNTY_SLUG,'platform':PLATFORM,
        'url':URL,'section_area':SECTION_AREA,
        'snapshots_returned':len(scrapes),'unique_cards':len(all_cards),
        'rows_upserted':upserted,'per_page':per_page,
    }
    print(f'UPSERTED {upserted}/{len(all_cards)}')
    rpc('scrape_log_finish', {
        'p_run_id':run_id,'p_status':'success',
        'p_rows_in':len(all_cards),'p_rows_inserted':upserted,
        'p_notes':json.dumps(summary)[:6000],
    })

except Exception as e:
    import traceback
    err = f'{type(e).__name__}: {e}\n{traceback.format_exc()[:1500]}'
    print(f'ERROR: {err}', file=sys.stderr)
    try:
        requests.post(f'{REST}/rpc/scrape_log_finish',
            json={'p_run_id':run_id,'p_status':'failed','p_error':err[:2000]},
            headers=H, timeout=15)
    except Exception: pass
    sys.exit(1)
