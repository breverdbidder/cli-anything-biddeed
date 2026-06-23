#!/usr/bin/env python3
"""
calendar_sweep_mca.py — BIDDEED 67-County Calendar Sweep v1.0

Phase A: Scrape CALENDAR page → discover future auction dates
Phase B: Scrape PREVIEW page per date → extract upcoming listings
Phase C: Upsert directly into multi_county_auctions

Env (required): COUNTY_SLUG, BASE_URL, PLATFORM, SALE_TYPE,
                SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, FIRECRAWL_API_KEY

Exit codes:
  0 = success (≥1 row upserted)
  1 = fatal error (Firecrawl failure, Supabase error)
  2 = county genuinely dark (zero future dates on calendar, or zero listings found)
      — non-fatal for GHA (continue-on-error: true)
"""
import os, re, sys, json, time
from datetime import date, datetime
import requests


# ── ENV ──────────────────────────────────────────────────────────────────────

def _req(name):
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f'Missing required env: {name}')
    return v

COUNTY    = _req('COUNTY_SLUG').lower().strip()
BASE_URL  = _req('BASE_URL').rstrip('/')
PLATFORM  = _req('PLATFORM').lower().strip()
SALE_TYPE = _req('SALE_TYPE').lower().strip()
SUPA_URL  = _req('SUPABASE_URL').rstrip('/')
SUPA_KEY  = _req('SUPABASE_SERVICE_ROLE_KEY')
FC_KEY    = _req('FIRECRAWL_API_KEY')

TODAY = date.today()
REST  = f'{SUPA_URL}/rest/v1'
SUPA_H = {
    'apikey': SUPA_KEY,
    'Authorization': f'Bearer {SUPA_KEY}',
    'Content-Type': 'application/json',
}
FC_H = {'Authorization': f'Bearer {FC_KEY}', 'Content-Type': 'application/json'}

print(f'>>> calendar_sweep_mca v1.0 | {COUNTY} ({SALE_TYPE}) | {PLATFORM} | today={TODAY}')
print(f'    BASE_URL={BASE_URL}')


# ── FIRECRAWL ─────────────────────────────────────────────────────────────────

def firecrawl(url, actions, timeout_ms=120000):
    body = {
        'url': url,
        'formats': ['markdown', 'html'],
        'actions': actions,
        'onlyMainContent': False,
        'timeout': timeout_ms,
    }
    try:
        r = requests.post(
            'https://api.firecrawl.dev/v1/scrape',
            headers=FC_H, json=body, timeout=150,
        )
    except requests.RequestException as e:
        print(f'  ! firecrawl request error: {e}', file=sys.stderr)
        return '', '', str(e)
    if r.status_code != 200:
        print(f'  ! firecrawl {r.status_code}: {r.text[:300]}', file=sys.stderr)
        return '', '', f'http_{r.status_code}'
    data = r.json().get('data', {})
    return data.get('markdown', ''), data.get('html', ''), None


# ── PHASE A: CALENDAR → FUTURE DATES ─────────────────────────────────────────

CALENDAR_ACTIONS = [
    {'type': 'wait', 'milliseconds': 15000},
    {'type': 'scroll', 'direction': 'down'},
    {'type': 'wait', 'milliseconds': 3000},
    {'type': 'scroll', 'direction': 'down'},
    {'type': 'wait', 'milliseconds': 2000},
]

def scrape_calendar():
    """Probe both CALENDAR endpoints; return sorted list of future dates."""
    urls = [
        f'{BASE_URL}/index.cfm?zaction=USER&zmethod=CALENDAR',
        f'{BASE_URL}/index.cfm?zaction=AUCTION&Zmethod=CALENDAR',
    ]
    best_md, best_html = '', ''
    for url in urls:
        print(f'  [calendar] {url}')
        md, html, err = firecrawl(url, CALENDAR_ACTIONS)
        if err:
            print(f'    skipped: {err}')
            time.sleep(2)
            continue
        print(f'    md={len(md)} html={len(html)}')
        if len(md) + len(html) > len(best_md) + len(best_html):
            best_md, best_html = md, html
        time.sleep(2)

    if not best_md and not best_html:
        return [], 'All calendar fetches returned empty'

    combined = best_md + '\n\n' + best_html
    raw_dates: set[date] = set()

    # MM/DD/YYYY
    for m in re.finditer(r'(\d{2})/(\d{2})/(\d{4})', combined):
        try:
            d = date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
            if 2024 <= d.year <= 2030:
                raw_dates.add(d)
        except (ValueError, OverflowError):
            pass

    # YYYY-MM-DD
    for m in re.finditer(r'(\d{4})-(\d{2})-(\d{2})', combined):
        try:
            d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if 2024 <= d.year <= 2030:
                raw_dates.add(d)
        except (ValueError, OverflowError):
            pass

    # AUCTIONDATE=MM/DD/YYYY
    for m in re.finditer(r'AUCTIONDATE=([\d/]+)', combined, re.IGNORECASE):
        try:
            d = datetime.strptime(m.group(1), '%m/%d/%Y').date()
            if 2024 <= d.year <= 2030:
                raw_dates.add(d)
        except ValueError:
            pass

    future = sorted(d for d in raw_dates if d >= TODAY)
    print(f'  [calendar] raw={len(raw_dates)} total dates; future={len(future)}: {future[:7]}')
    return future, None


