#!/usr/bin/env python3
"""Brevard Tier1 v9.18 - BACKEND ENDPOINT + token-aware parser.
Hits /index.cfm?zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD&AREA=C&bypassPage=N directly.
Response is JSON: {retHTML: '...token-compressed HTML...', rlist: 'aid1,aid2,...'}"""
import os, re, sys, json, time
from datetime import date
import requests

SUPABASE_URL = os.environ['SUPABASE_URL'].rstrip('/')
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
AUCTION_DATE_STR = os.environ.get('AUCTION_DATE','2026-05-14')
MAX_PAGES = int(os.environ.get('MAX_PAGES','15'))
DATE_SLASH = date.fromisoformat(AUCTION_DATE_STR).strftime('%m/%d/%Y')
BASE = 'https://brevard.realforeclose.com'
PREVIEW_URL = f'{BASE}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={DATE_SLASH}'

REST = f'{SUPABASE_URL}/rest/v1'
H = {'apikey':SUPABASE_KEY,'Authorization':f'Bearer {SUPABASE_KEY}','Content-Type':'application/json','Prefer':'return=representation'}

def rpc(name, params):
    r = requests.post(f'{REST}/rpc/{name}', json=params, headers=H, timeout=60)
    if r.status_code >= 400: raise RuntimeError(f'RPC {name} [{r.status_code}]: {r.text[:400]}')
    return r.json() if r.text and r.text.strip() else None

# Token expansion: RealAuction compresses retHTML to save bytes
# Decoded by inspecting client-side LoadNewArea() and visible patterns
def expand_tokens(html):
    # Order matters - longer tokens first
    replacements = [
        ('@CAD_LBL', 'class="AD_LBL"'),
        ('@CAD_DTA', 'class="AD_DTA"'),
        ('@CAD_TXT', 'class="AD_TXT"'),
        ('@AASTAT_MSGA', '<div class="ASTAT_MSGA"'),
        ('@AASTAT_MSGB', '<div class="ASTAT_MSGB"'),
        ('@AASTAT_MSGC', '<div class="ASTAT_MSGC"'),
        ('@AASTAT_MSGD', '<div class="ASTAT_MSGD"'),
        ('@AASTAT_MSGE', '<div class="ASTAT_MSGE"'),
        ('@AASTAT', '<div class="ASTAT'),
        ('@E_ITEM_SPACER', 'class="AUCTION_ITEM_SPACER'),
        ('@E_ITEM', 'class="AUCTION_ITEM'),
        ('@E_STATS', 'class="AUCTION_STATS'),
        ('@E_DETAILS', 'class="AUCTION_DETAILS'),
        ('@E_BIDDING', 'class="AUCTION_BIDDING'),
        ('@A', '<div '),
        ('@B', '</div>'),
        ('@C', 'class='),
        ('@H', '<tr><td '),
        ('@F', '</td><td '),
        ('@G', '</td></tr>'),
        ('@I', 'table'),
    ]
    for tok, rep in replacements:
        html = html.replace(tok, rep)
    return html

def parse_aitem(segment, aid):
    """Parse one auction item segment (raw, with tokens). Returns card dict."""
    c = {'aid': aid}

    # Find labeled fields. Tokens @F separates td cells; @G ends row.
    # Pattern: LABEL:@F[anything but @]*?@CAD_DTA"...>VALUE@G  OR  LABEL:@F...>VALUE@G
    def grab(label):
        m = re.search(
            re.escape(label) + r':\s*@F[^@]*?@CAD_DTA[^>]*>(.*?)(?:@G|<)',
            segment, re.IGNORECASE | re.DOTALL)
        if not m:
            # Alternate without @CAD_DTA token
            m = re.search(re.escape(label) + r':\s*@F[^>]*>([^@<]+?)\s*@G',
                          segment, re.IGNORECASE | re.DOTALL)
        if m:
            val = re.sub(r'<[^>]+>', ' ', m.group(1))
            val = re.sub(r'\s+', ' ', val).strip()
            return val[:200] if val else None
        return None

    c['auction_type_text'] = grab('Auction Type')
    c['case_number_text'] = grab('Case #')
    c['certificate_text'] = grab('Certificate #')
    c['opening_bid_text'] = grab('Opening Bid')
    c['property_address_text'] = grab('Property Address')
    c['assessed_value_text'] = grab('Assessed Value')

    # Parcel ID is inside a <a href=".../parcel/XXXXX">XXXXX</a>
    pm = re.search(r'/parcel/(\d{6,12})', segment)
    if pm: c['parcel_id_text'] = pm.group(1)

    # Status from ASTAT_MSGA block - usually contains the status word
    # Look for the status text near the top of the segment
    head = segment[:1800]
    status_keywords = [
        ('Auction Sold', 'Sold'),
        ('Redeemed', 'Redeemed'),
        ('Canceled', 'Canceled'),
        ('Cancelled', 'Canceled'),
        ('Postponed', 'Postponed'),
        ('Struck', 'Struck-Off'),
        ('Waiting', 'Waiting'),
    ]
    for label, canon in status_keywords:
        if re.search(r'\b' + label + r'\b', head, re.IGNORECASE):
            c['raw_status_text'] = label
            break

    # Sold amount + sold to (when status is Sold)
    if c.get('raw_status_text') == 'Auction Sold':
        amt = re.search(r'Amount[^$]*\$([\d,]+\.\d{2})', head, re.IGNORECASE | re.DOTALL)
        if amt: c['sold_amount_text'] = amt.group(1)
        ts = re.search(r'(\d{2}/\d{2}/\d{4}\s+\d{1,2}:\d{2}\s*(?:AM|PM)\s*ET)', head, re.IGNORECASE)
        if ts: c['sold_timestamp_text'] = ts.group(1)
        sto = re.search(r'Sold\s*To[^@<]*(3rd\s*Party\s*Bidder|PLAINTIFF|[A-Z][A-Za-z0-9 ]{3,40})', head, re.IGNORECASE)
        if sto: c['sold_to_text'] = sto.group(1).strip()[:60]

    # Save a snippet for debugging
    c['raw_card_text'] = re.sub(r'\s+',' ', segment[:1200])
    c['parse_confidence'] = 'high' if c.get('parcel_id_text') and c.get('opening_bid_text') else 'partial'
    return c

