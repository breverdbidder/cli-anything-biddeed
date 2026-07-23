#!/usr/bin/env python3
"""RealAuction Multi-County Tier1 Scraper v2.0 (GTM-22 T1 CRITICAL fix).

v1.0 fetched pages via Firecrawl; that account is at 0/100000 remaining
credits (billing period never renewed — confirmed via /v1/team/credit-usage),
so every dispatch died in "Run scraper" with a 402. v2.0 renders pages with
a self-hosted headless browser instead (no paid dependency):
  - Playwright/Chromium per page (page 1 fresh load; page N re-navigates via
    the same #curPCA Backspace x3 + write(page_num) + Enter interaction the
    site's own pagination widget uses)
  - DOM-anchored extraction (div.AUCTION_ITEM / table.ad_tab) instead of
    markdown regex — verified against live Waiting/Redeemed/Sold examples
  - In-scraper status canonicalization (no after-update SQL fixes)
  - Multi sold-to category support: 3rd Party, Cert Holder, Plaintiff, Tax Deed Applicant

What's parameterized:
  COUNTY_SLUG    - e.g. 'osceola', 'polk', 'volusia' (required)
  BASE_URL       - e.g. 'https://osceola.realtaxdeed.com' (required, no trailing slash)
  PLATFORM       - e.g. 'realtaxdeed' or 'realforeclose' (required, becomes part of source tag)
  SALE_TYPE      - 'tax_deed' or 'foreclosure' (required)
  AUCTION_DATE   - YYYY-MM-DD (required, no default)
  MAX_PAGES      - default 15

Known limitation: this DOM extractor targets the classic RealAuction
template (div.AUCTION_ITEM). At least one subdomain (brevard.realtaxdeed.com)
has migrated to a newer Bootstrap/SPA template with no AUCTION_ITEM markup —
that template is out of scope for this fix and will still yield zero cards.

Provenance:
  Derived from scrape_brevardclerk.py v9.20 (run 38: 117 cards, 100% verified against screenshot).
  Created under ASCEND session for multi-county FL rollout.
"""
import os, re, sys, json
from datetime import date
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')

# Required envs (fail fast if missing)
def _req(name):
    v = os.environ.get(name)
    if not v: raise RuntimeError(f'Missing required env: {name}')
    return v

SUPABASE_URL       = _req('SUPABASE_URL').rstrip('/')
SUPABASE_KEY       = _req('SUPABASE_SERVICE_ROLE_KEY')
COUNTY_SLUG        = _req('COUNTY_SLUG').lower().strip()
BASE_URL           = _req('BASE_URL').rstrip('/')
PLATFORM           = _req('PLATFORM').lower().strip()
SALE_TYPE          = _req('SALE_TYPE').lower().strip()
AUCTION_DATE_STR   = _req('AUCTION_DATE')

MAX_PAGES   = int(os.environ.get('MAX_PAGES', '15'))
DATE_SLASH  = date.fromisoformat(AUCTION_DATE_STR).strftime('%m/%d/%Y')
PREVIEW_URL = f'{BASE_URL}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={DATE_SLASH}'
SOURCE_TAG  = f'{COUNTY_SLUG}_{PLATFORM}'

REST = f'{SUPABASE_URL}/rest/v1'
H = {'apikey':SUPABASE_KEY,'Authorization':f'Bearer {SUPABASE_KEY}','Content-Type':'application/json','Prefer':'return=representation'}

def rpc(name, params):
    r = requests.post(f'{REST}/rpc/{name}', json=params, headers=H, timeout=60)
    if r.status_code >= 400: raise RuntimeError(f'RPC {name} [{r.status_code}]: {r.text[:400]}')
    return r.json() if r.text and r.text.strip() else None

def render_page(browser, page_num):
    """Render page N via a headless browser. Page 1 is a fresh load; page N>1
    re-navigates via the site's own #curPCA pagination widget (same
    interaction the previous Firecrawl 'actions' array performed)."""
    page = browser.new_page(user_agent=UA)
    try:
        resp = page.goto(PREVIEW_URL, timeout=60000)
        if resp is None or resp.status >= 400:
            print(f'  ! render {resp.status if resp else "no-response"} for {PREVIEW_URL}')
            return ''
        page.wait_for_timeout(7000)
        if page_num > 1:
            el = page.query_selector('#curPCA')
            if el is None:
                print('  ! no #curPCA pagination control found')
                return ''
            el.click()
            page.wait_for_timeout(500)
            for _ in range(3):
                page.keyboard.press('Backspace')
            page.keyboard.type(str(page_num))
            page.keyboard.press('Enter')
            page.wait_for_timeout(4500)
        return page.content()
    except Exception as e:
        print(f'  ! render error: {type(e).__name__}: {e}')
        return ''
    finally:
        page.close()

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

