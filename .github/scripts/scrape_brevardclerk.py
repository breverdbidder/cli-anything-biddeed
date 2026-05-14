#!/usr/bin/env python3
"""Brevard Tier1 v9.19 - BACKEND ENDPOINT + per-AITEM clean parser.
Fixes v9.18 bugs:
  - Status now extracted from @AASTAT block within each AITEM segment (not bled from neighbors)
  - Sold amount/timestamp/buyer extracted from same AITEM segment only
  - Adds SOLD_CERT_HOLDER and SOLD_PLAINTIFF categories
  - Canonicalizes status in-scraper, no post-update needed"""
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

def sel(table, q=''):
    r = requests.get(f'{REST}/{table}?{q}', headers={'apikey':SUPABASE_KEY,'Authorization':f'Bearer {SUPABASE_KEY}'}, timeout=30)
    r.raise_for_status(); return r.json()

# --- Status canonicalization map ---
# Tier1 SSOT: status keyword in segment text → canonical bucket
def canonicalize(status_text, sold_to_text):
    if not status_text: return 'LISTED', status_text
    s = status_text.lower()
    if 'redeem' in s: return 'REDEEMED', 'Redeemed'
    if 'cancel' in s: return 'CANCELED', 'Canceled'
    if 'postpon' in s: return 'POSTPONED', 'Postponed'
    if 'struck' in s: return 'STRUCK_OFF', 'Struck-Off'
    if 'wait' in s or 'pending' in s: return 'LISTED', 'Waiting'
    if 'sold' in s or 'sale' in s:
        st = (sold_to_text or '').lower()
        if 'cert' in st or 'c/h' in st: return 'SOLD_CERT_HOLDER', 'Auction Sold'
        if 'plaintiff' in st: return 'SOLD_PLAINTIFF', 'Auction Sold'
        if '3rd' in st or '3 rd' in st or 'third' in st: return 'SOLD_3RD_PARTY', 'Auction Sold'
        return 'SOLD_3RD_PARTY', 'Auction Sold'  # default sold bucket
    return 'LISTED', status_text

def parse_aitem(segment, aid):
    """Parse one AITEM_<aid> segment. Status + sold info isolated to THIS segment's @AASTAT block."""
    c = {'aid': aid}

    # Locate the status block: @AAUCTION_STATS ... up to @AAUCTION_DETAILS (or end of segment)
    stats_match = re.search(r'AUCTION_STATS.*?(?=AUCTION_DETAILS|AUCTION_BIDDING|$)', segment, re.DOTALL)
    stats_block = stats_match.group(0) if stats_match else segment[:1500]

    # --- Detect status keyword in stats block ---
    # Patterns to look for in priority order
    status_text = None
    if re.search(r'Auction\s*Sold', stats_block, re.IGNORECASE): status_text = 'Auction Sold'
    elif re.search(r'\bRedeemed\b', stats_block, re.IGNORECASE): status_text = 'Redeemed'
    elif re.search(r'\bCancel(?:ed|led)\b', stats_block, re.IGNORECASE): status_text = 'Canceled'
    elif re.search(r'\bPostponed\b', stats_block, re.IGNORECASE): status_text = 'Postponed'
    elif re.search(r'\bStruck\b', stats_block, re.IGNORECASE): status_text = 'Struck-Off'
    elif re.search(r'\bWaiting\b', stats_block, re.IGNORECASE): status_text = 'Waiting'

    # --- If sold: extract amount + timestamp + sold_to from SAME stats block ---
    sold_amt = sold_to = sold_ts = None
    if status_text == 'Auction Sold':
        amt_m = re.search(r'\$([\d,]+\.\d{2})', stats_block)
        if amt_m: sold_amt = amt_m.group(1)
        ts_m = re.search(r'(\d{2}/\d{2}/\d{4}\s+\d{1,2}:\d{2}\s*(?:AM|PM)\s*ET)', stats_block, re.IGNORECASE)
        if ts_m: sold_ts = ts_m.group(1)
        # Sold-to: search for category keyword in stats block
        for label in ['3rd Party Bidder','3rd Party','Certificate Holder','Cert Holder','Plaintiff','Tax Deed Applicant']:
            if re.search(re.escape(label), stats_block, re.IGNORECASE):
                sold_to = label
                break

    canon, normalized_status = canonicalize(status_text, sold_to)

    # --- Detail fields from token-compressed table rows ---
    def grab(label):
        m = re.search(
            re.escape(label) + r':\s*@F[^@]*?@CAD_DTA[^>]*>(.*?)(?:@G|<)',
            segment, re.IGNORECASE | re.DOTALL)
        if not m:
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

    # Parcel from PropertySearch link
    pm = re.search(r'/parcel/(\d{6,12})', segment)
    if pm: c['parcel_id_text'] = pm.group(1)

    if status_text: c['raw_status_text'] = normalized_status
    if sold_amt:
        c['sold_amount_text'] = sold_amt
    if sold_to: c['sold_to_text'] = sold_to
    if sold_ts: c['sold_timestamp_text'] = sold_ts

    c['_canon'] = canon
    c['raw_card_text'] = re.sub(r'\s+',' ', segment[:1200])
    c['parse_confidence'] = 'high' if c.get('parcel_id_text') and c.get('opening_bid_text') and status_text else 'partial'
    return c

