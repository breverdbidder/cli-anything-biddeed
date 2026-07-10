#!/usr/bin/env python3
"""Brevard Tier1 v9.20 - Firecrawl with page navigation (proven from v9.12) + multi sold-to.
The AJAX FNC=LOAD endpoint returns empty @AASTAT placeholders; status is populated client-side
via JS polling that Firecrawl runs. So we use Firecrawl + #curPCA input write to advance pages."""
import os, re, sys, json
from datetime import date
import requests

SUPABASE_URL = os.environ['SUPABASE_URL'].rstrip('/')
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
FIRECRAWL_KEY = os.environ['FIRECRAWL_API_KEY']
AUCTION_DATE_STR = os.environ.get('AUCTION_DATE','2026-05-14')
MAX_PAGES = int(os.environ.get('MAX_PAGES','15'))
DATE_SLASH = date.fromisoformat(AUCTION_DATE_STR).strftime('%m/%d/%Y')
PREVIEW_URL = f'https://brevard.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={DATE_SLASH}'

REST = f'{SUPABASE_URL}/rest/v1'
H = {'apikey':SUPABASE_KEY,'Authorization':f'Bearer {SUPABASE_KEY}','Content-Type':'application/json','Prefer':'return=representation'}

def rpc(name, params):
    r = requests.post(f'{REST}/rpc/{name}', json=params, headers=H, timeout=60)
    if r.status_code >= 400: raise RuntimeError(f'RPC {name} [{r.status_code}]: {r.text[:400]}')
    return r.json() if r.text and r.text.strip() else None

def firecrawl_page(page_num):
    """Fetch markdown for page N of 'Auctions Closed' via #curPCA input write."""
    actions = [{'type':'wait','milliseconds':7000}]
    if page_num > 1:
        actions += [
            {'type':'click','selector':'#curPCA'},
            {'type':'wait','milliseconds':500},
            {'type':'press','key':'Backspace'},
            {'type':'press','key':'Backspace'},
            {'type':'press','key':'Backspace'},
            {'type':'write','text':str(page_num),'selector':'#curPCA'},
            {'type':'press','key':'Enter'},
            {'type':'wait','milliseconds':4500},
        ]
    body = {'url':PREVIEW_URL,'formats':['markdown'],'actions':actions,
            'onlyMainContent':False,'timeout':90000}
    r = requests.post('https://api.firecrawl.dev/v1/scrape',
        headers={'Authorization':f'Bearer {FIRECRAWL_KEY}','Content-Type':'application/json'},
        json=body, timeout=120)
    if r.status_code != 200:
        print(f'  ! firecrawl {r.status_code}: {r.text[:200]}')
        return ''
    return r.json().get('data',{}).get('markdown','')

def canonicalize(status_text, sold_to_text):
    s = (status_text or '').lower()
    if 'redeem' in s: return 'REDEEMED'
    if 'cancel' in s: return 'CANCELED'
    if 'postpon' in s: return 'POSTPONED'
    if 'struck' in s: return 'STRUCK_OFF'
    if 'wait' in s or 'pending' in s: return 'LISTED'
    if 'sold' in s:
        st = (sold_to_text or '').lower()
        if 'cert' in st or 'c/h' in st: return 'SOLD_CERT_HOLDER'
        if 'plaintiff' in st: return 'SOLD_PLAINTIFF'
        if '3rd' in st or 'third' in st: return 'SOLD_3RD_PARTY'
        return 'SOLD_3RD_PARTY'
    return 'LISTED'