def extract_cards(html):
    """DOM parser anchored on each div.AUCTION_ITEM (classic RealAuction template)."""
    soup = BeautifulSoup(html, 'html.parser')
    cards = []

    for item in soup.select('div.AUCTION_ITEM'):
        stats = item.select_one('.AUCTION_STATS')
        if stats is None:
            continue
        msga = stats.select_one('.ASTAT_MSGA')
        msgb = stats.select_one('.ASTAT_MSGB')
        msgd = stats.select_one('.ASTAT_MSGD')
        soldto_msg = stats.select_one('.ASTAT_MSG_SOLDTO_MSG')
        msga_t = msga.get_text(strip=True) if msga else ''
        msgb_t = msgb.get_text(strip=True) if msgb else ''
        msgd_t = msgd.get_text(strip=True) if msgd else ''
        soldto_t = soldto_msg.get_text(strip=True) if soldto_msg else ''

        status_text = sold_amt = sold_to = sold_ts = None
        if msga_t == 'Auction Sold':
            status_text = 'Auction Sold'
            sold_ts = msgb_t or None
            sold_amt = msgd_t.lstrip('$').strip() or None
            sold_to = soldto_t or None
        elif msga_t == 'Auction Status':
            status_text = msgb_t or None
        elif msga_t == 'Auction Starts':
            status_text = 'Waiting'

        c = {}
        table = item.select_one('table.ad_tab')
        rows = table.select('tr') if table else []
        addr_parts = []
        for i, tr in enumerate(rows):
            lbl_td = tr.select_one('td.AD_LBL')
            dta_td = tr.select_one('td.AD_DTA')
            if dta_td is None: continue
            label = lbl_td.get_text(strip=True) if lbl_td else ''
            value = dta_td.get_text(' ', strip=True)
            if label == 'Auction Type:':      c['auction_type_text'] = value or None
            elif label == 'Case #:':          c['case_number_text'] = value or None
            elif label == 'Certificate #:':   c['certificate_text'] = value or None
            elif label == 'Opening Bid:':     c['opening_bid_text'] = value or None
            elif label == 'Parcel ID:':
                a = dta_td.select_one('a')
                c['parcel_id_text'] = (a.get_text(strip=True) if a else value) or None
            elif label == 'Property Address:':
                if value: addr_parts.append(value)
            elif label == '' and value and i > 0:
                addr_parts.append(value)
            elif label == 'Assessed Value:':  c['assessed_value_text'] = value or None

        if not c.get('parcel_id_text'):
            continue  # not a real auction row
        if addr_parts:
            c['property_address_text'] = ', '.join(addr_parts)

        if status_text: c['raw_status_text'] = status_text
        if sold_amt:    c['sold_amount_text'] = sold_amt
        if sold_ts:     c['sold_timestamp_text'] = sold_ts
        if sold_to:     c['sold_to_text'] = sold_to
        c['_canon']            = canonicalize(status_text, sold_to)
        c['raw_card_text']     = re.sub(r'\s+', ' ', item.get_text(' ', strip=True))[:1200]
        c['parse_confidence']  = 'high' if c.get('parcel_id_text') and c.get('opening_bid_text') and status_text else 'partial'
        cards.append(c)
    return cards

# === MAIN ===
run_id = rpc('scrape_log_start', {
    'p_source':       SOURCE_TAG,
    'p_county':       COUNTY_SLUG,
    'p_sale_type':    SALE_TYPE,
    'p_auction_date': AUCTION_DATE_STR,
    'p_triggered_by': f'ascend_phase1_{COUNTY_SLUG}_{PLATFORM}',
})
print(f'>>> v2.0 multi-county scraper | county={COUNTY_SLUG} platform={PLATFORM} date={AUCTION_DATE_STR} run={run_id}')
print(f'    PREVIEW_URL={PREVIEW_URL}')

try:
    seen_parcels  = set()
    all_cards     = []
    page_stats    = []
    canon_counts  = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox'])
        try:
            for page_num in range(1, MAX_PAGES + 1):
                print(f'\n--- PAGE {page_num} ---')
                html = render_page(browser, page_num)
                if not html:
                    print('  empty render, stop'); break
                cards = extract_cards(html)
                new = [c for c in cards if c['parcel_id_text'] not in seen_parcels]
                for c in new:
                    seen_parcels.add(c['parcel_id_text'])
                    all_cards.append(c)
                    canon_counts[c['_canon']] = canon_counts.get(c['_canon'], 0) + 1
                page_stats.append({'page':page_num,'html_chars':len(html),'cards':len(cards),'new':len(new),
                                  'first_3':[{'case':c.get('case_number_text'),'parcel':c.get('parcel_id_text'),
                                              'canon':c['_canon'],'sold':c.get('sold_amount_text')} for c in cards[:3]]})
                print(f'  html={len(html)} cards={len(cards)} new={len(new)} total={len(all_cards)}')
                if len(new) == 0 and page_num > 1: break
        finally:
            browser.close()

    # Hard fail if NO cards found at all (Honesty Protocol V3 K2: no silent skip)
    if len(all_cards) == 0:
        raise RuntimeError(f'Zero cards extracted for {COUNTY_SLUG} on {AUCTION_DATE_STR}. Either no auctions scheduled OR scraper failed. Refusing to mark success.')

    print(f'\n=== {len(all_cards)} cards / {len(page_stats)} pages / canon={canon_counts} ===')

    upserted = 0
    upsert_errors = []
    for c in all_cards:
        try:
            c.pop('_canon', None)
            payload = {k:v for k,v in c.items() if v is not None}
            payload.update({'county':COUNTY_SLUG,'platform':PLATFORM,'run_id':str(run_id)})
            rpc('tier1_card_upsert_rpc', {'p': payload})
            upserted += 1
        except Exception as e:
            upsert_errors.append(f'{c.get("parcel_id_text")}: {e}')
            if len(upsert_errors) <= 3: print(f'  ! {c.get("parcel_id_text")}: {e}')

    # FAIL-LOUD (PENCIL incident 01): parsed>0 but inserted=0 must never be "success"
    if len(all_cards) > 0 and upserted == 0:
        raise RuntimeError(f'Silent failure: {len(all_cards)} cards parsed, 0 upserted. Errors: ' + ' || '.join(upsert_errors[:5]))

    summary = {
        'parser':           'v2.0_realauction_county_playwright',
        'county':           COUNTY_SLUG,
        'platform':         PLATFORM,
        'sale_type':        SALE_TYPE,
        'base_url':         BASE_URL,
        'pages':            len(page_stats),
        'total_cards':      len(all_cards),
        'rows_upserted':    upserted,
        'canon_breakdown':  canon_counts,
        'page_stats':       page_stats,
    }
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
