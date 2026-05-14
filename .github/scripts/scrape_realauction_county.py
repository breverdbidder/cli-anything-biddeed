#!/usr/bin/env python3
"""Generic RealAuction county scraper - v9.3 schema-driven card parsing.
Parameterized via env: COUNTY_SLUG, COUNTY_DOMAIN, AUCTION_DATE.
Works for ANY county on realforeclose.com / realtaxdeed.com / realtdm.com / realauction.com."""
import os, re, sys, json
from datetime import date
import requests

SUPABASE_URL = os.environ['SUPABASE_URL'].rstrip('/')
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
FIRECRAWL_KEY = os.environ['FIRECRAWL_API_KEY']
COUNTY_SLUG = os.environ['COUNTY_SLUG'].lower().strip()
COUNTY_DOMAIN = os.environ['COUNTY_DOMAIN'].strip()
AUCTION_DATE_STR = os.environ['AUCTION_DATE']
AUCTION_DATE = date.fromisoformat(AUCTION_DATE_STR)
DATE_SLASH = AUCTION_DATE.strftime('%m/%d/%Y')

# Source-system slug: e.g. osceola_realtaxdeed
PLATFORM = 'realtaxdeed' if 'realtaxdeed' in COUNTY_DOMAIN else \
           'realforeclose' if 'realforeclose' in COUNTY_DOMAIN else \
           'realtdm' if 'realtdm' in COUNTY_DOMAIN else 'realauction'
SOURCE_CODE = f'{COUNTY_SLUG}_{PLATFORM}'
PREVIEW_URL = f'https://{COUNTY_DOMAIN}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={DATE_SLASH}'

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
    'p_source':SOURCE_CODE,'p_county':COUNTY_SLUG,
    'p_sale_type':'tax_deed','p_auction_date':AUCTION_DATE_STR,
    'p_triggered_by':'gha_multi_county_v9_3',
})
print(f'>>> {SOURCE_CODE} v9.3 schema-driven, run={run_id}, url={PREVIEW_URL}')

try:
    summary = {'parser':'v9.3_multi_county','county':COUNTY_SLUG,'platform':PLATFORM,'url':PREVIEW_URL}
    schema_rows = sel('v_realauction_schema', 'select=*')
    schema_by_field = {f['field_name']: f for f in schema_rows}
    status_map = schema_by_field['auction_status']['normalization'] or {}
    print(f'Loaded {len(schema_rows)} schema fields, {len(status_map)} status labels')

    # Firecrawl fetch
    fc = requests.post('https://api.firecrawl.dev/v1/scrape',
        headers={'Authorization':f'Bearer {FIRECRAWL_KEY}','Content-Type':'application/json'},
        json={'url':PREVIEW_URL,'formats':['markdown'],'waitFor':6000,'onlyMainContent':False},
        timeout=120)
    if fc.status_code != 200: raise RuntimeError(f'Firecrawl {fc.status_code}: {fc.text[:400]}')
    md = fc.json().get('data',{}).get('markdown','')
    print(f'MD: {len(md):,} chars')
    summary['fc_md_chars'] = len(md)

    # Anchor on Parcel IDs + Auction Type for chunking
    parcel_anchors = list(re.finditer(r'Parcel\s*ID[^\d]+(\d{6,12})', md, re.IGNORECASE))
    at_anchors = list(re.finditer(r'Auction\s*Type', md, re.IGNORECASE))
    print(f'Anchors: parcels={len(parcel_anchors)} auction_type={len(at_anchors)}')
    summary['parcels_anchored'] = len(parcel_anchors)

    LEFT_FIELDS = {'auction_status','sold_timestamp','sold_amount','sold_to','auction_type','case_number','certificate_number','opening_bid'}
    RIGHT_FIELDS = {'property_address','assessed_value','name_on_title'}
    extracted = []

    for i, m in enumerate(parcel_anchors):
        prev_end = parcel_anchors[i-1].end() if i > 0 else max(0, m.start() - 1500)
        left_scope = md[prev_end : m.end()]
        next_at_start = next((a.start() for a in at_anchors if a.start() > m.end()), m.end() + 400)
        right_scope = md[m.end() : next_at_start]

        raw = {'parcel_id_text': m.group(1)}

        # Status detection: find LAST status keyword in left_scope (= current card's, since latest is closest to PID)
        last_status_pos, last_status_label = -1, None
        for label in status_map.keys():
            for sm in re.finditer(re.escape(label), left_scope, re.IGNORECASE):
                if sm.start() > last_status_pos:
                    last_status_pos, last_status_label = sm.start(), label
        if last_status_label: raw['raw_status_text'] = last_status_label

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

        # Clean up sold_to artifacts
        if raw.get('sold_to_text'):
            sto = re.sub(r'[\s|\-_]+',' ', raw['sold_to_text']).strip()
            sto = re.sub(r'\s*(Auction Type|Name on Title|Bid History).*$','', sto, flags=re.IGNORECASE).strip()
            raw['sold_to_text'] = sto[:80] if sto else None

        raw['raw_card_text'] = (left_scope[-800:] + ' | RIGHT: ' + right_scope[:600])[:1500]
        raw['parse_confidence'] = 'high' if raw.get('raw_status_text') and raw.get('opening_bid_text') else 'partial'
        extracted.append(raw)

    print(f'\nExtracted {len(extracted)} cards (high_conf={sum(1 for c in extracted if c["parse_confidence"]=="high")})')
    for c in extracted[:3]:
        print(f"  parcel={c.get('parcel_id_text')} status={c.get('raw_status_text')} "
              f"open={c.get('opening_bid_text')} sold={c.get('sold_amount_text')} assessed={c.get('assessed_value_text')}")

    upserted = 0
    for c in extracted:
        try:
            rpc('tier1_card_upsert_rpc', {'p': {
                'county':COUNTY_SLUG,'platform':PLATFORM,'run_id':str(run_id),
                **c
            }})
            upserted += 1
        except Exception as e:
            if upserted < 3: print(f'  ! upsert {c.get("parcel_id_text")}: {e}')

    summary.update({
        'cards_extracted': len(extracted),
        'cards_high_conf': sum(1 for c in extracted if c['parse_confidence']=='high'),
        'rows_upserted': upserted,
    })
    print(f'\nUPSERTED {upserted}/{len(extracted)}')

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
