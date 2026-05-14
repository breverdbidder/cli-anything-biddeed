#!/usr/bin/env python3
"""Brevard Tier1 v9 - Schema-driven per-card parser using config.realauction_card_schema."""
import os, re, sys, json
from datetime import date, datetime
import requests

SUPABASE_URL = os.environ['SUPABASE_URL'].rstrip('/')
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
FIRECRAWL_KEY = os.environ.get('FIRECRAWL_API_KEY','')
AUCTION_DATE_STR = os.environ.get('AUCTION_DATE','2026-05-14')
VERBOSE = os.environ.get('VERBOSE','true').lower()=='true'
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

run_id = rpc('scrape_log_start', {
    'p_source':'brevard_realforeclose','p_county':'brevard',
    'p_sale_type':'tax_deed','p_auction_date':AUCTION_DATE_STR,
    'p_triggered_by':'gha_workflow_dispatch_v9',
})
print(f'>>> v9 schema-driven, run={run_id}')

try:
    summary = {'parser':'v9_schema_driven','url':PREVIEW_URL}

    # 1. Load extraction schema from DB
    schema_rows = sel('v_realauction_schema', 'select=*')
    print(f'Loaded {len(schema_rows)} schema fields')

    # 2. Firecrawl scrape
    fc = requests.post('https://api.firecrawl.dev/v1/scrape',
        headers={'Authorization':f'Bearer {FIRECRAWL_KEY}','Content-Type':'application/json'},
        json={'url':PREVIEW_URL,'formats':['markdown'],'waitFor':6000,'onlyMainContent':False},
        timeout=120)
    if fc.status_code != 200: raise RuntimeError(f'Firecrawl {fc.status_code}: {fc.text[:400]}')
    md = fc.json().get('data',{}).get('markdown','')
    print(f'Markdown: {len(md):,} chars')
    summary['fc_md_chars'] = len(md)

    if VERBOSE:
        i = md.lower().find('auctions closed')
        if i > 0:
            print(f'\n--- MD FROM CLOSED SECTION (3500 chars) ---')
            print(md[i:i+3500])
            print('--- END ---\n')

    # 3. Split into cards by Parcel ID anchor
    parcel_anchors = list(re.finditer(r'Parcel\s*ID[^\d]+(\d{6,9})', md, re.IGNORECASE))
    print(f'Found {len(parcel_anchors)} parcel anchors')

    cards = []
    for i, m in enumerate(parcel_anchors):
        chunk_start = parcel_anchors[i-1].end() if i > 0 else max(0, m.start() - 1500)
        chunk_end = min(len(md), m.end() + 400)
        cards.append({
            'parcel_id_anchor': m.group(1),
            'chunk': md[chunk_start:chunk_end],
        })

    # 4. For each card, apply schema patterns
    extracted = []
    for card in cards:
        chunk = card['chunk']
        raw = {}
        for field in schema_rows:
            pat = field.get('extraction_pattern')
            if not pat or pat == 'first text in left panel': continue
            try:
                # Use DOTALL because card text spans multiple newlines
                mm = re.search(pat, chunk, re.IGNORECASE | re.DOTALL)
                if mm:
                    raw[field['field_name'] + '_text'] = mm.group(1).strip()[:200]
            except re.error as e:
                print(f'  ! regex error for {field["field_name"]}: {e}')

        # Special: detect status from left-panel text BEFORE "Auction Type"
        i_at = chunk.lower().find('auction type')
        left_panel = chunk[:i_at] if i_at > 0 else chunk[:500]
        status_map = next((f['normalization'] for f in schema_rows if f['field_name']=='auction_status' and f.get('normalization')), {}) or {}
        raw_status = None
        for label in sorted(status_map.keys(), key=len, reverse=True):
            if label.lower() in left_panel.lower():
                raw_status = label
                break
        if raw_status: raw['raw_status_text'] = raw_status

        # Extract sold_to from left panel "Sold To\s+(.+?)" pattern
        st = re.search(r'Sold To[:\s\n|]+(.+?)(?=Auction Type|Name on Title|Bid History|$)', left_panel, re.IGNORECASE | re.DOTALL)
        if st:
            sto = re.sub(r'[\s|]+', ' ', st.group(1)).strip()[:80]
            if sto and sto.lower() not in ('','sold to'):
                raw['sold_to_text'] = sto

        # Sold timestamp: look for date pattern in left panel
        ts = re.search(r'(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}\s+[AP]M\s+ET)', left_panel)
        if ts: raw['sold_timestamp_text'] = ts.group(1)

        if raw.get('parcel_id_text'):
            raw['raw_card_text'] = chunk[:1500]
            raw['parse_confidence'] = 'high' if raw.get('raw_status_text') and raw.get('opening_bid_text') else 'partial'
            extracted.append(raw)

    print(f'\n=== EXTRACTED {len(extracted)} CARDS ===')
    for c in extracted[:5]:
        print(f"  parcel={c.get('parcel_id_text')} status={c.get('raw_status_text')} "
              f"open={c.get('opening_bid_text')} sold={c.get('sold_amount_text')} "
              f"sold_to={c.get('sold_to_text')} assessed={c.get('assessed_value_text')}")
    print(f'  ... (showing first 5 of {len(extracted)})')

    # 5. Upsert via canonical RPC (auto-normalizes per schema)
    upserted = 0
    for c in extracted:
        try:
            rpc('tier1_card_upsert_rpc', {'p': {
                'county':'brevard','platform':'realforeclose','run_id':str(run_id),
                **c
            }})
            upserted += 1
        except Exception as e:
            if upserted < 3: print(f'  ! upsert {c.get("parcel_id_text")}: {e}')

    summary.update({
        'parcels_anchored': len(parcel_anchors),
        'cards_extracted': len(extracted),
        'cards_high_conf': sum(1 for c in extracted if c.get('parse_confidence')=='high'),
        'rows_upserted': upserted,
    })
    print(f'\n=== UPSERTED {upserted}/{len(extracted)} ===')

    rpc('scrape_log_finish', {
        'p_run_id':run_id,'p_status':'success',
        'p_rows_in':len(extracted),'p_rows_inserted':upserted,
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
