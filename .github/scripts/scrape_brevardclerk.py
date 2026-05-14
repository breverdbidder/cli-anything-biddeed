#!/usr/bin/env python3
"""Brevard Tier1 v9.16 - DIRECT BACKEND ENDPOINT integration.
Uses session cookies + /index.cfm?zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD&AREA=C&bypassPage=N
to fetch each of 12 pages directly. NO Firecrawl. NO UI puppeteering."""
import os, re, sys, json, time
from datetime import date
import requests

SUPABASE_URL = os.environ['SUPABASE_URL'].rstrip('/')
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
AUCTION_DATE_STR = os.environ.get('AUCTION_DATE','2026-05-14')
MAX_PAGES = int(os.environ.get('MAX_PAGES','15'))
AUCTION_DATE = date.fromisoformat(AUCTION_DATE_STR)
DATE_SLASH = AUCTION_DATE.strftime('%m/%d/%Y')
BASE = 'https://brevard.realforeclose.com'
PREVIEW_URL = f'{BASE}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={DATE_SLASH}'

REST = f'{SUPABASE_URL}/rest/v1'
H = {'apikey':SUPABASE_KEY,'Authorization':f'Bearer {SUPABASE_KEY}','Content-Type':'application/json','Prefer':'return=representation'}

def rpc(name, params):
    r = requests.post(f'{REST}/rpc/{name}', json=params, headers=H, timeout=60)
    if r.status_code >= 400: raise RuntimeError(f'RPC {name} [{r.status_code}]: {r.text[:400]}')
    return r.json() if r.text and r.text.strip() else None

def sel(table, q=''):
    r = requests.get(f'{REST}/{table}?{q}', headers={'apikey':SUPABASE_KEY,'Authorization':f'Bearer {SUPABASE_KEY}'}, timeout=30)
    r.raise_for_status(); return r.json()

# Browser-like session - critical to look human
sess = requests.Session()
sess.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
})

def parse_card_from_html(html):
    """Each card is a <tr class='Auction_Item'> or contained in AITEM_<id> div with table rows."""
    cards = []
    # Find each AITEM block
    aitem_blocks = re.findall(r'<div[^>]+id=["\']AITEM_(\d+)["\'][^>]*>(.*?)(?=<div[^>]+id=["\']AITEM_|</div>\s*</div>\s*<div\s+class=["\']Bottom_Mark|$)',
                              html, re.DOTALL | re.IGNORECASE)
    for aid, body in aitem_blocks:
        c = {'aid': aid}
        # Auction Type, Case #, Certificate #, Opening Bid, Parcel ID, Property Address, Assessed Value
        for label, field in [
            ('Auction Type','auction_type_text'),
            ('Case #','case_number_text'),
            ('Certificate #','certificate_text'),
            ('Opening Bid','opening_bid_text'),
            ('Parcel ID','parcel_id_text'),
            ('Property Address','property_address_text'),
            ('Assessed Value','assessed_value_text'),
        ]:
            # Capture text in next <td class="AD_DTA"> after the AD_LBL row containing label
            m = re.search(
                re.escape(label) + r'[^<]*</td>\s*<td[^>]*class=["\'][^"\']*AD_DTA[^"\']*["\'][^>]*>(.*?)</td>',
                body, re.DOTALL | re.IGNORECASE)
            if m:
                val = re.sub(r'<[^>]+>','', m.group(1))
                val = re.sub(r'\s+',' ', val).strip()
                if val: c[field] = val[:200]
        # Status & sold info - look for "Auction Status" or "Auction Sold" labels
        status_m = re.search(r'(Auction\s*Status|Auction\s*Sold|Cancel|Wait|Redeem|Struck|Postpone)[^<]*</td[^>]*>\s*(?:<td[^>]*>)?([^<]+)', body, re.IGNORECASE)
        if status_m:
            ctx = status_m.group(0)
            for kw in ['Sold','Redeemed','Cancel','Postpone','Struck','Wait','Listed']:
                if kw.lower() in ctx.lower():
                    c['raw_status_text'] = kw
                    break
        # Sold amount + sold to
        sold_amt = re.search(r'\$([\d,]+\.\d{2})\s*</[^>]+>\s*[^<]*Sold\s*To', body, re.IGNORECASE)
        if sold_amt: c['sold_amount_text'] = sold_amt.group(1)
        sold_to = re.search(r'Sold\s*To\s*</td>\s*<td[^>]*>([^<]+)', body, re.IGNORECASE) or \
                  re.search(r'>(\s*3rd Party Bidder\s*|\s*PLAINTIFF\s*)<', body, re.IGNORECASE)
        if sold_to: c['sold_to_text'] = sold_to.group(1).strip()[:60]
        c['raw_card_text'] = re.sub(r'<[^>]+>',' ', body)[:1500]
        c['parse_confidence'] = 'high' if c.get('parcel_id_text') and c.get('opening_bid_text') else 'partial'
        if c.get('parcel_id_text'): cards.append(c)
    return cards

