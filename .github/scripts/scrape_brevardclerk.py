#!/usr/bin/env python3
"""Brevard Tier1 v9.3 - Schema-driven per-card parser. Clean chunk semantics."""
import os, re, sys, json
from datetime import date
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
print(f'>>> v9.3 clean, run={run_id}')

try:
    summary = {'parser':'v9.3_clean','url':PREVIEW_URL}

    # 1. Load extraction schema
    schema_rows = sel('v_realauction_schema', 'select=*')
    schema_by_field = {f['field_name']: f for f in schema_rows}
    print(f'Loaded {len(schema_rows)} schema fields')

    # 2. Firecrawl
    fc = requests.post('https://api.firecrawl.dev/v1/scrape',
        headers={'Authorization':f'Bearer {FIRECRAWL_KEY}','Content-Type':'application/json'},
        json={'url':PREVIEW_URL,'formats':['markdown'],'waitFor':6000,'onlyMainContent':False},
        timeout=120)
    if fc.status_code != 200: raise RuntimeError(f'Firecrawl {fc.status_code}: {fc.text[:400]}')
    md = fc.json().get('data',{}).get('markdown','')
    print(f'Markdown: {len(md):,} chars')
    summary['fc_md_chars'] = len(md)

    # 3. Anchor cards on Parcel ID. For each card:
    #    LEFT scope = md[prev_parcel.end() : current_parcel.end()]
    #         contains: prev_card_tail (noise) + current LEFT panel + current right panel up to Parcel ID
    #    RIGHT scope = md[current_parcel.end() : next_AT.start() or end]
    #         contains: current address + assessed + footer (clean — next card's status NOT yet)
    parcel_anchors = list(re.finditer(r'Parcel\s*ID[^\d]+(\d{6,9})', md, re.IGNORECASE))
    at_anchors = list(re.finditer(r'Auction\s*Type', md, re.IGNORECASE))
    print(f'Anchors: parcel={len(parcel_anchors)} auction_type={len(at_anchors)}')

    LEFT_FIELDS  = {'sold_timestamp','sold_amount','sold_to','auction_type','case_number','certificate_number','opening_bid'}
    RIGHT_FIELDS = {'property_address','assessed_value','name_on_title'}
    status_map = (schema_by_field.get('auction_status', {}) or {}).get('normalization') or {}
    sold_to_map = (schema_by_field.get('sold_to', {}) or {}).get('normalization') or {}

    extracted = []
    for i, m in enumerate(parcel_anchors):
        prev_end = parcel_anchors[i-1].end() if i > 0 else max(0, m.start() - 1500)
        left_scope = md[prev_end : m.end()]
        # Right scope: from current parcel to next Auction Type (or 400 chars)
        next_at_start = next((a.start() for a in at_anchors if a.start() > m.end()), m.end() + 400)
        right_scope = md[m.end() : next_at_start]

        raw = {'parcel_id_text': m.group(1)}

        # Status detection — find LAST status keyword in left_scope (the one closest to current parcel = current card's)
        last_status_pos = -1
        last_status_label = None
        for label in status_map.keys():
            for sm in re.finditer(re.escape(label), left_scope, re.IGNORECASE):
                if sm.start() > last_status_pos:
                    last_status_pos = sm.start()
                    last_status_label = label
        if last_status_label:
            raw['raw_status_text'] = last_status_label

        # Apply schema regexes
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
            except re.error as e:
                print(f'  ! regex {fn}: {e}')

        # Clean sold_to: strip trailing markdown garbage and "Auction Type" if it sneaks in
        if raw.get('sold_to_text'):
            sto = re.sub(r'[\s|\-_]+',' ', raw['sold_to_text'])
            sto = re.sub(r'\s*(Auction Type|Name on Title|Bid History).*$','', sto, flags=re.IGNORECASE).strip()
            raw['sold_to_text'] = sto[:80] if sto else None

        raw['raw_card_text'] = (left_scope[-400:] + ' | RIGHT: ' + right_scope[:400])[:1500]
        # Confidence: high if both status AND sold_amount/opening_bid present
        if raw.get('raw_status_text') and raw.get('opening_bid_text'):
            raw['parse_confidence'] = 'high'
        elif raw.get('opening_bid_text'):
            raw['parse_confidence'] = 'partial'
        else:
            raw['parse_confidence'] = 'low'
        extracted.append(raw)

    print(f'\n=== EXTRACTED {len(extracted)} CARDS ===')
    for c in extracted:
        print(f"  {c.get('parcel_id_text')}: status={c.get('raw_status_text','?')} "
              f"sold=${c.get('sold_amount_text','-')} to={c.get('sold_to_text','-')} "
              f"open=${c.get('opening_bid_text','-')} assessed=${c.get('assessed_value_text','-')} "
              f"addr={(c.get('property_address_text') or '')[:30]}")

    # 4. Upsert
    upserted = 0
    for c in extracted:
        try:
            rpc('tier1_card_upsert_rpc', {'p': {'county':'brevard','platform':'realforeclose','run_id':str(run_id), **c}})
            upserted += 1
        except Exception as e:
            print(f'  ! upsert {c.get("parcel_id_text")}: {e}')

    summary.update({
        'parcels_anchored': len(parcel_anchors),
        'cards_extracted': len(extracted),
        'cards_high_conf': sum(1 for c in extracted if c.get('parse_confidence')=='high'),
        'rows_upserted': upserted,
    })
    print(f'\n=== UPSERTED {upserted}/{len(extracted)} ===')
    rpc('scrape_log_finish', {'p_run_id':run_id,'p_status':'success','p_rows_in':len(extracted),'p_rows_inserted':upserted,'p_notes':json.dumps(summary)[:6000]})
except Exception as e:
    import traceback
    err = f'{type(e).__name__}: {e}\n{traceback.format_exc()[:1200]}'
    print(f'ERROR: {err}', file=sys.stderr)
    try:
        requests.post(f'{REST}/rpc/scrape_log_finish', json={'p_run_id':run_id,'p_status':'failed','p_error':err[:2000]}, headers=H, timeout=15)
    except Exception: pass
    sys.exit(1)