run_id = rpc('scrape_log_start', {
    'p_source':'brevard_realforeclose','p_county':'brevard',
    'p_sale_type':'tax_deed','p_auction_date':AUCTION_DATE_STR,
    'p_triggered_by':'gha_workflow_dispatch_v9_18_backend',
})
print(f'>>> v9.18 BACKEND+TOKEN-AWARE, run={run_id}')

try:
    sess = requests.Session()
    sess.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0',
        'Accept': 'text/html,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    })

    # Establish session
    r0 = sess.get(PREVIEW_URL, timeout=30)
    print(f'PREVIEW: {r0.status_code} {len(r0.text):,}b session_cookies={list(sess.cookies.keys())}')
    if r0.status_code != 200:
        raise RuntimeError(f'PREVIEW failed: {r0.status_code}')

    sess.headers['Referer'] = PREVIEW_URL
    sess.headers['X-Requested-With'] = 'XMLHttpRequest'
    sess.headers['Accept'] = 'application/json, text/javascript, */*; q=0.01'

    all_cards = []
    seen_aids = set()
    page_stats = []

    for page_num in range(1, MAX_PAGES + 1):
        tx = int(time.time() * 1000)
        url = f'{BASE}/index.cfm?zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD&AREA=C&PageDir=0&doR=1&tx={tx}&bypassPage={page_num}'
        rr = sess.get(url, params={'test':1}, timeout=30)
        if rr.status_code != 200:
            print(f'[{page_num:>2}] HTTP {rr.status_code}, stop'); break
        try:
            j = rr.json()
        except Exception:
            # Sometimes returns JSON-in-JSON or wrapped in noise; locate {"retHTML"
            m = re.search(r'\{"retHTML":.*\}', rr.text, re.DOTALL)
            if not m:
                print(f'[{page_num:>2}] no JSON, stop'); break
            j = json.loads(m.group(0))

        retHTML = j.get('retHTML','') or ''
        rlist_str = j.get('rlist','') or ''
        aids = [a.strip() for a in rlist_str.split(',') if a.strip()]

        # Split retHTML by AITEM_<aid> markers, preserving each segment with its AID
        cards_this_page = []
        for i, aid in enumerate(aids):
            start_marker = f'AITEM_{aid}'
            si = retHTML.find(start_marker)
            if si < 0: continue
            # End at next AITEM_ or end of retHTML
            next_marker = re.search(r'AITEM_\d+', retHTML[si + len(start_marker):])
            ei = (si + len(start_marker) + next_marker.start()) if next_marker else len(retHTML)
            segment = retHTML[si:ei]
            card = parse_aitem(segment, aid)
            if card.get('parcel_id_text'):
                cards_this_page.append(card)

        new = [c for c in cards_this_page if c['aid'] not in seen_aids]
        for c in new:
            seen_aids.add(c['aid'])
            all_cards.append(c)

        page_stats.append({
            'page':page_num,'rlist_count':len(aids),'parsed':len(cards_this_page),'new':len(new),
            'sample':[{'parcel':c.get('parcel_id_text'),'case':c.get('case_number_text'),
                       'status':c.get('raw_status_text'),'open':c.get('opening_bid_text'),
                       'sold':c.get('sold_amount_text')} for c in cards_this_page[:3]],
        })
        print(f'[{page_num:>2}] rlist={len(aids)} parsed={len(cards_this_page)} new={len(new)} total={len(all_cards)}')
        if len(new) == 0 and page_num > 1:
            print('  no new, stop'); break

    print(f'\n=== TOTAL: {len(all_cards)} unique cards across {len(page_stats)} pages ===')

    upserted = 0
    for c in all_cards:
        try:
            payload = {k:v for k,v in c.items() if k != 'aid' and v is not None}
            payload.update({'county':'brevard','platform':'realforeclose','run_id':str(run_id)})
            rpc('tier1_card_upsert_rpc', {'p': payload})
            upserted += 1
        except Exception as e:
            if upserted < 3: print(f'  ! upsert parcel={c.get("parcel_id_text")}: {e}')

    summary = {
        'parser':'v9.18_backend_token_aware',
        'endpoint':'/index.cfm?zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD&AREA=C&bypassPage=N',
        'pages':len(page_stats),
        'total_cards':len(all_cards),
        'high_conf':sum(1 for c in all_cards if c['parse_confidence']=='high'),
        'rows_upserted':upserted,
        'page_stats':page_stats,
    }
    rpc('scrape_log_finish', {
        'p_run_id':run_id,'p_status':'success',
        'p_rows_in':len(all_cards),'p_rows_inserted':upserted,
        'p_notes':json.dumps(summary)[:6000],
    })
    print(f'DONE: {upserted} rows upserted')

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