# ── PHASE B: PREVIEW → UPCOMING LISTINGS ─────────────────────────────────────

PREVIEW_P1_ACTIONS = [
    {'type': 'wait', 'milliseconds': 8000},
    {'type': 'scroll', 'direction': 'down'},
    {'type': 'wait', 'milliseconds': 2000},
]

def paginate_actions(page_num):
    return [
        {'type': 'wait', 'milliseconds': 7000},
        {'type': 'click', 'selector': '#curPCA'},
        {'type': 'wait', 'milliseconds': 500},
        {'type': 'press', 'key': 'Backspace'},
        {'type': 'press', 'key': 'Backspace'},
        {'type': 'press', 'key': 'Backspace'},
        {'type': 'write', 'text': str(page_num), 'selector': '#curPCA'},
        {'type': 'press', 'key': 'Enter'},
        {'type': 'wait', 'milliseconds': 4500},
    ]


def canonicalize(status_text, sold_to_text=''):
    s = (status_text or '').lower()
    if 'redeem' in s:                  return 'REDEEMED'
    if 'cancel' in s:                  return 'CANCELED'
    if 'postpon' in s:                 return 'POSTPONED'
    if 'struck' in s:                  return 'STRUCK_OFF'
    if 'wait' in s or 'pending' in s:  return 'LISTED'
    if 'sold' in s:
        st = (sold_to_text or '').lower()
        if 'cert' in st or 'c/h' in st:   return 'SOLD_CERT_HOLDER'
        if 'plaintiff' in st:              return 'SOLD_PLAINTIFF'
        return 'SOLD_3RD_PARTY'
    return 'LISTED'