run_id = rpc('scrape_log_start', {
    'p_source':'brevard_realforeclose','p_county':'brevard',
    'p_sale_type':'tax_deed','p_auction_date':AUCTION_DATE_STR,
    'p_triggered_by':'gha_workflow_dispatch_v9_16_backend',
})
print(f'>>> v9.16 BACKEND ENDPOINT, run={run_id}')

try:
    # Step 1: Establish session by hitting PREVIEW (sets auction date in session)
    print(f'\n[1] Establishing session: {PREVIEW_URL}')
    r = sess.get(PREVIEW_URL, timeout=30)
    print(f'    {r.status_code} {len(r.text):,} bytes, cookies={dict(sess.cookies)}')
    if r.status_code != 200:
        raise RuntimeError(f'Initial PREVIEW failed: {r.status_code} {r.text[:200]}')

    # Step 2: Iterate pages via the AJAX backend endpoint
    all_cards = []
    seen_aids = set()
    page_stats = []
    sess.headers['Referer'] = PREVIEW_URL
    sess.headers['X-Requested-With'] = 'XMLHttpRequest'
    sess.headers['Accept'] = 'application/json, text/javascript, */*; q=0.01'

    for page_num in range(1, MAX_PAGES + 1):
        tx = int(time.time() * 1000)
        load_url = f'{BASE}/index.cfm?zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD&AREA=C&PageDir=0&doR=1&tx={tx}&bypassPage={page_num}'
        print(f'\n[{page_num:>2}] GET {load_url}')
        rr = sess.get(load_url, params={'test':1}, timeout=30)
        print(f'     {rr.status_code} {len(rr.text):,} bytes')
        if rr.status_code != 200:
            print(f'     ! HTTP {rr.status_code}: {rr.text[:200]}')
            break
        # Try JSON parse first
        page_html = ''
        try:
            j = rr.json()
            # Look for HTML payload inside JSON
            for k in ('DATA','data','HTML','html','content','retHTML'):
                if isinstance(j, dict) and k in j:
                    page_html = str(j[k]); break
            if not page_html and isinstance(j, dict):
                # Maybe the entire response is the JSON
                page_html = json.dumps(j)[:30000]
        except Exception:
            page_html = rr.text

        cards = parse_card_from_html(page_html)
        new = [c for c in cards if c['aid'] not in seen_aids]
        for c in new:
            seen_aids.add(c['aid'])
            all_cards.append(c)
        page_stats.append({
            'page':page_num,'bytes':len(rr.text),'cards':len(cards),'new':len(new),
            'first_3_parcels':[c.get('parcel_id_text') for c in cards[:3]],
            'first_3_cases':[c.get('case_number_text') for c in cards[:3]],
        })
        print(f'     extracted={len(cards)} new={len(new)} total={len(all_cards)}')
        if len(new) == 0 and page_num > 1:
            print('     no new parcels, stop pagination')
            break

    print(f'\n=== TOTAL: {len(all_cards)} unique cards across {len(page_stats)} pages ===')

    upserted = 0
    for c in all_cards:
        try:
            payload = {k:v for k,v in c.items() if k != 'aid'}
            payload.update({'county':'brevard','platform':'realforeclose','run_id':str(run_id)})
            rpc('tier1_card_upsert_rpc', {'p': payload})
            upserted += 1
        except Exception as e:
            if upserted < 3: print(f'  ! upsert {c.get("parcel_id_text")}: {e}')

    summary = {
        'parser':'v9.16_backend_endpoint',
        'endpoint':'/index.cfm?zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD&AREA=C&bypassPage=N',
        'pages':len(page_stats),
        'total_cards':len(all_cards),
        'high_conf':sum(1 for c in all_cards if c['parse_confidence']=='high'),
        'rows_upserted':upserted,
        'page_stats':page_stats,
    }
    print(json.dumps(summary, indent=2)[:3000])
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
    except: pass
    sys.exit(1)