def extract_cards(md):
    """Markdown parser anchored on each parcel ID. Status block precedes the table for each card."""
    cards = []
    # Only consider region AFTER 'Auctions Closed or Canceled' header
    ac_pos = md.lower().find('auctions closed')
    if ac_pos < 0: ac_pos = 0
    region = md[ac_pos:]

    # Cards are delimited by 'Auction Status' or 'Auction Sold' anchors followed by a details table
    # Find every parcel ID anchor, then walk backward to find that card's status block
    parcel_anchors = list(re.finditer(r'Parcel\s*ID[^\d]*?\[(\d{6,12})\]', region))
    if not parcel_anchors:
        parcel_anchors = list(re.finditer(r'Parcel\s*ID[^\d]+?(\d{6,12})', region))

    for i, pm in enumerate(parcel_anchors):
        # Card starts after previous parcel's table OR after section header
        # Bound: chunk before this parcel match (the status section + table header live here)
        start = parcel_anchors[i-1].end() if i > 0 else 0
        end = parcel_anchors[i+1].start() if i+1 < len(parcel_anchors) else len(region)
        seg = region[start:end]

        c = {'parcel_id_text': pm.group(1)}

        # Status: search for keywords IN THIS SEGMENT only
        # Find what comes immediately after 'Auction Status' or 'Auction Sold' (the closest preceding one)
        status_text = None
        sold_amt = sold_to = sold_ts = None

        # First check if 'Auction Sold' appears BEFORE the parcel id within this segment
        seg_to_parcel = seg[:seg.find(pm.group(1)) if pm.group(1) in seg else len(seg)]
        if re.search(r'Auction\s*Sold', seg_to_parcel, re.IGNORECASE):
            status_text = 'Auction Sold'
            # Sold amount, timestamp, sold-to come right after "Auction Sold"
            sub = seg_to_parcel[seg_to_parcel.lower().rfind('auction sold'):]
            ts_m = re.search(r'(\d{2}/\d{2}/\d{4}\s+\d{1,2}:\d{2}\s*(?:AM|PM)\s*ET)', sub)
            if ts_m: sold_ts = ts_m.group(1)
            amt_m = re.search(r'Amount\s*\n+\s*\$([\d,]+\.\d{2})', sub) or re.search(r'\$([\d,]+\.\d{2})', sub)
            if amt_m: sold_amt = amt_m.group(1)
            # Sold To: check all known categories
            for label in ['3rd Party Bidder','Certificate Holder','Cert Holder','Plaintiff','Tax Deed Applicant','3rd Party']:
                if re.search(re.escape(label), sub, re.IGNORECASE):
                    sold_to = label
                    break
        elif re.search(r'Auction\s*Status\s*\n+\s*Redeemed', seg_to_parcel, re.IGNORECASE):
            status_text = 'Redeemed'
        elif re.search(r'Auction\s*Status\s*\n+\s*Canceled', seg_to_parcel, re.IGNORECASE):
            status_text = 'Canceled'
        elif re.search(r'Auction\s*Status\s*\n+\s*Cancelled', seg_to_parcel, re.IGNORECASE):
            status_text = 'Canceled'
        elif re.search(r'Auction\s*Status\s*\n+\s*Postponed', seg_to_parcel, re.IGNORECASE):
            status_text = 'Postponed'
        elif re.search(r'Auction\s*Status\s*\n+\s*Struck', seg_to_parcel, re.IGNORECASE):
            status_text = 'Struck-Off'
        elif re.search(r'Auction\s*Status\s*\n+\s*Waiting', seg_to_parcel, re.IGNORECASE):
            status_text = 'Waiting'

        # Detail fields (from table rows after parcel id)
        def grab(label):
            m = re.search(label + r':\s*\|\s*([^\|\n]+?)\s*\|', seg, re.IGNORECASE)
            if m:
                val = re.sub(r'\s+', ' ', m.group(1)).strip()
                return val[:200] if val else None
            return None
        c['auction_type_text'] = grab('Auction Type')
        c['case_number_text'] = grab('Case #')
        c['certificate_text'] = grab('Certificate #')
        c['opening_bid_text'] = grab('Opening Bid')
        c['property_address_text'] = grab('Property Address')
        c['assessed_value_text'] = grab('Assessed Value')

        if status_text: c['raw_status_text'] = status_text
        if sold_amt: c['sold_amount_text'] = sold_amt
        if sold_ts: c['sold_timestamp_text'] = sold_ts
        if sold_to: c['sold_to_text'] = sold_to
        c['_canon'] = canonicalize(status_text, sold_to)
        c['raw_card_text'] = re.sub(r'\s+',' ', seg[:1200])
        c['parse_confidence'] = 'high' if c.get('parcel_id_text') and c.get('opening_bid_text') and status_text else 'partial'
        cards.append(c)
    return cards

run_id = rpc('scrape_log_start', {
    'p_source':'brevard_realforeclose','p_county':'brevard',
    'p_sale_type':'tax_deed','p_auction_date':AUCTION_DATE_STR,
    'p_triggered_by':'gha_workflow_dispatch_v9_20_firecrawl_paginated',
})
print(f'>>> v9.20 FIRECRAWL+PAGINATED+MULTI-SOLD-TO run={run_id}')

try:
    seen_parcels = set()
    all_cards = []
    page_stats = []
    canon_counts = {}

    for page_num in range(1, MAX_PAGES + 1):
        print(f'\n--- PAGE {page_num} ---')
        md = firecrawl_page(page_num)
        if not md:
            print('  empty md, stop'); break
        cards = extract_cards(md)
        new = [c for c in cards if c['parcel_id_text'] not in seen_parcels]
        for c in new:
            seen_parcels.add(c['parcel_id_text']); all_cards.append(c)
            canon_counts[c['_canon']] = canon_counts.get(c['_canon'], 0) + 1
        page_stats.append({'page':page_num,'md_chars':len(md),'cards':len(cards),'new':len(new),
                          'first_3':[{'case':c.get('case_number_text'),'parcel':c.get('parcel_id_text'),
                                      'canon':c['_canon'],'sold':c.get('sold_amount_text')} for c in cards[:3]]})
        print(f'  md={len(md)} cards={len(cards)} new={len(new)} total={len(all_cards)}')
        if len(new) == 0 and page_num > 1: break

    print(f'\n=== {len(all_cards)} cards / {len(page_stats)} pages / {canon_counts} ===')

    upserted = 0
    for c in all_cards:
        try:
            c.pop('_canon', None)
            payload = {k:v for k,v in c.items() if v is not None}
            payload.update({'county':'brevard','platform':'realforeclose','run_id':str(run_id)})
            rpc('tier1_card_upsert_rpc', {'p': payload})
            upserted += 1
        except Exception as e:
            if upserted < 3: print(f'  ! {c.get("parcel_id_text")}: {e}')

    summary = {'parser':'v9.20_firecrawl_paginated','pages':len(page_stats),
               'total_cards':len(all_cards),'rows_upserted':upserted,
               'canon_breakdown':canon_counts,'page_stats':page_stats}
    rpc('scrape_log_finish', {'p_run_id':run_id,'p_status':'success',
        'p_rows_in':len(all_cards),'p_rows_inserted':upserted,
        'p_notes':json.dumps(summary)[:6000]})

except Exception as e:
    import traceback
    err = f'{type(e).__name__}: {e}\n{traceback.format_exc()[:1200]}'
    print(f'ERROR: {err}', file=sys.stderr)
    try:
        requests.post(f'{REST}/rpc/scrape_log_finish',
            json={'p_run_id':run_id,'p_status':'failed','p_error':err[:2000]},
            headers=H, timeout=15)
    except: pass
    sys.exit(1)