def extract_cards(md):
    """Parse auction cards. Works for both upcoming (Waiting) and closed auctions."""
    cards = []

    # Anchor on 'Upcoming' section if present, else full page
    up_pos = md.lower().find('upcoming auctions')
    ac_pos = md.lower().find('auctions closed')
    if up_pos >= 0:
        region = md[up_pos:]
    elif ac_pos >= 0:
        region = md[ac_pos:]
    else:
        region = md  # scan full page

    parcel_anchors = list(re.finditer(r'Parcel\s*ID[^\d]*?\[(\d{6,12})\]', region))
    if not parcel_anchors:
        parcel_anchors = list(re.finditer(r'Parcel\s*ID[^\d]+?(\d{6,12})', region))

    for i, pm in enumerate(parcel_anchors):
        start = parcel_anchors[i - 1].end() if i > 0 else 0
        end   = parcel_anchors[i + 1].start() if i + 1 < len(parcel_anchors) else len(region)
        seg   = region[start:end]

        status_text = None
        sold_amt = sold_to = sold_ts = None

        seg_to_parcel = seg[:seg.find(pm.group(1)) if pm.group(1) in seg else len(seg)]
        if re.search(r'Auction\s*Sold', seg_to_parcel, re.IGNORECASE):
            status_text = 'Auction Sold'
            sub = seg_to_parcel[seg_to_parcel.lower().rfind('auction sold'):]
            ts_m = re.search(r'(\d{2}/\d{2}/\d{4}\s+\d{1,2}:\d{2}\s*(?:AM|PM)\s*ET)', sub)
            if ts_m: sold_ts = ts_m.group(1)
            amt_m = (re.search(r'Amount\s*\n+\s*\$([\d,]+\.\d{2})', sub) or
                     re.search(r'\$([\d,]+\.\d{2})', sub))
            if amt_m: sold_amt = amt_m.group(1)
            for lbl in ['3rd Party Bidder', 'Certificate Holder', 'Cert Holder',
                        'Plaintiff', 'Tax Deed Applicant', '3rd Party']:
                if re.search(re.escape(lbl), sub, re.IGNORECASE):
                    sold_to = lbl
                    break
        elif re.search(r'Auction\s*Status\s*\n+\s*Redeemed', seg_to_parcel, re.IGNORECASE):
            status_text = 'Redeemed'
        elif re.search(r'Auction\s*Status\s*\n+\s*Cancell?ed', seg_to_parcel, re.IGNORECASE):
            status_text = 'Canceled'
        elif re.search(r'Auction\s*Status\s*\n+\s*Postponed', seg_to_parcel, re.IGNORECASE):
            status_text = 'Postponed'
        elif re.search(r'Auction\s*Status\s*\n+\s*Struck', seg_to_parcel, re.IGNORECASE):
            status_text = 'Struck-Off'
        elif re.search(r'Auction\s*Status\s*\n+\s*Waiting', seg_to_parcel, re.IGNORECASE):
            status_text = 'Waiting'
        else:
            status_text = 'Waiting'  # default for upcoming auctions

        def grab(label):
            m = re.search(label + r':\s*\|\s*([^\|\n]+?)\s*\|', seg, re.IGNORECASE)
            if m:
                val = re.sub(r'\s+', ' ', m.group(1)).strip()
                return val[:200] if val else None
            # Also handle "Label\nValue" format
            m2 = re.search(label + r'\s*\n+\s*([^\n]{1,150})', seg, re.IGNORECASE)
            if m2:
                val = re.sub(r'\s+', ' ', m2.group(1)).strip()
                return val[:200] if val else None
            return None

        case_num   = grab('Case #') or grab('Case Number')
        prop_addr  = grab('Property Address') or grab('Address')
        open_bid_t = grab('Opening Bid') or grab('Opening')
        assessed_t = grab('Assessed Value') or grab('Assessed')
        auction_tp = grab('Auction Type')
        cert_num   = grab('Certificate #') or grab('Certificate')

        # skip cards with no case number (unparseable segment)
        if not case_num:
            continue

        # parse opening_bid to float
        opening_bid = None
        if open_bid_t:
            clean = re.sub(r'[^\d.]', '', open_bid_t)
            if clean:
                try:
                    opening_bid = float(clean)
                except ValueError:
                    pass

        cards.append({
            'parcel_id':      pm.group(1),
            'case_number':    case_num,
            'property_address': prop_addr,
            'opening_bid':    opening_bid,
            'assessed_value': assessed_t,
            'auction_type':   auction_tp,
            'certificate_number': cert_num,
            '_status':        status_text,
            '_sold_to':       sold_to,
            '_canon':         canonicalize(status_text, sold_to),
        })

    return cards


def scrape_preview(auction_date: date):
    """
    Scrape the PREVIEW page for a specific auction date.
    Paginates via #curPCA up to MAX_PAGES.
    Returns list of card dicts.
    """
    MAX_PAGES = 12
    date_slash = auction_date.strftime('%m/%d/%Y')
    url = f'{BASE_URL}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={date_slash}'
    print(f'  [preview] {url}')

    md, _, err = firecrawl(url, PREVIEW_P1_ACTIONS)
    if err or not md:
        print(f'    page 1 failed: {err}')
        return []

    cards = extract_cards(md)
    seen  = {c['parcel_id'] for c in cards}
    print(f'    page 1: md={len(md)} cards={len(cards)}')

    for pg in range(2, MAX_PAGES + 1):
        time.sleep(2)
        pg_md, _, pg_err = firecrawl(url, paginate_actions(pg))
        if pg_err or not pg_md:
            print(f'    page {pg} failed: {pg_err} — stopping pagination')
            break
        pg_cards = extract_cards(pg_md)
        new = [c for c in pg_cards if c['parcel_id'] not in seen]
        if not new:
            print(f'    page {pg}: no new cards — stopping')
            break
        for c in new:
            seen.add(c['parcel_id'])
        cards.extend(new)
        print(f'    page {pg}: {len(new)} new | total={len(cards)}')

    return cards


# ── PHASE C: UPSERT → MULTI_COUNTY_AUCTIONS ──────────────────────────────────