run_id = rpc('scrape_log_start', {
    'p_source':'brevard_realforeclose','p_county':'brevard',
    'p_sale_type':'tax_deed','p_auction_date':AUCTION_DATE_STR,
    'p_triggered_by':'gha_workflow_dispatch_v9_19_clean',
})
print(f'>>> v9.19 CLEAN PER-AITEM, run={run_id}')

try:
    sess = requests.Session()
    sess.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0',
        'Accept': 'text/html,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    })

    r0 = sess.get(PREVIEW_URL, timeout=30)
    if r0.status_code != 200: raise RuntimeError(f'PREVIEW failed: {r0.status_code}')
    print(f'PREVIEW: {r0.status_code} session={list(sess.cookies.keys())}')

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
        try: j = rr.json()
        except Exception:
            m = re.search(r'\{"retHTML":.*\}', rr.text, re.DOTALL)
            if not m: print(f'[{page_num:>2}] no JSON, stop'); break
            j = json.loads(m.group(0))

        retHTML = j.get('retHTML','') or ''
        rlist_str = j.get('rlist','') or ''
        aids = [a.strip() for a in rlist_str.split(',') if a.strip()]

        cards_this_page = []
        for aid in aids:
            si = retHTML.find(f'AITEM_{aid}')
            if si < 0: continue
            after = retHTML[si + len(f'AITEM_{aid}'):]
            nm = re.search(r'AITEM_\d+', after)
            ei = (si + len(f'AITEM_{aid}') + nm.start()) if nm else len(retHTML)
            segment = retHTML[si:ei]
            card = parse_aitem(segment, aid)
            if card.get('parcel_id_text'):
                cards_this_page.append(card)

        new = [c for c in cards_this_page if c['aid'] not in seen_aids]
        for c in new:
            seen_aids.add(c['aid']); all_cards.append(c)

        page_stats.append({
            'page':page_num,'rlist_count':len(aids),'parsed':len(cards_this_page),'new':len(new),
            'samples':[{'case':c.get('case_number_text'),'parcel':c.get('parcel_id_text'),
                        'canon':c['_canon'],'sold':c.get('sold_amount_text'),
                        'sold_to':c.get('sold_to_text')} for c in cards_this_page[:3]],
        })
        print(f'[{page_num:>2}] rlist={len(aids)} parsed={len(cards_this_page)} new={len(new)}')
        if len(new) == 0 and page_num > 1: break

    print(f'\n=== TOTAL: {len(all_cards)} cards across {len(page_stats)} pages ===')

    # Pre-canonicalize before upsert so view picks up correct status
    upserted = 0
    canon_counts = {}
    for c in all_cards:
        canon = c.pop('_canon', 'LISTED')
        canon_counts[canon] = canon_counts.get(canon, 0) + 1
        try:
            payload = {k:v for k,v in c.items() if k != 'aid' and v is not None}
            payload.update({'county':'brevard','platform':'realforeclose','run_id':str(run_id)})
            rpc('tier1_card_upsert_rpc', {'p': payload})
            upserted += 1
        except Exception as e:
            if upserted < 3: print(f'  ! upsert {c.get("parcel_id_text")}: {e}')

    summary = {
        'parser':'v9.19_clean_per_aitem',
        'pages':len(page_stats),
        'total_cards':len(all_cards),
        'high_conf':sum(1 for c in all_cards if c.get('parse_confidence')=='high'),
        'rows_upserted':upserted,
        'canon_breakdown':canon_counts,
        'page_stats':page_stats,
    }
    rpc('scrape_log_finish', {
        'p_run_id':run_id,'p_status':'success',
        'p_rows_in':len(all_cards),'p_rows_inserted':upserted,
        'p_notes':json.dumps(summary)[:6000],
    })
    print(f'DONE: {upserted} rows, breakdown: {canon_counts}')

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