def upsert_to_mca(cards, auction_date: date):
    """Batch-upsert cards to multi_county_auctions. Returns (inserted, errors)."""
    now_iso  = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    date_iso = auction_date.isoformat()

    rows = []
    for c in cards:
        row = {
            'county':          COUNTY,
            'case_number':     c['case_number'],
            'auction_date':    date_iso,
            'sale_type':       SALE_TYPE,
            'auction_type':    SALE_TYPE,
            'source_platform': PLATFORM,
            'auction_status':  'upcoming',
            'state':           'FL',
            'last_seen_at':    now_iso,
            'data_source':     'calendar_sweep_mca_v1',
        }
        if c.get('property_address'):
            row['property_address'] = c['property_address']
        if c.get('opening_bid') is not None:
            row['opening_bid'] = c['opening_bid']
        if c.get('parcel_id'):
            row['parcel_id'] = c['parcel_id']
        rows.append(row)

    if not rows:
        return 0, []

    inserted = 0
    errors   = []
    BATCH    = 50
    for i in range(0, len(rows), BATCH):
        batch = rows[i:i + BATCH]
        try:
            r = requests.post(
                f'{REST}/multi_county_auctions',
                json=batch,
                headers={**SUPA_H, 'Prefer': 'resolution=merge-duplicates,return=minimal'},
                timeout=30,
            )
            if r.status_code in (200, 201):
                inserted += len(batch)
            else:
                err = f'batch {i // BATCH + 1}: http {r.status_code} {r.text[:200]}'
                errors.append(err)
                print(f'  ! {err}', file=sys.stderr)
        except requests.RequestException as e:
            err = f'batch {i // BATCH + 1}: {e}'
            errors.append(err)
            print(f'  ! {err}', file=sys.stderr)

    return inserted, errors


# ── MAIN ─────────────────────────────────────────────────────────────────────

# Phase A
future_dates, cal_err = scrape_calendar()
if cal_err:
    print(f'ERROR: Calendar scrape failed: {cal_err}', file=sys.stderr)
    sys.exit(1)

if not future_dates:
    print(f'NOTE: {COUNTY}/{SALE_TYPE} — zero future dates on calendar; county is genuinely dark',
          file=sys.stderr)
    # Write to GHA step summary for visibility
    gh_summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if gh_summary:
        with open(gh_summary, 'a') as f:
            f.write(f'## {COUNTY}/{SALE_TYPE}: DARK (no future dates)\n')
            f.write(f'- Platform: {PLATFORM}\n- Base: {BASE_URL}\n')
    sys.exit(2)

# Cap at 5 future dates to control Firecrawl spend
target_dates = future_dates[:5]
print(f'\nScraping {len(target_dates)} future dates: {target_dates}')

# Phase B + C
total_upserted = 0
all_errors     = []

for auction_date in target_dates:
    print(f'\n--- {COUNTY} | {auction_date} ---')
    time.sleep(2)
    cards = scrape_preview(auction_date)
    if not cards:
        print(f'  NOTE: Zero cards for {auction_date} (no listings or parse failure)')
        continue
    upserted, errs = upsert_to_mca(cards, auction_date)
    total_upserted += upserted
    all_errors.extend(errs)
    print(f'  → upserted {upserted} / {len(cards)} cards for {auction_date}')

# Verify: quick SELECT to confirm rows landed
verify_url = (
    f'{REST}/multi_county_auctions?county=eq.{COUNTY}'
    f'&auction_date=gte.{TODAY.isoformat()}'
    f'&source_platform=eq.{PLATFORM}'
    '&select=auction_date,case_number&limit=5'
)
try:
    vr = requests.get(verify_url, headers=SUPA_H, timeout=20)
    if vr.status_code == 200:
        sample = vr.json()
        print(f'\nVERIFY: {len(sample)} rows in MCA for {COUNTY}/{PLATFORM} (sample: {sample[:3]})')
    else:
        print(f'\nVERIFY: SELECT returned {vr.status_code}', file=sys.stderr)
except Exception as e:
    print(f'\nVERIFY: failed: {e}', file=sys.stderr)

# GHA step summary
gh_summary = os.environ.get('GITHUB_STEP_SUMMARY')
if gh_summary:
    with open(gh_summary, 'a') as f:
        f.write(f'## {COUNTY}/{SALE_TYPE} on {PLATFORM}\n')
        f.write(f'- Target dates: `{target_dates}`\n')
        f.write(f'- Rows upserted: **{total_upserted}**\n')
        if all_errors:
            f.write(f'- Errors: {all_errors[:3]}\n')

# GHA outputs
gh_out = os.environ.get('GITHUB_OUTPUT')
if gh_out:
    with open(gh_out, 'a') as f:
        f.write(f'rows_upserted={total_upserted}\n')
        f.write(f'dates_scraped={len(target_dates)}\n')

# Exit decision
if total_upserted == 0 and all_errors:
    print(f'ERROR: 0 rows upserted, {len(all_errors)} errors', file=sys.stderr)
    sys.exit(1)

if total_upserted == 0:
    print(f'NOTE: Zero rows upserted — {COUNTY}/{SALE_TYPE} has no upcoming listings on calendar',
          file=sys.stderr)
    sys.exit(2)

print(f'\nSUCCESS: {total_upserted} rows upserted to multi_county_auctions for {COUNTY}/{SALE_TYPE}')
sys.exit(0)
